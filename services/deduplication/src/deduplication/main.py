"""
Deduplication Service for Real-Time Crypto Price Predictor

This service processes Kafka streams and removes duplicate messages based on:
- Trades: product_id + timestamp_ms
- Candles: pair + window_start_ms + window_end_ms  
- Technical Indicators: pair + window_start_ms + window_end_ms

The service maintains an in-memory cache with TTL for efficient deduplication.
"""

import json
import time
import threading
from typing import Dict, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler

from loguru import logger
from quixstreams import Application
from quixstreams.models import TopicConfig


@dataclass
class DeduplicationConfig:
    """Configuration for the deduplication service"""
    kafka_broker_address: str = "localhost:9092"
    input_topics: list = None
    output_topics: list = None
    cache_ttl_seconds: int = 3600  # 1 hour
    cache_cleanup_interval: int = 300  # 5 minutes
    health_port: int = 8080

    def __post_init__(self):
        if self.input_topics is None:
            self.input_topics = ["trades", "candles", "technical-indicators"]
        if self.output_topics is None:
            self.output_topics = ["trades-dedupe", "candles-dedupe", "technical-indicators-dedupe"]


class DeduplicationCache:
    """Thread-safe cache for tracking seen message keys with TTL"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, float]] = defaultdict(dict)  # topic -> {key: timestamp}
        self._lock = threading.RLock()
        self._stats = {
            "total_processed": 0,
            "duplicates_found": 0,
            "cache_size": 0
        }
    
    def is_duplicate(self, topic: str, key: str) -> bool:
        """Check if a message key is a duplicate"""
        current_time = time.time()
        
        with self._lock:
            if key in self._cache[topic]:
                # Found duplicate
                self._stats["duplicates_found"] += 1
                logger.debug(f"Duplicate found for topic {topic}, key: {key}")
                return True
            
            # Not a duplicate, store it
            self._cache[topic][key] = current_time
            self._stats["total_processed"] += 1
            return False
    
    def cleanup_expired(self):
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_count = 0
        
        with self._lock:
            for topic in list(self._cache.keys()):
                expired_keys = [
                    key for key, timestamp in self._cache[topic].items()
                    if current_time - timestamp > self.ttl_seconds
                ]
                
                for key in expired_keys:
                    del self._cache[topic][key]
                    expired_count += 1
                
                # Remove empty topic entries
                if not self._cache[topic]:
                    del self._cache[topic]
            
            self._stats["cache_size"] = sum(len(topic_cache) for topic_cache in self._cache.values())
        
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired cache entries")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self._lock:
            return {
                **self._stats,
                "cache_size": sum(len(topic_cache) for topic_cache in self._cache.values())
            }


class DeduplicationService:
    """Main deduplication service"""
    
    def __init__(self, config: DeduplicationConfig):
        self.config = config
        self.cache = DeduplicationCache(config.cache_ttl_seconds)
        self._running = False
        self._health_status = {"healthy": True, "ready": False}
        
        # Start cache cleanup thread
        self._start_cache_cleanup()
        
        # Start health server
        self._start_health_server()
    
    def _start_cache_cleanup(self):
        """Start background thread for cache cleanup"""
        def cleanup_worker():
            while self._running:
                time.sleep(self.config.cache_cleanup_interval)
                if self._running:
                    self.cache.cleanup_expired()
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info(f"Cache cleanup thread started (interval: {self.config.cache_cleanup_interval}s)")
    
    def _start_health_server(self):
        """Start health check HTTP server"""
        class HealthHandler(BaseHTTPRequestHandler):
            def __init__(self, service_instance, *args, **kwargs):
                self.service = service_instance
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                if self.path == "/health":
                    self._handle_health()
                elif self.path == "/ready":
                    self._handle_ready()
                elif self.path == "/stats":
                    self._handle_stats()
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def _handle_health(self):
                status_code = 200 if self.service._health_status["healthy"] else 503
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(self.service._health_status).encode())
            
            def _handle_ready(self):
                status_code = 200 if self.service._health_status["ready"] else 503
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(self.service._health_status).encode())
            
            def _handle_stats(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                stats = self.service.cache.get_stats()
                self.wfile.write(json.dumps(stats).encode())
            
            def log_message(self, format, *args):
                pass  # Suppress HTTP server logs
        
        def create_handler(*args, **kwargs):
            return HealthHandler(self, *args, **kwargs)
        
        def run_server():
            try:
                server = HTTPServer(('0.0.0.0', self.config.health_port), create_handler)
                logger.info(f"Health server started on port {self.config.health_port}")
                server.serve_forever()
            except Exception as e:
                logger.error(f"Health server error: {e}")
        
        health_thread = threading.Thread(target=run_server, daemon=True)
        health_thread.start()
    
    def _generate_dedup_key(self, topic: str, message: dict) -> Optional[str]:
        """Generate deduplication key based on topic and message content"""
        try:
            if topic == "trades":
                # For trades: product_id + timestamp_ms
                return f"{message['product_id']}:{message['timestamp_ms']}"
            
            elif topic in ["candles", "technical-indicators"]:
                # For candles/technical indicators: pair + window_start_ms + window_end_ms
                return f"{message['pair']}:{message['window_start_ms']}:{message['window_end_ms']}"
            
            else:
                logger.warning(f"Unknown topic for deduplication: {topic}")
                return None
                
        except KeyError as e:
            logger.error(f"Missing required field {e} in message from topic {topic}")
            return None
    
    def process_topic(self, input_topic: str, output_topic: str):
        """Process a single topic for deduplication"""
        logger.info(f"Starting deduplication for {input_topic} -> {output_topic}")
        
        app = Application(
            broker_address=self.config.kafka_broker_address,
            consumer_group=f"deduplication-{input_topic}",
            auto_create_topics=True
        )
        
        # Input topic
        input_topic_config = app.topic(
            name=input_topic,
            value_serializer="json"
        )
        
        # Output topic
        output_topic_config = app.topic(
            name=output_topic,
            value_serializer="json",
            config=TopicConfig(replication_factor=1, num_partitions=4)
        )
        
        # Create streaming dataframe
        sdf = app.dataframe(topic=input_topic_config)
        
        def deduplicate_message(message: dict) -> Optional[dict]:
            """Deduplicate a single message"""
            dedup_key = self._generate_dedup_key(input_topic, message)
            
            if dedup_key is None:
                logger.warning(f"Could not generate dedup key for message: {message}")
                return message  # Pass through if we can't generate key
            
            if self.cache.is_duplicate(input_topic, dedup_key):
                logger.debug(f"Dropping duplicate message: {dedup_key}")
                return None  # Drop duplicate
            
            return message  # Pass through unique message
        
        # Apply deduplication
        sdf = sdf.apply(deduplicate_message)
        
        # Filter out None values (duplicates)
        sdf = sdf.filter(lambda x: x is not None)
        
        # Log processed messages
        sdf = sdf.update(lambda msg: logger.debug(f"Processed unique message from {input_topic}"))
        
        # Send to output topic
        sdf = sdf.to_topic(output_topic_config)
        
        logger.info(f"Deduplication pipeline ready for {input_topic}")
        app.run()
    
    def run(self):
        """Run the deduplication service"""
        self._running = True
        self._health_status["ready"] = True
        
        logger.info("Starting deduplication service")
        logger.info(f"Input topics: {self.config.input_topics}")
        logger.info(f"Output topics: {self.config.output_topics}")
        
        if len(self.config.input_topics) != len(self.config.output_topics):
            raise ValueError("Number of input topics must match number of output topics")
        
        # Create threads for each topic pair
        threads = []
        for input_topic, output_topic in zip(self.config.input_topics, self.config.output_topics):
            thread = threading.Thread(
                target=self.process_topic,
                args=(input_topic, output_topic),
                daemon=True
            )
            thread.start()
            threads.append(thread)
        
        logger.info(f"Started {len(threads)} deduplication threads")
        
        try:
            # Wait for all threads
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            logger.info("Shutting down deduplication service")
        finally:
            self._running = False
            self._health_status["healthy"] = False
            self._health_status["ready"] = False


def main():
    """Main entry point"""
    import os
    
    config = DeduplicationConfig(
        kafka_broker_address=os.getenv("KAFKA_BROKER_ADDRESS", "localhost:9092"),
        cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
        cache_cleanup_interval=int(os.getenv("CACHE_CLEANUP_INTERVAL", "300")),
        health_port=int(os.getenv("HEALTH_PORT", "8080"))
    )
    
    # Override topics from environment if provided
    if os.getenv("INPUT_TOPICS"):
        config.input_topics = os.getenv("INPUT_TOPICS").split(",")
    if os.getenv("OUTPUT_TOPICS"):
        config.output_topics = os.getenv("OUTPUT_TOPICS").split(",")
    
    logger.info("Starting Deduplication Service")
    logger.info(f"Configuration: {config}")
    
    service = DeduplicationService(config)
    
    try:
        service.run()
    except Exception as e:
        logger.error(f"Service error: {e}")
        raise


if __name__ == "__main__":
    main() 