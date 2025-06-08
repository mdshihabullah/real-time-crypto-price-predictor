"""Main module for the candles service"""

from datetime import timedelta

from loguru import logger
from quixstreams import Application
from quixstreams.models import TopicConfig

from candles.config import config


def custom_ts_extractor(value, headers, timestamp,timestamp_type):

    """
    Specifying a custom timestamp extractor to use the timestamp from the message payload 
    instead of Kafka timestamp.
    """
    return value["timestamp_ms"]


def init_candle(trade: dict) -> dict:
    """
    Initialize a candle with the first trade
    """
    # breakpoint()
    return {
        'open': trade['price'],
        'high': trade['price'],
        'low': trade['price'],
        'close': trade['price'],
        'volume': trade['quantity'],
        'timestamp_ms': trade['timestamp_ms'],
        'pair': trade['product_id'],
    }


def update_candle(candle: dict, current_trade: dict) -> dict:
    """
    Update the candle with the latest trade
    """
    # breakpoint()
    candle['close'] = current_trade['price']
    candle['high'] = max(candle['high'], current_trade['price'])
    candle['low'] = min(candle['low'], current_trade['price'])
    candle['volume'] += current_trade['quantity']
    candle['timestamp_ms'] = current_trade['timestamp_ms']
    candle['pair'] = current_trade['product_id']

    return candle

def run (
        kafka_broker_address:str,
        kafka_input_topic:str,
        kafka_output_topic:str,
        window_in_sec:int,
        kafka_consumer_group:str,
        emit_intermediate_candles:bool=True
):
    """
    Run the application to consume trades and produce candles in real time
    """
    app = Application(
        broker_address=kafka_broker_address,
        consumer_group=kafka_consumer_group
    )

    # Define a topic "my_topic" with JSON serialization
    input_topic = app.topic(name=kafka_input_topic,
                            value_serializer="json",
                            timestamp_extractor=custom_ts_extractor,
                            config=TopicConfig(
                                num_partitions=4,
                                replication_factor=1
                                )
                            )
    output_topic = app.topic(
        name=kafka_output_topic,
        value_serializer="json",
        config=TopicConfig(
            num_partitions=4,
            replication_factor=1
        )
    )

    sdf = app.dataframe(topic=input_topic)

    sdf = (
        # Define a tumbling window with grace period to handle late-arriving messages
        sdf.tumbling_window(
            duration_ms=timedelta(seconds=window_in_sec),
            grace_ms=timedelta(seconds=10),  # Added grace period for late messages
        )
        .reduce(reducer=update_candle, initializer=init_candle)
    )

    if emit_intermediate_candles:
        # Emit all intermediate candles to make the system more responsive
        # Using partition closing strategy for more timely updates across all pairs
        sdf = sdf.current(closing_strategy="partition")
    else:
        # Emit only the final candle
        # Using partition closing strategy to ensure all pairs' windows close timely
        sdf = sdf.final(closing_strategy="partition")

    # Extract open, high, low, close, volume, timestamp_ms, pair from the dataframe
    sdf['open'] = sdf['value']['open']
    sdf['high'] = sdf['value']['high']
    sdf['low'] = sdf['value']['low']
    sdf['close'] = sdf['value']['close']
    sdf['volume'] = sdf['value']['volume']
    # sdf['timestamp_ms'] = sdf['value']['timestamp_ms']
    sdf['pair'] = sdf['value']['pair']

    # Extract window start and end timestamps
    sdf['window_start_ms'] = sdf['start']
    sdf['window_end_ms'] = sdf['end']

    # keep only the relevant columns
    sdf = sdf[
        [
            'pair',
            # 'timestamp_ms',
            'open',
            'high',
            'low',
            'close',
            'volume',
            'window_start_ms',
            'window_end_ms',
        ]
    ]

    sdf['window_in_sec'] = window_in_sec

    # logging on the console
    sdf = sdf.update(lambda value: logger.debug(f'Candle: {value}'))
    sdf = sdf.to_topic(topic=output_topic)

    app.run()


if __name__ == "__main__":
    run(
        kafka_broker_address=config.kafka_broker_address,
        kafka_input_topic=config.kafka_input_topic,
        kafka_output_topic=config.kafka_output_topic,
        window_in_sec=config.window_in_sec,
        kafka_consumer_group=config.kafka_consumer_group,
        emit_intermediate_candles=config.emit_intermediate_candles
        )
