"""Kraken WebSocket API connector"""

import json
import time
from datetime import datetime
from typing import Optional

from loguru import logger
from websocket import create_connection, WebSocket

from websocket._exceptions import (
    WebSocketConnectionClosedException,
    WebSocketTimeoutException,
)

from trades.trade import Trade


class KrakenWebSocketAPI:
    """
    Enhanced Kraken WebSocket API with robust error handling and auto-reconnection
    """

    URL = "wss://ws.kraken.com/v2"
    RECONNECT_DELAY = 5  # seconds
    MAX_RECONNECT_ATTEMPTS = 10
    HEARTBEAT_TIMEOUT = 30  # seconds
    CONNECTION_TIMEOUT = 10  # seconds

    def __init__(
        self,
        product_ids: list[str],
    ):
        self.product_ids = product_ids
        self._ws_client: Optional[WebSocket] = None
        self._last_heartbeat = time.time()
        self._reconnect_attempts = 0
        self._connected = False

        # Initialize connection
        self._connect()

    def _connect(self) -> bool:
        """
        Create WebSocket connection with retry logic

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("Establishing WebSocket connection to Kraken...")

            # Close existing connection if any
            self._cleanup_connection()

            # Create new connection with timeout
            self._ws_client = create_connection(
                self.URL, timeout=self.CONNECTION_TIMEOUT
            )

            # Send initial subscribe message
            self._subscribe(self.product_ids)

            self._connected = True
            self._last_heartbeat = time.time()
            self._reconnect_attempts = 0

            logger.info("✅ WebSocket connection established successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to establish WebSocket connection: {e}")
            self._connected = False
            return False

    def _cleanup_connection(self):
        """Clean up existing WebSocket connection"""
        if self._ws_client:
            try:
                self._ws_client.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket connection: {e}")
            finally:
                self._ws_client = None
                self._connected = False

    def _reconnect(self) -> bool:
        """
        Attempt to reconnect with exponential backoff

        Returns:
            bool: True if reconnection successful, False otherwise
        """
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error(
                f"Max reconnection attempts ({self.MAX_RECONNECT_ATTEMPTS}) reached"
            )
            return False

        self._reconnect_attempts += 1

        # Exponential backoff with jitter
        delay = min(self.RECONNECT_DELAY * (2 ** (self._reconnect_attempts - 1)), 60)

        logger.warning(
            f"Attempting reconnection #{self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS} "
            f"in {delay} seconds..."
        )

        time.sleep(delay)
        return self._connect()

    def _is_connection_healthy(self) -> bool:
        """
        Check if WebSocket connection is healthy

        Returns:
            bool: True if connection is healthy, False otherwise
        """
        if not self._connected or not self._ws_client:
            return False

        # Check for heartbeat timeout
        if time.time() - self._last_heartbeat > self.HEARTBEAT_TIMEOUT:
            logger.warning("Heartbeat timeout detected")
            return False

        return True

    def get_trades(self) -> list[Trade]:
        """
        Get the trades from the Kraken WebSocket API with robust error handling
        """
        # Check connection health before attempting to receive data
        if not self._is_connection_healthy():
            logger.warning("Connection unhealthy, attempting reconnection...")
            if not self._reconnect():
                logger.error("Failed to reconnect, returning empty trades list")
                return []

        try:
            # Set socket timeout to prevent hanging
            self._ws_client.settimeout(10.0)
            
            # Receive data with timeout
            data: str = self._ws_client.recv()

            # Handle heartbeat messages
            if "heartbeat" in data:
                logger.debug("Heartbeat received")
                self._last_heartbeat = time.time()
                return []

            # Transform raw string into a JSON object
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON: {e}")
                return []

            try:
                trades_data = data["data"]
            except KeyError as e:
                logger.error(f"No `data` field with trades in the message {e}")
                return []

            trades = [
                Trade(
                    product_id=trade["symbol"],
                    price=trade["price"],
                    quantity=trade["qty"],
                    timestamp=trade["timestamp"],
                    timestamp_ms=int(
                        datetime.fromisoformat(trade["timestamp"]).timestamp() * 1000
                    ),
                )
                for trade in trades_data
            ]

            return trades

        except WebSocketConnectionClosedException:
            logger.error("WebSocket connection closed unexpectedly")
            self._connected = False
            # Attempt immediate reconnection
            if self._reconnect():
                return []  # Return empty list for this iteration
            else:
                raise Exception("WebSocket connection failed and could not reconnect")

        except WebSocketTimeoutException:
            logger.warning("WebSocket receive timeout")
            return []

        except Exception as e:
            logger.error(f"Unexpected error in WebSocket receive: {e}")
            self._connected = False
            # Attempt reconnection for unexpected errors
            if not self._reconnect():
                raise Exception(f"WebSocket error: {e}")
            return []

    def _subscribe(self, product_ids: list[str]):
        """
        Subscribes to the websocket for the given `product_ids`
        and waits for the initial snapshot.
        """
        try:
            # send a subscribe message to the websocket
            subscribe_message = json.dumps(
                {
                    "method": "subscribe",
                    "params": {
                        "channel": "trade",
                        "symbol": product_ids,
                        "snapshot": False,
                    },
                }
            )

            self._ws_client.send(subscribe_message)
            logger.info(f"Subscribed to trades for: {product_ids}")

            # discard the first 2 messages for each product_id
            # as they contain no trade data
            for product_id in product_ids:
                try:
                    _ = self._ws_client.recv()
                    _ = self._ws_client.recv()
                except Exception as e:
                    logger.warning(
                        f"Error discarding initial messages for {product_id}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error in WebSocket subscription: {e}")
            raise

    def close(self):
        """Close the WebSocket connection gracefully"""
        logger.info("Closing WebSocket connection...")
        self._cleanup_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
