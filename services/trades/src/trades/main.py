"""Main module for the trades service"""

import sys
import time
import threading
from typing import List
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

from loguru import logger
from quixstreams import Application
from quixstreams.models import TopicConfig

from trades.config import config
from trades.kraken_rest_api import KrakenRESTAPI
from trades.kraken_websocket_api import KrakenWebSocketAPI
from trades.trade import Trade


# Global health status
health_status = {
    "healthy": False,
    "ready": False,
    "last_trade_time": None,
    "websocket_connected": False,
    "kafka_connected": False,
}


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints"""

    def do_GET(self):
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/ready":
            self._handle_ready()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_health(self):
        """Liveness probe - service is running"""
        if health_status["healthy"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "unhealthy"}).encode())

    def _handle_ready(self):
        """Readiness probe - service is ready to accept traffic"""
        if health_status["ready"] and health_status["websocket_connected"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "status": "ready",
                        "websocket_connected": health_status["websocket_connected"],
                        "kafka_connected": health_status["kafka_connected"],
                        "last_trade_time": health_status["last_trade_time"],
                    }
                ).encode()
            )
        else:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "status": "not_ready",
                        "websocket_connected": health_status["websocket_connected"],
                        "kafka_connected": health_status["kafka_connected"],
                    }
                ).encode()
            )

    def log_message(self, format, *args):
        """Suppress default HTTP server logging"""
        pass


def start_health_server():
    """Start health check HTTP server in background thread"""

    def run_server():
        try:
            server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
            logger.info("Health check server started on port 8000")
            server.serve_forever()
        except Exception as e:
            logger.error(f"Health server error: {e}")

    health_thread = threading.Thread(target=run_server, daemon=True)
    health_thread.start()


def custom_ts_extractor(value, headers, timestamp, timestamp_type):
    """
    Specifying a custom timestamp extractor to use the timestamp from the message payload
    instead of Kafka timestamp.
    """
    return value["timestamp_ms"]


def setup_kafka(
    kafka_broker_address: str, kafka_topic: str
) -> tuple[Application, TopicConfig]:
    """Set up Kafka application and topic"""
    # Create an Application and tell it to create topics automatically
    app = Application(broker_address=kafka_broker_address, auto_create_topics=True)

    # Define a topic with JSON serialization
    topic = app.topic(
        name=kafka_topic,
        value_serializer="json",
        timestamp_extractor=custom_ts_extractor,
        config=TopicConfig(
            replication_factor=1, num_partitions=len(config.product_ids)
        ),
    )

    return app, topic


def publish_trade(producer, topic: TopicConfig, event: Trade) -> None:
    """Publish a single trade to Kafka"""
    try:
        # Serialize an event using the defined Topic
        message = topic.serialize(key=event.product_id, value=event.to_dict())

        # Produce a message into the Kafka topic
        producer.produce(topic=topic.name, value=message.value, key=message.key)

        # Update health status
        health_status["kafka_connected"] = True
        health_status["last_trade_time"] = time.time()

    except Exception as e:
        logger.error(f"Failed to publish trade to Kafka: {e}")
        health_status["kafka_connected"] = False
        raise


def process_historical_data(
    producer, topic: TopicConfig, kraken_api: KrakenRESTAPI
) -> None:
    """Process historical data from REST API using progressive streaming or traditional batch"""
    logger.info(f"Fetching trade data for the last {config.last_n_days} days")

    if config.enable_progressive_streaming:
        logger.info(
            "Using progressive streaming - trades will be published to Kafka as fetched"
        )
        _process_historical_data_streaming(producer, topic, kraken_api)
    else:
        logger.info(
            "Using traditional batch processing - all trades collected before publishing"
        )
        _process_historical_data_batch(producer, topic, kraken_api)


def _process_historical_data_streaming(
    producer, topic: TopicConfig, kraken_api: KrakenRESTAPI
) -> None:
    """Process historical data using progressive streaming (recommended)"""
    try:
        # Define callback function to publish trades as they are fetched
        def publish_batch_to_kafka(trades: List[Trade]) -> None:
            """Callback to publish a batch of trades to Kafka immediately"""
            for trade in trades:
                publish_trade(producer, topic, trade)
            logger.info(f"Published {len(trades)} trades to Kafka topic '{topic.name}'")

        # Show progress indication
        sys.stdout.write("Streaming trades data to Kafka as fetched...\n")
        sys.stdout.flush()

        # Stream trades with progressive publishing to Kafka
        start_time = time.time()
        events: list[Trade] = kraken_api.get_trades_streaming(
            callback=publish_batch_to_kafka
        )
        elapsed = time.time() - start_time

        logger.info(
            f"Streamed and published {len(events)} trades in {elapsed:.2f} seconds"
        )

        if not events:
            logger.warning(
                "No trades were found. Check the time range and product IDs."
            )
            return

        logger.info(
            f"Successfully backfilled and streamed {len(events)} trades for "
            f"{config.last_n_days} days to Kafka"
        )
        logger.info("All historical trades have been published to Kafka progressively")

    except Exception as e:
        logger.error(f"Error in streaming REST API mode: {e}")
        raise


def _process_historical_data_batch(
    producer, topic: TopicConfig, kraken_api: KrakenRESTAPI
) -> None:
    """Process historical data using traditional batch method (legacy)"""
    try:
        # Show progress indication
        sys.stdout.write("Fetching trades data, this may take some time...\n")
        sys.stdout.flush()

        # Get trades with a timeout
        start_time = time.time()
        events: list[Trade] = kraken_api.get_trades()
        elapsed = time.time() - start_time

        logger.info(f"Fetched {len(events)} trades in {elapsed:.2f} seconds")

        if not events:
            logger.warning(
                "No trades were found. Check the time range and product IDs."
            )
            return

        # Show progress during publishing
        total = len(events)
        logger.info(f"Publishing {total} trades to Kafka topic '{topic.name}'")

        for i, event in enumerate(events):
            # Show progress periodically
            if i % 100 == 0 or i == total - 1:
                progress = (i + 1) / total * 100
                sys.stdout.write(
                    f"\rPublishing trades: {i + 1}/{total} ({progress:.1f}%)..."
                )
                sys.stdout.flush()

            publish_trade(producer, topic, event)

        # Clear progress line
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()

        logger.info(
            f"Successfully backfilled {len(events)} trades for {config.last_n_days} days"
        )

    except Exception as e:
        logger.error(f"Error in batch REST API mode: {e}")
        raise


def process_websocket_data(
    producer, topic: TopicConfig, kraken_api: KrakenWebSocketAPI
) -> None:
    """Process streaming data from WebSocket API with robust error handling and recovery"""
    logger.info("Starting enhanced WebSocket streaming mode with auto-recovery")

    # Update health status
    health_status["websocket_connected"] = True
    health_status["ready"] = True

    consecutive_errors = 0
    max_consecutive_errors = 5
    error_backoff_delay = 1  # Start with 1 second
    max_error_delay = 60  # Max 60 seconds between retries
    
    # Keep track of last successful operation to detect stale connections
    last_successful_trade = time.time()
    max_silence_duration = 300  # 5 minutes without trades triggers reconnection
    
    # Connection quality monitoring
    connection_health_checks = 0
    max_health_checks_without_data = 10

    while True:
        try:
            events: list[Trade] = kraken_api.get_trades()

            # Reset error counter on successful operation
            if events:
                consecutive_errors = 0
                error_backoff_delay = 1
                health_status["websocket_connected"] = True
                last_successful_trade = time.time()
                connection_health_checks = 0
                
                for event in events:
                    try:
                        publish_trade(producer, topic, event)
                        logger.debug(f"Published trade: {event.product_id} @ {event.price}")
                    except Exception as e:
                        logger.error(f"Failed to publish trade: {e}")
                        # Continue processing other events even if one fails
            else:
                # No events received - check for stale connection
                connection_health_checks += 1
                current_time = time.time()
                
                if (current_time - last_successful_trade > max_silence_duration or 
                    connection_health_checks > max_health_checks_without_data):
                    logger.warning(
                        f"Potential stale connection detected. "
                        f"No trades for {current_time - last_successful_trade:.1f}s, "
                        f"health checks: {connection_health_checks}"
                    )
                    
                    # Force reconnection by raising an exception
                    kraken_api._connected = False
                    raise Exception("Stale connection detected, forcing reconnection")
                
                # Small delay when no events to prevent CPU spinning
                time.sleep(0.1)

        except Exception as e:
            consecutive_errors += 1
            health_status["websocket_connected"] = False
            connection_health_checks = 0

            logger.error(
                f"Error in WebSocket mode (attempt {consecutive_errors}/{max_consecutive_errors}): {e}"
            )

            # If too many consecutive errors, raise exception to trigger pod restart
            if consecutive_errors >= max_consecutive_errors:
                health_status["healthy"] = False
                health_status["ready"] = False
                logger.critical(
                    f"Too many consecutive errors ({consecutive_errors}). "
                    "Service health degraded - Kubernetes will restart the pod."
                )
                # Sleep before exiting to give health checks time to fail
                time.sleep(10)
                raise Exception(
                    f"WebSocket service failed after {consecutive_errors} consecutive errors"
                )

            # Exponential backoff for error recovery
            logger.warning(
                f"Backing off for {error_backoff_delay} seconds before retry..."
            )
            time.sleep(error_backoff_delay)
            error_backoff_delay = min(error_backoff_delay * 2, max_error_delay)


def run_backfill_job(
    kafka_broker_address: str,
    kafka_topic: str,
    kraken_api: KrakenRESTAPI,
) -> None:
    """Run the backfill job - fetch historical data and exit"""
    logger.info("Starting backfill job - fetching historical data")
    
    # Start health check server
    start_health_server()

    # Mark service as healthy
    health_status["healthy"] = True

    app, topic = setup_kafka(kafka_broker_address, kafka_topic)

    # Create a Producer instance
    with app.get_producer() as producer:
        # Test Kafka connection
        try:
            producer.poll(0)  # Test connection
            health_status["kafka_connected"] = True
            logger.info("✅ Kafka connection established")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka: {e}")
            health_status["kafka_connected"] = False
            raise

        # Process historical data and exit
        process_historical_data(producer, topic, kraken_api)
        logger.info("✅ Backfill job completed successfully")


def run_websocket_job(
    kafka_broker_address: str,
    kafka_topic: str,
    kraken_api: KrakenWebSocketAPI,
) -> None:
    """Run the websocket job - continuously stream live data"""
    logger.info("Starting websocket job - streaming live data")
    
    # Start health check server
    start_health_server()

    # Mark service as healthy
    health_status["healthy"] = True

    app, topic = setup_kafka(kafka_broker_address, kafka_topic)

    # Create a Producer instance
    with app.get_producer() as producer:
        # Test Kafka connection
        try:
            producer.poll(0)  # Test connection
            health_status["kafka_connected"] = True
            logger.info("✅ Kafka connection established")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka: {e}")
            health_status["kafka_connected"] = False
            raise

        # Stream live data continuously
        process_websocket_data(producer, topic, kraken_api)


def run(
    kafka_broker_address: str,
    kafka_topic: str,
    kraken_api: KrakenRESTAPI | KrakenWebSocketAPI,
) -> None:
    """Run the trades service based on job mode"""
    
    # Route to appropriate job type based on configuration
    if config.job_mode == "backfill":
        if not isinstance(kraken_api, KrakenRESTAPI):
            logger.error("Backfill job requires REST API mode")
            raise ValueError("Backfill job requires REST API mode")
        run_backfill_job(kafka_broker_address, kafka_topic, kraken_api)
        
    elif config.job_mode == "websocket":
        if not isinstance(kraken_api, KrakenWebSocketAPI):
            logger.error("WebSocket job requires WebSocket API mode")
            raise ValueError("WebSocket job requires WebSocket API mode")
        run_websocket_job(kafka_broker_address, kafka_topic, kraken_api)
        
    else:
        raise ValueError(f"Unknown job mode: {config.job_mode}")


def configure_logging():
    """Configure logging for the application"""
    logger.add("trades_service.log", rotation="100 MB", level="INFO")


def get_api_client() -> KrakenRESTAPI | KrakenWebSocketAPI:
    """Initialize the appropriate API client based on job mode and configuration"""
    if config.job_mode == "backfill":
        logger.info(
            f"Backfill job: Using Kraken REST API for historical data (last {config.last_n_days} days)"
        )
        return KrakenRESTAPI(
            product_ids=config.product_ids, last_n_days=config.last_n_days
        )
    elif config.job_mode == "websocket":
        logger.info("WebSocket job: Using Kraken WebSocket connector for live data")
        return KrakenWebSocketAPI(product_ids=config.product_ids)
    else:
        # Fallback to old behavior if job_mode is not set properly
        if config.kraken_api_mode == "REST":
            logger.info(
                f"Using Kraken REST API for historical data (last {config.last_n_days} days)"
            )
            return KrakenRESTAPI(
                product_ids=config.product_ids, last_n_days=config.last_n_days
            )
        elif config.kraken_api_mode == "WS":
            logger.info("Using Kraken WebSocket connector for live data")
            return KrakenWebSocketAPI(product_ids=config.product_ids)
        else:
            raise ValueError(f"Unknown job mode: {config.job_mode} or API mode: {config.kraken_api_mode}")


if __name__ == "__main__":
    try:
        # Configure logging
        configure_logging()

        # Initialize the appropriate API
        api = get_api_client()

        # Run the service
        run(
            kafka_broker_address=config.kafka_broker_address,
            kafka_topic=config.kafka_topic,
            kraken_api=api,
        )
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
        health_status["healthy"] = False
        health_status["ready"] = False
    except Exception as e:
        logger.error(f"Service error: {e}")
        health_status["healthy"] = False
        health_status["ready"] = False
        sys.exit(1)
