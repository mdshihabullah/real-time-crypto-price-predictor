"""Kraken REST API connector"""

import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from loguru import logger

from trades.trade import Trade


class KrakenRESTAPI:
    """
    Kraken REST API connector for retrieving historical trade data
    """

    BASE_URL = "https://api.kraken.com/0/public/Trades"
    REQUEST_TIMEOUT = 30  # seconds
    HEADERS = {"Accept": "application/json"}

    def __init__(self, product_ids: List[str], last_n_days: int = 1):
        """
        Initialize the Kraken REST API connector

        Args:
            product_ids: List of product IDs to fetch trades for (e.g., "BTC/EUR")
            last_n_days: Number of days of historical data to retrieve
        """
        self.product_ids = product_ids
        self.last_n_days = last_n_days
        # Store timestamps separately from Trade objects
        self.trade_timestamps: Dict[str, float] = {}
        logger.info(
            f"Initialized KrakenRESTAPI with \
                    product_ids={product_ids}, last_n_days={last_n_days}"
        )

    def _get_timestamp_for_days_ago(self, days: int) -> float:
        """
        Get the UNIX timestamp for N days ago

        Args:
            days: Number of days ago

        Returns:
            UNIX timestamp as float
        """
        target_date = datetime.now() - timedelta(days=days)
        timestamp = target_date.timestamp()
        logger.debug(
            f"Generated timestamp for {days} days ago: \
                     {timestamp} ({target_date.isoformat()})"
        )
        return timestamp

    def _convert_to_nanoseconds(self, timestamp: float) -> str:
        """
        Convert a UNIX timestamp to nanoseconds string format for Kraken API

        Args:
            timestamp: UNIX timestamp in seconds

        Returns:
            Timestamp in nanoseconds as string
        """
        return str(int(timestamp * 1_000_000_000))

    def _fetch_trades_page(
        self, product_id: str, since: Optional[str] = None
    ) -> Tuple[List[Any], Optional[str]]:
        """
        Fetch a single page of trades from Kraken API

        Args:
            product_id: Product ID to fetch trades for (e.g., "BTC/EUR")
            since: Timestamp in nanoseconds to start from (as string)

        Returns:
            Tuple of (trades_data, last_id)
        """
        params = {"pair": product_id}
        if since:
            params["since"] = since

        logger.debug(f"Fetching trades for {product_id} with params: {params}")
        start_time = time.time()

        try:
            response = requests.get(
                url=self.BASE_URL,
                params=params,
                headers=self.HEADERS,
                timeout=self.REQUEST_TIMEOUT,
            )
            elapsed = time.time() - start_time
            logger.debug(
                f"Request completed in {elapsed:.2f}s with status {response.status_code}"
            )

            response.raise_for_status()
            data = response.json()

            if errors := data.get("error"):
                if errors:
                    logger.error(f"Kraken API error for {product_id}: {errors}")
                    return [], None

            result = data["result"]

            # Find the pair key in the result (first key that's not 'last')
            pair_key = next((key for key in result.keys() if key != "last"), None)

            if not pair_key:
                logger.error(
                    f"Could not find trades data for {product_id}, keys in result: {list(result.keys())}"
                )
                return [], None

            trades_data = result[pair_key]
            last_id = result.get(
                "last"
            )  # This is the timestamp in nanoseconds for pagination

            logger.debug(
                f"Received {len(trades_data)} trades for {product_id}, last_id: {last_id}"
            )
            return trades_data, last_id

        except requests.Timeout:
            logger.error(
                f"Request timeout after {self.REQUEST_TIMEOUT}s for {product_id}"
            )
            return [], None
        except requests.RequestException as e:
            logger.error(f"Error fetching trades for {product_id}: {e}")
            return [], None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing response for {product_id}: {e}")
            return [], None
        except Exception as e:
            logger.error(f"Unexpected error for {product_id}: {e}")
            return [], None

    def _transform_trade(
        self, trade_data: list, product_id: str, trade_id: str
    ) -> Optional[Trade]:
        """
        Transform Kraken trade data to Trade model

        Args:
            trade_data: Raw trade data from Kraken API
            product_id: Product ID for the trade
            trade_id: Unique ID for the trade (used for timestamp lookup)

        Returns:
            Trade object or None on error
        """
        # Kraken trade data format: [price, volume, time, buy/sell, market/limit, miscellaneous]
        try:
            price = float(trade_data[0])
            quantity = float(trade_data[1])

            # Get timestamp as float and store it separately by trade_id
            trade_time = float(trade_data[2])
            self.trade_timestamps[trade_id] = trade_time

            # Format timestamp as ISO string for the Trade object
            timestamp = datetime.fromtimestamp(trade_time).isoformat()

            # Format timestamp as milliseconds since epoch
            timestamp_ms = int(trade_time * 1000)

            return Trade(
                product_id=product_id,
                price=price,
                quantity=quantity,
                timestamp=timestamp,
                timestamp_ms=timestamp_ms,
            )
        except (ValueError, IndexError) as e:
            logger.error(f"Error transforming trade data: {e}, data: {trade_data}")
            return None

    def get_trades_streaming(self, callback=None) -> List[Trade]:
        """
        Stream trades for configured product IDs within the last N days,
        calling callback for each batch of trades as they are fetched.
        
        This implements the progressive backfill pattern where trades are
        processed and published to Kafka immediately rather than collecting
        all trades in memory first.

        Args:
            callback: Function to call for each batch of trades. 
                     Signature: callback(trades: List[Trade]) -> None

        Returns:
            List of Trade objects (for compatibility, but consider using callback)
        """
        all_trades = []
        earliest_timestamp = self._get_timestamp_for_days_ago(self.last_n_days)

        logger.info(
            f"Starting to stream trades since {datetime.fromtimestamp(earliest_timestamp).isoformat()}"
        )
        logger.info("Using progressive streaming pattern - trades will be published as fetched")

        # Process each product ID
        for product_id in self.product_ids:
            logger.info(
                f"Streaming trades for {product_id} from the last {self.last_n_days} days"
            )

            # Store the raw timestamps for this product separately
            product_timestamps = []
            total_product_trades = 0

            request_count = 0
            consecutive_empty_pages = 0

            # Convert timestamp to nanoseconds for the API
            current_since = self._convert_to_nanoseconds(earliest_timestamp)

            # Fetch all trades from earliest_timestamp to now
            # The API returns at most 1000 trades per request, so we need multiple requests
            # to get all trades within our time range
            now_timestamp = datetime.now().timestamp()

            while True:
                request_count += 1
                logger.info(
                    f"Fetching request #{request_count} for {product_id} since {current_since}"
                )

                trades_data, last_id = self._fetch_trades_page(
                    product_id, current_since
                )

                if not trades_data:
                    consecutive_empty_pages += 1
                    logger.warning(
                        f"No trades data received for {product_id} on request #{request_count}"
                    )

                    # If we get too many empty responses in a row, something is wrong
                    if consecutive_empty_pages >= 3:
                        logger.error(
                            f"Giving up after {consecutive_empty_pages} consecutive empty responses for {product_id}"
                        )
                        break

                    # Try again after a slightly longer delay
                    time.sleep(5)
                    continue

                consecutive_empty_pages = 0  # Reset counter on success

                # Process trades from this batch and stream them immediately
                batch_trades = []
                latest_trade_time = 0

                for i, trade in enumerate(trades_data):
                    try:
                        trade_time = float(trade[2])
                        latest_trade_time = max(latest_trade_time, trade_time)

                        # Only include trades within our time range
                        # (the API might return trades earlier than our specified since)
                        if trade_time >= earliest_timestamp:
                            # Generate a unique ID for this trade to lookup timestamp later
                            trade_id = f"{product_id}_{request_count}_{i}"

                            trade_obj = self._transform_trade(
                                trade, product_id, trade_id
                            )
                            if trade_obj:
                                batch_trades.append(trade_obj)
                                product_timestamps.append(trade_time)
                    except Exception as e:
                        logger.error(f"Error processing trade: {e}")
                        continue

                # Stream this batch immediately if we have trades
                if batch_trades:
                    logger.info(
                        f"Streaming {len(batch_trades)} trades for {product_id} from request #{request_count}"
                    )
                    
                    # Call the callback to stream trades immediately
                    if callback:
                        try:
                            callback(batch_trades)
                        except Exception as e:
                            logger.error(f"Error in callback for {product_id}: {e}")
                    
                    # Also add to return list for compatibility
                    all_trades.extend(batch_trades)
                    total_product_trades += len(batch_trades)

                # Determine if we've reached the current time
                if (
                    latest_trade_time > 0 and latest_trade_time >= now_timestamp - 60
                ):  # Within a minute of now
                    logger.info(f"Reached current time for {product_id}")
                    break

                # Stop if no more data
                if not last_id:
                    logger.info(f"No more data available for {product_id}")
                    break

                # Check if we're making progress with "since"
                if current_since == last_id:
                    logger.warning(
                        f"Pagination not progressing for {product_id}, last_id unchanged: {last_id}"
                    )
                    break

                # Update for next request - use the last_id (which is the timestamp in nanoseconds of the last trade)
                current_since = last_id

                # Rate limiting with a dynamic backoff strategy
                if request_count % 10 == 0:
                    sleep_time = 2  # Take a slightly longer break every 10 requests
                else:
                    sleep_time = 1

                logger.debug(f"Sleeping for {sleep_time}s before next request")
                time.sleep(sleep_time)

                # Show streaming progress
                if product_timestamps:
                    earliest_collected = min(product_timestamps)
                    latest_collected = max(product_timestamps)

                    days_covered = (latest_collected - earliest_collected) / (
                        24 * 60 * 60
                    )
                    coverage_percent = min(100, (days_covered / self.last_n_days) * 100)

                    progress_msg = f"Streaming {product_id}: {total_product_trades} trades, {days_covered:.1f} days ({coverage_percent:.1f}% of target)"
                    sys.stdout.write(f"\r{progress_msg}...")
                    sys.stdout.flush()

            logger.info(f"Completed streaming {total_product_trades} trades for {product_id}")

            # Reset stdout
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()

        # Clear the timestamp dictionary to free memory
        self.trade_timestamps.clear()

        logger.info(
            f"Completed streaming a total of {len(all_trades)} trades across all products"
        )
        return all_trades

    def get_trades(self) -> List[Trade]:
        """
        Get all trades for configured product IDs within the last N days

        Returns:
            List of Trade objects
        """
        all_trades = []
        earliest_timestamp = self._get_timestamp_for_days_ago(self.last_n_days)

        logger.info(
            f"Starting to fetch trades since {datetime.fromtimestamp(earliest_timestamp).isoformat()}"
        )

        # Process each product ID
        for product_id in self.product_ids:
            logger.info(
                f"Fetching trades for {product_id} from the last {self.last_n_days} days"
            )

            product_trades = []
            # Store the raw timestamps for this product separately
            product_timestamps = []

            request_count = 0
            consecutive_empty_pages = 0

            # Convert timestamp to nanoseconds for the API
            current_since = self._convert_to_nanoseconds(earliest_timestamp)

            # Fetch all trades from earliest_timestamp to now
            # The API returns at most 1000 trades per request, so we need multiple requests
            # to get all trades within our time range
            now_timestamp = datetime.now().timestamp()

            while True:
                request_count += 1
                logger.info(
                    f"Fetching request #{request_count} for {product_id} since {current_since}"
                )

                trades_data, last_id = self._fetch_trades_page(
                    product_id, current_since
                )

                if not trades_data:
                    consecutive_empty_pages += 1
                    logger.warning(
                        f"No trades data received for {product_id} on request #{request_count}"
                    )

                    # If we get too many empty responses in a row, something is wrong
                    if consecutive_empty_pages >= 3:
                        logger.error(
                            f"Giving up after {consecutive_empty_pages} consecutive empty responses for {product_id}"
                        )
                        break

                    # Try again after a slightly longer delay
                    time.sleep(5)
                    continue

                consecutive_empty_pages = 0  # Reset counter on success

                # Process trades from this batch
                new_trades_count = 0
                latest_trade_time = 0

                for i, trade in enumerate(trades_data):
                    try:
                        trade_time = float(trade[2])
                        latest_trade_time = max(latest_trade_time, trade_time)

                        # Only include trades within our time range
                        # (the API might return trades earlier than our specified since)
                        if trade_time >= earliest_timestamp:
                            # Generate a unique ID for this trade to lookup timestamp later
                            trade_id = f"{product_id}_{request_count}_{i}"

                            trade_obj = self._transform_trade(
                                trade, product_id, trade_id
                            )
                            if trade_obj:
                                product_trades.append(trade_obj)
                                product_timestamps.append(trade_time)
                                new_trades_count += 1
                    except Exception as e:
                        logger.error(f"Error processing trade: {e}")
                        continue

                logger.info(
                    f"Added {new_trades_count} trades for {product_id} from request #{request_count}"
                )

                # Determine if we've reached the current time
                if (
                    latest_trade_time > 0 and latest_trade_time >= now_timestamp - 60
                ):  # Within a minute of now
                    logger.info(f"Reached current time for {product_id}")
                    break

                # Stop if no more data
                if not last_id:
                    logger.info(f"No more data available for {product_id}")
                    break

                # Check if we're making progress with "since"
                if current_since == last_id:
                    logger.warning(
                        f"Pagination not progressing for {product_id}, last_id unchanged: {last_id}"
                    )
                    break

                # Update for next request - use the last_id (which is the timestamp in nanoseconds of the last trade)
                current_since = last_id

                # Rate limiting with a dynamic backoff strategy
                if request_count % 10 == 0:
                    sleep_time = 2  # Take a slightly longer break every 10 requests
                else:
                    sleep_time = 1

                logger.debug(f"Sleeping for {sleep_time}s before next request")
                time.sleep(sleep_time)

                # Show progress
                if product_timestamps:
                    earliest_collected = min(product_timestamps)
                    latest_collected = max(product_timestamps)

                    days_covered = (latest_collected - earliest_collected) / (
                        24 * 60 * 60
                    )
                    coverage_percent = min(100, (days_covered / self.last_n_days) * 100)

                    progress_msg = f"Processing {product_id}: {len(product_trades)} trades, {days_covered:.1f} days ({coverage_percent:.1f}% of target)"
                    sys.stdout.write(f"\r{progress_msg}...")
                    sys.stdout.flush()

            logger.info(f"Retrieved {len(product_trades)} trades for {product_id}")
            all_trades.extend(product_trades)

            # Reset stdout
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()

        # Clear the timestamp dictionary to free memory
        self.trade_timestamps.clear()

        logger.info(
            f"Retrieved a total of {len(all_trades)} trades across all products"
        )
        return all_trades
