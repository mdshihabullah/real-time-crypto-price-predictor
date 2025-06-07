"""Main module for the trades service"""

import sys
import time
from typing import Any, List, Optional, Tuple

from loguru import logger
from quixstreams import Application
from quixstreams.models import TimestampType, TopicConfig

from trades.config import config
from trades.kraken_rest_api import KrakenRESTAPI
from trades.kraken_websocket_api import KrakenWebSocketAPI
from trades.trade import Trade


def custom_ts_extractor(value: Any) -> int:
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
    # Serialize an event using the defined Topic
    message = topic.serialize(key=event.product_id, value=event.to_dict())

    # Produce a message into the Kafka topic
    producer.produce(topic=topic.name, value=message.value, key=message.key)


def process_historical_data(
    producer, topic: TopicConfig, kraken_api: KrakenRESTAPI
) -> None:
    """Process historical data from REST API"""
    logger.info(f"Fetching trade data for the last {config.last_n_days} days")

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
        logger.error(f"Error in REST API mode: {e}")
        raise


def process_websocket_data(
    producer, topic: TopicConfig, kraken_api: KrakenWebSocketAPI
) -> None:
    """Process streaming data from WebSocket API"""
    logger.info("Starting WebSocket streaming mode")
    while True:
        try:
            events: list[Trade] = kraken_api.get_trades()

            for event in events:
                publish_trade(producer, topic, event)
                logger.info(f"Produced message with key {event.product_id}")

        except Exception as e:
            logger.error(f"Error in WebSocket mode: {e}")
            # Brief pause before retrying
            time.sleep(5)


def run(
    kafka_broker_address: str,
    kafka_topic: str,
    kraken_api: KrakenRESTAPI | KrakenWebSocketAPI,
) -> None:
    """Run the trades service"""
    app, topic = setup_kafka(kafka_broker_address, kafka_topic)

    # Create a Producer instance
    with app.get_producer() as producer:
        # If using REST API, first get historical data, then switch to WebSocket
        if isinstance(kraken_api, KrakenRESTAPI):
            process_historical_data(producer, topic, kraken_api)

            # After backfill complete, switch to WebSocket for live data
            logger.info("Backfill complete, switching to WebSocket for live data")
            ws_api = KrakenWebSocketAPI(product_ids=config.product_ids)
            process_websocket_data(producer, topic, ws_api)
        else:
            # Just use WebSocket directly
            process_websocket_data(producer, topic, kraken_api)


def configure_logging():
    """Configure logging for the application"""
    logger.add("trades_service.log", rotation="100 MB", level="INFO")


def get_api_client() -> KrakenRESTAPI | KrakenWebSocketAPI:
    """Initialize the appropriate API client based on configuration"""
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
        raise ValueError("Kraken API mode should be either 'REST' or 'WS'")


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
    except Exception as e:
        logger.error(f"Service error: {e}")
        sys.exit(1)
