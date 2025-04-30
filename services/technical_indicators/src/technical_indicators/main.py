"""Main module for the technical indicators service"""

from loguru import logger
from quixstreams import Application

from technical_indicators.candle_utils import update_candles_in_state
from technical_indicators.config import config
from technical_indicators.indicators import compute_technical_indicators
from technical_indicators.tables import create_table_in_risingwave

def run (
        kafka_broker_address:str,
        kafka_input_topic:str,
        kafka_output_topic:str,
        window_in_sec:int,
        kafka_consumer_group:str,
        risingwave_table_name:str
):
    """
    Run the application to consume candles and produce technical indicators
    """
    app = Application(
        broker_address=kafka_broker_address,
        consumer_group=kafka_consumer_group
    )

    # Define a topic "my_topic" with JSON serialization
    candles_topic = app.topic(name=kafka_input_topic, value_serializer="json")
    technical_indicators_topic = app.topic(name=kafka_output_topic,
                                           value_serializer="json")


    sdf = app.dataframe(topic=candles_topic)
    sdf = sdf[sdf['window_in_sec'] == window_in_sec]

    # Step 3. Update the state dictionary with the new candles
    sdf = sdf.apply(update_candles_in_state, stateful=True)

    # Step 4. Compute technical indicators from the candles in the state dictionary
    sdf = sdf.apply(compute_technical_indicators, stateful=True)


    # logging on the console
    sdf = sdf.update(lambda value: logger.debug(f'Candle: {value}'))
    sdf = sdf.to_topic(topic=technical_indicators_topic)

    app.run()


if __name__ == "__main__":
    run(
        kafka_broker_address=config.kafka_broker_address,
        kafka_input_topic=config.kafka_input_topic,
        kafka_output_topic=config.kafka_output_topic,
        window_in_sec=config.window_in_sec,
        kafka_consumer_group=config.kafka_consumer_group,
        risingwave_table_name=config.risingwave_table_name
        )
