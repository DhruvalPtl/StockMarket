"""
This module contains elements for interacting with the Groww API.
"""

import hashlib
import pandas as pd
import random
import requests
import time
import uuid
import warnings

from colorama import Fore, init
from os import path, pardir
from pandas import DataFrame
from typing import Any, Optional, Tuple, Final

from growwapi.common.files import get_cwd
from growwapi.groww.exceptions import (
    GrowwAPIException,
    GrowwAPITimeoutException,
    GrowwAPIAuthenticationException,
    GrowwAPIAuthorisationException,
    GrowwAPIBadRequestException,
    GrowwAPINotFoundException,
    GrowwAPIRateLimitException,
    InstrumentNotFoundException,
)


class GrowwAPI:
    _ERROR_MAP = {
        400: GrowwAPIBadRequestException,
        401: GrowwAPIAuthenticationException,
        403: GrowwAPIAuthorisationException,
        404: GrowwAPINotFoundException,
        429: GrowwAPIRateLimitException,
        504: GrowwAPITimeoutException,
    }

    """
    A client for interacting with the Groww API.
    """

    # Validity constants
    VALIDITY_DAY = "DAY"
    VALIDITY_EOS = "EOS"
    VALIDITY_IOC = "IOC"
    VALIDITY_GTC = "GTC"
    VALIDITY_GTD = "GTD"

    # Exchange constants
    EXCHANGE_BSE = "BSE"
    EXCHANGE_MCX = "MCX"
    EXCHANGE_MCXSX = "MCXSX"
    EXCHANGE_NCDEX = "NCDEX"
    EXCHANGE_NSE = "NSE"
    EXCHANGE_US = "US"

    # OrderType constants
    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_MARKET = "MARKET"
    ORDER_TYPE_STOP_LOSS = "SL"
    ORDER_TYPE_STOP_LOSS_MARKET = "SL_M"

    # Product constants
    PRODUCT_ARBITRAGE = "ARB"
    PRODUCT_BO = "BO"
    PRODUCT_CNC = "CNC"
    PRODUCT_CO = "CO"
    PRODUCT_NRML = "NRML"
    PRODUCT_MIS = "MIS"
    PRODUCT_MTF = "MTF"

    # Segment constants
    SEGMENT_CASH = "CASH"
    SEGMENT_CURRENCY = "CURRENCY"
    SEGMENT_COMMODITY = "COMMODITY"
    SEGMENT_FNO = "FNO"

    # TransactionType constants
    TRANSACTION_TYPE_BUY = "BUY"
    TRANSACTION_TYPE_SELL = "SELL"

    # CandleInterval constants
    CANDLE_INTERVAL_MIN_1 = "1minute"
    CANDLE_INTERVAL_MIN_2 = "2minute"
    CANDLE_INTERVAL_MIN_3 = "3minute"
    CANDLE_INTERVAL_MIN_5 = "5minute"
    CANDLE_INTERVAL_MIN_10 = "10minute"
    CANDLE_INTERVAL_MIN_15 = "15minute"
    CANDLE_INTERVAL_MIN_30 = "30minute"
    CANDLE_INTERVAL_HOUR_1 = "1hour"
    CANDLE_INTERVAL_HOUR_4 = "4hour"
    CANDLE_INTERVAL_DAY = "1day"
    CANDLE_INTERVAL_WEEK = "1week"
    CANDLE_INTERVAL_MONTH = "1month"

    # SmartOrderType constants
    SMART_ORDER_TYPE_GTT = "GTT"
    SMART_ORDER_TYPE_OCO = "OCO"

    # SmartOrderStatus constants
    SMART_ORDER_STATUS_ACTIVE = "ACTIVE"
    SMART_ORDER_STATUS_TRIGGERED = "TRIGGERED"
    SMART_ORDER_STATUS_CANCELLED = "CANCELLED"
    SMART_ORDER_STATUS_EXPIRED = "EXPIRED"
    SMART_ORDER_STATUS_FAILED = "FAILED"
    SMART_ORDER_STATUS_COMPLETED = "COMPLETED"

    # TriggerDirection constants
    TRIGGER_DIRECTION_UP = "UP"
    TRIGGER_DIRECTION_DOWN = "DOWN"

    INSTRUMENT_CSV_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"
    _GROWW_GENERATE_SOCKET_TOKEN_URL: Final[str] = (
        "https://api.groww.in/v1/api/apex/v1/socket/token/create/"
    )

    def __init__(self, token: str) -> None:
        """
        Initialize the GrowwAPI with the given token and key.

        Args:
            token (str): API token for authentication.
        """
        self.domain = "https://api.groww.in/v1"
        self.token = token
        self.instruments = None
        self._display_changelog()
        print("Ready to Groww!")

    def _display_changelog(self):
        """
        Display the changelog for the Groww API by printing messages to the console.
        """

        init(autoreset=True)
        changelog = self._get_changelog()
        info_messages = changelog.get("info", [])
        warning_messages = changelog.get("warning", [])

        if info_messages:
            print(Fore.YELLOW + "INFO:")
            for message in info_messages:
                print(Fore.YELLOW + "- " + message)

        if warning_messages:
            print(Fore.RED + "WARNING:")
            for message in warning_messages:
                print(Fore.RED + "- " + message)

    def _get_changelog(self):
        """
        Get the changelog for the Groww API.
        :return: dict: A dictionary containing the JSON response from the API, or an empty dictionary in case of failure.
        The dictionary may contain the following keys:
            - "info" (list): Informational messages.
            - "warning" (list): Warning messages.
        """
        url = self.domain + "/changelog"
        headers = GrowwAPI._build_headers(self.token)
        try:
            response = self._request_get(
                url=url,
                headers=headers,
            )
            return response.json()
        except Exception as e:
            return {}

    def _download_and_load_instruments(self) -> DataFrame:
        """
        Download the instruments CSV file and load it into a DataFrame.

        Returns:
            DataFrame: The instruments data.
        """
        response = requests.get(self.INSTRUMENT_CSV_URL)
        response.raise_for_status()  # Raise an exception for HTTP errors
        csv_path = path.join(get_cwd(), pardir, "instruments.csv")
        with open(csv_path, "wb") as f:
            f.write(response.content)
        return pd.read_csv(csv_path, dtype="str")

    def _load_instruments(self) -> DataFrame:
        """
        Load the instruments data into a DataFrame.

        Returns:
            DataFrame: The instruments data.
        """
        if self.instruments is None:
            self.instruments = self._download_and_load_instruments()
        return self.instruments

    def place_order(
        self,
        validity: str,
        exchange: str,
        order_type: str,
        product: str,
        quantity: int,
        segment: str,
        trading_symbol: str,
        transaction_type: str,
        order_reference_id: Optional[str] = None,
        price: Optional[float] = 0.0,
        trigger_price: Optional[float] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Place a new order.

        Args:
            validity (str): The validity of the order.
            exchange (str): The exchange to place the order on.
            order_type (str): The type of order.
            price (float): The price of the order in Rupee.
            product (str): The product type.
            quantity (int): The quantity of the order.
            segment (str): The segment of the order.
            trading_symbol (str): The trading symbol to place the order for.
            transaction_type (str): The transaction type.
            order_reference_id (Optional[str]): The reference ID to track the order with. Defaults to a random 8-digit number.
            trigger_price (float): The trigger price of the order in Rupee.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The placed order response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/order/create"

        order_reference_id = (
            order_reference_id
            if order_reference_id is not None
            else str(random.randint(10000000, 99999999))
        )
        headers = GrowwAPI._build_headers(self.token)
        request_body = {
            "trading_symbol": trading_symbol,
            "quantity": quantity,
            "price": price,
            "trigger_price": trigger_price,
            "validity": validity,
            "exchange": exchange,
            "segment": segment,
            "product": product,
            "order_type": order_type,
            "transaction_type": transaction_type,
            "order_reference_id": order_reference_id,
        }

        response = self._request_post(
            url=url,
            json=request_body,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def modify_order(
        self,
        order_type: str,
        segment: str,
        groww_order_id: str,
        quantity: int,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Modify an existing order.

        Args:
            order_type (str): The type of order.
            price (float): The price of the order in Rupee.
            quantity (int): The quantity of the order.
            segment (str): The segment of the order.
            groww_order_id (Optional[str]): The Groww order ID.
            trigger_price (float): The trigger price of the order in Rupee.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The modified order response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/order/modify"
        headers = GrowwAPI._build_headers(self.token)
        request_body = {
            "quantity": quantity,
            "price": price,
            "trigger_price": trigger_price,
            "groww_order_id": groww_order_id,
            "order_type": order_type,
            "segment": segment,
        }

        response = self._request_post(
            url=url,
            json=request_body,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def cancel_order(
        self,
        groww_order_id: str,
        segment: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Cancel an existing order.

        Args:
            groww_order_id (str): The Groww order ID.
            segment (str): The segment of the order.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The cancelled order response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/order/cancel"
        headers = GrowwAPI._build_headers(self.token)
        request_body = {
            "segment": segment,
            "groww_order_id": groww_order_id,
        }

        response = self._request_post(
            url=url,
            json=request_body,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_holdings_for_user(self, timeout: Optional[int] = None) -> dict:
        """
        Get the holdings for the user.

        Args:
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The user's holdings response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/holdings/user"
        response = self._request_get(
            url=url, headers=GrowwAPI._build_headers(self.token), timeout=timeout
        )
        return self._parse_response(response)

    def get_quote(
        self,
        trading_symbol: str,
        exchange: str,
        segment: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Fetch the latest quote data for an instrument.

        Args:
            symbol (str): The symbol to fetch the data for.
            exchange (str): The exchange to fetch the data from.
            segment (str): The segment to fetch the data from.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The latest quote data.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/live-data/quote"
        params = {
            "exchange": exchange,
            "segment": segment,
            "trading_symbol": trading_symbol,
        }
        response = self._request_get(
            url=url,
            headers=GrowwAPI._build_headers(self.token),
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_ltp(
        self,
        exchange_trading_symbols: Tuple[str],
        segment: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Fetch the LTP data for a list of instruments.

        Args:

            exchange_trading_symbol (str): A list of exchange_trading_symbols to fetch the ltp for. Example: "NSE_RELIANCE, NSE_INFY" or  ("NSE_RELIANCE", "NSE_INFY")
            segment (Segment): The segment to fetch the data from.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The LTP data.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/live-data/ltp"
        params = {"segment": segment, "exchange_symbols": exchange_trading_symbols}
        response = self._request_get(
            url=url,
            headers=GrowwAPI._build_headers(self.token),
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_ohlc(
        self,
        exchange_trading_symbols: Tuple[str],
        segment: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Fetch the OHLC data for a list of instruments.

        Args:
            exchange_trading_symbol (str): A list of exchange_trading_symbols to fetch the ohlc for. Example: "NSE:RELIANCE, NSE:INFY" or  ("NSE:RELIANCE", "NSE:INFY")
            segment (str): The segment to fetch the data from.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The OHLC data.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/live-data/ohlc"
        params = {"segment": segment, "exchange_symbols": exchange_trading_symbols}
        response = self._request_get(
            url=url,
            headers=GrowwAPI._build_headers(self.token),
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_greeks(
        self,
        exchange: str,
        underlying: str,
        trading_symbol: str,
        expiry: str
    ) -> dict:
        """
        Fetch the Greeks data for an option instrument.

        Args:
            exchange (str): The exchange to fetch the data from.
            underlying (str): The underlying symbol of the option.
            trading_symbol (str): The trading symbol of the option.
            expiry (str): The expiry date of the option in yyyy-MM-dd format.
        Returns:
            dict: The Greeks data.
        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/live-data/greeks/exchange/{exchange}/underlying/{underlying}/trading_symbol/{trading_symbol}/expiry/{expiry}"
        response = self._request_get(
            url=url,
            headers=GrowwAPI._build_headers(self.token),
        )
        return self._parse_response(response)

    def get_option_chain(
        self,
        exchange: str,
        underlying: str,
        expiry_date: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Fetch the option chain data for FNO (Futures and Options) contracts.

        Args:
            exchange (str): The exchange to fetch the data from.
            underlying (str): The underlying symbol for the contract such as NIFTY, BANKNIFTY, RELIANCE etc.
            expiry_date (str): Expiry date of the contract in YYYY-MM-DD format.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).
        Returns:
            dict: The option chain data including Greeks for all strikes.
        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/option-chain/exchange/{exchange}/underlying/{underlying}"
        params = {
            "expiry_date": expiry_date,
        }        
        response = self._request_get(
            url=url,
            headers=GrowwAPI._build_headers(self.token),
            params=params if params else None,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_order_detail(
        self,
        segment: str,
        groww_order_id: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get the details of an order.

        Args:
            segment (str): The segment of the order.
            groww_order_id (str): The Groww order ID.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The order details response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url: str = self.domain + "/order/detail/" + groww_order_id
        headers = GrowwAPI._build_headers(self.token)
        params = {"segment": segment}

        response = self._request_get(
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_order_list(
        self,
        page: Optional[int] = 0,
        page_size: Optional[int] = 25,
        segment: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get a list of orders.

        Args:
            page (Optonal[int]): The page number for the orders. Defaults to 0.
            page_size (Optional[int]): The number of orders per page. Defaults to 25.
            segment (Optional[str]): The segment of the orders.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The list of orders response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/order/list"

        headers = GrowwAPI._build_headers(self.token)
        params = {"segment": segment, "page": page} if segment else {}

        response = self._request_get(
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_order_status(
        self,
        segment: str,
        groww_order_id: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get the status of an order.

        Args:
            segment (str): The segment of the order.
            groww_order_id (str): The Groww order ID.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The order status response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/order/status/" + groww_order_id
        headers = GrowwAPI._build_headers(self.token)
        params = {"segment": segment}

        response = self._request_get(
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_order_status_by_reference(
        self,
        segment: str,
        order_reference_id: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get the status of an order by reference ID.

        Args:
            segment (str): The segment of the order.
            order_reference_id (str): The reference ID of the order.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The order status response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/order/status/reference/{order_reference_id}"
        headers = GrowwAPI._build_headers(self.token)
        params = {"segment": segment}

        response = self._request_get(
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_position_for_trading_symbol(
        self,
        trading_symbol: str,
        segment: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get the positions for a symbol.

        Args:
            trading_symbol (str): The trading symbol to get the positions for.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).
            segment (str): The segment of the trading_symbol.

        Returns:
            dict: The positions response for the symbol.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/positions/trading-symbol"
        response = self._request_get(
            url=url,
            headers=GrowwAPI._build_headers(self.token),
            params={"trading_symbol": trading_symbol, "segment": segment},
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_positions_for_user(
        self,
        segment: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get the positions for the user for all the symbols they have positions in.

        Args:
            segment (str): The segment of the positions.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The user's positions response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/positions/user"
        response = self._request_get(
            url=url,
            params={"segment": segment},
            headers=GrowwAPI._build_headers(self.token),
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_trade_list_for_order(
        self,
        groww_order_id: str,
        segment: str,
        page: Optional[int] = 0,
        page_size: Optional[int] = 25,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get the list of trades for a specific order.

        Args:
            groww_order_id (str): The Groww order ID.
            segment (str): The segment of the order.
            page (Optional[int]): The page number for the trades. Defaults to 0.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The list of trades response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/order/trades/" + groww_order_id
        headers = GrowwAPI._build_headers(self.token)
        params = {"segment": segment, "page": page, "page_size": page_size}

        response = self._request_get(
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
        )

        parsed_response = self._parse_response(response)
        return parsed_response

    def get_available_margin_details(self, timeout: Optional[int] = None) -> dict:
        """
        Get the available margin details for the user.

        Args:
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The user's margin details response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/margins/detail/user"
        response = self._request_get(
            url=url, headers=GrowwAPI._build_headers(self.token), timeout=timeout
        )
        return self._parse_response(response)

    def get_all_instruments(self) -> DataFrame:
        """
        Get a dataframe containing all the instruments.
        :return: DataFrame
        """
        return self._load_instruments()

    def get_instrument_by_exchange_and_trading_symbol(
        self, exchange: str, trading_symbol: str
    ) -> dict:
        """
        Get the instrument details for a trading symbol on an exchange.
        :param exchange:
        :param trading_symbol:
        :return: dict
        """
        self._load_instruments()
        if self.instruments is None:
            raise InstrumentNotFoundException()

        df = self.instruments.loc[
            (self.instruments["exchange"] == exchange)
            & (self.instruments["trading_symbol"] == trading_symbol)
        ]
        if df.empty:
            raise InstrumentNotFoundException()
        return df.iloc[0].to_dict()

    def get_instrument_by_groww_symbol(self, groww_symbol: str) -> dict:
        """
        Get the instrument details for the groww_symbol.
        :param groww_symbol:
        :return: dict
        """
        self._load_instruments()
        if self.instruments is None:
            raise InstrumentNotFoundException()

        df = self.instruments.loc[(self.instruments["groww_symbol"] == groww_symbol)]
        if df.empty:
            raise InstrumentNotFoundException()
        return df.iloc[0].to_dict()

    def get_instrument_by_exchange_token(self, exchange_token: str) -> dict:
        """
        Get the instrument details for the exchange_token.
        :param exchange_token:
        :return:
        """
        self._load_instruments()
        if self.instruments is None:
            raise InstrumentNotFoundException()

        df = self.instruments.loc[
            (self.instruments["exchange_token"] == exchange_token)
        ]
        if df.empty:
            raise InstrumentNotFoundException()
        return df.iloc[0].to_dict()

    def get_historical_candle_data(
        self,
        trading_symbol: str,
        exchange: str,
        segment: str,
        start_time: str,
        end_time: str,
        interval_in_minutes: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get the historical data for an instrument.

        Args:
            trading_symbol (str): The symbol to fetch the data for.
            exchange (str): The exchange to fetch the data from.
            segment (str): The segment to fetch the data from.
            start_time (str): The start time in epoch milliseconds or yyyy-MM-dd HH:mm:ss format.
            end_time (str): The end time in epoch milliseconds or yyyy-MM-dd HH:mm:ss format.
            interval_in_minutes (Optional[int]): The interval in minutes.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The historical data.

        Raises:
            GrowwAPIException: If the request fails.
        """
        warnings.warn(
            "`get_historical_candle_data` is deprecated and will be removed in future releases. Please use `get_historical_candles` method instead. See https://groww.in/trade-api/docs/python-sdk/backtesting#get-historical-candle-data for more details.",
            DeprecationWarning,
            stacklevel=2,
        )
        url = f"{self.domain}/historical/candle/range"
        params = {
            "exchange": exchange,
            "segment": segment,
            "trading_symbol": trading_symbol,
            "start_time": start_time,
            "end_time": end_time,
            "interval_in_minutes": interval_in_minutes,
        }
        response = self._request_get(
            url=url,
            headers=self._build_headers(self.token),
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_historical_candles(
        self,
        exchange: str,
        segment: str,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        candle_interval: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get bulk historical candle data for an instrument with V2 response format.

        Args:
            exchange (str): The exchange to fetch the data from.
            segment (str): The segment to fetch the data from.
            groww_symbol (str): The Groww symbol to fetch the data for.
            start_time (str): The start time in yyyy-MM-dd HH:mm:ss format.
            end_time (str): The end time in yyyy-MM-dd HH:mm:ss format.
            candle_interval (str): The candle interval (e.g., "1minute", "5minute", "1day").
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The bulk historical candle data in V2 format.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/historical/candles"
        params = {
            "exchange": exchange,
            "segment": segment,
            "groww_symbol": groww_symbol,
            "start_time": start_time,
            "end_time": end_time,
            "candle_interval": candle_interval,
        }
        response = self._request_get(
            url=url,
            headers=self._build_headers(self.token),
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_expiries(
        self,
        exchange: str,
        underlying_symbol: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get expiry dates for a given exchange, symbol, year and optionally month.

        Args:
            exchange (str): The exchange to fetch expiries from.
            underlying_symbol (str): The underlying symbol to fetch expiries for.
            year (Optional[int]): The year to fetch expiries for (must be between 2000 and 5000). If not provided, current year is used.
            month (Optional[int]): The month to fetch expiries for (1-12). If not provided, gets all expiries for the year.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The list of expiry dates.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/historical/expiries"
        params = {
            "exchange": exchange,
            "underlying_symbol": underlying_symbol,
        }
        if year is not None:
            params["year"] = str(year)
        if month is not None:
            params["month"] = str(month)

        response = self._request_get(
            url=url,
            headers=self._build_headers(self.token),
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_contracts(
        self,
        exchange: str,
        underlying_symbol: str,
        expiry_date: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get contracts for a given exchange, symbol and expiry date.

        Args:
            exchange (str): The exchange to fetch contracts from.
            underlying_symbol (str): The underlying symbol to fetch contracts for (1-20 characters).
            expiry_date (str): The expiry date to fetch contracts for (YYYY-MM-DD format).
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The list of contracts.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/historical/contracts"
        params = {
            "exchange": exchange,
            "underlying_symbol": underlying_symbol,
            "expiry_date": expiry_date,
        }
        response = self._request_get(
            url=url,
            headers=self._build_headers(self.token),
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_order_margin_details(
        self,
        segment: str,
        orders: list[dict],
        timeout: Optional[int] = None,
    ) -> dict:

        url = f"{self.domain}/margins/detail/orders"
        params = {"segment": segment}
        request_body = [
            {
                "trading_symbol": order["trading_symbol"],
                "transaction_type": order["transaction_type"],
                "quantity": order["quantity"],
                "price": order["price"],
                "order_type": order["order_type"],
                "product": order["product"],
                "exchange": order["exchange"],
            }
            for order in orders
        ]

        response = self._request_post(
            url=url,
            headers=self._build_headers(self.token),
            json=request_body,
            params=params,
            timeout=timeout,
        )

        return self._parse_response(response)

    def create_smart_order(
        self,
        smart_order_type: str,
        segment: str,
        trading_symbol: str,
        quantity: int,
        product_type: str,
        exchange: str,
        duration: str,
        reference_id: Optional[str] = None,
        trigger_price: Optional[str] = None,
        trigger_direction: Optional[str] = None,
        order: Optional[dict] = None,
        child_legs: Optional[dict] = None,
        net_position_quantity: Optional[int] = None,
        target: Optional[dict] = None,
        stop_loss: Optional[dict] = None,
        transaction_type: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Create a smart order (GTT or OCO).

        For GTT orders, provide: trigger_price, trigger_direction, order (and optionally child_legs).
        For OCO orders, provide: net_position_quantity, target, stop_loss, transaction_type.

        Args:
            smart_order_type (str): Smart order type (GTT or OCO).
            segment (str): Market segment (e.g., CASH, FNO).
            trading_symbol (str): Trading symbol of the instrument.
            quantity (int): Quantity for the order.
            product_type (str): Product type (e.g., CNC, MIS).
            exchange (str): Exchange (e.g., NSE, BSE).
            duration (str): Validity (e.g., DAY, GTC).
            reference_id (Optional[str]): Unique reference ID to track the smart order. Defaults to a random 8-digit number.
            trigger_price (Optional[str]): GTT: Trigger price as a decimal string.
            trigger_direction (Optional[str]): GTT: Direction to monitor (UP or DOWN).
            order (Optional[dict]): GTT: Order details with keys: order_type, price (optional), transaction_type.
            child_legs (Optional[dict]): GTT: Optional child legs for bracket orders.
            net_position_quantity (Optional[int]): OCO: Current net position in this symbol.
            target (Optional[dict]): OCO: Target leg with keys: trigger_price, order_type, price (optional).
            stop_loss (Optional[dict]): OCO: Stop-loss leg with keys: trigger_price, order_type, price (optional).
            transaction_type (Optional[str]): OCO: Transaction type (BUY or SELL).
            timeout (Optional[int]): Request timeout in seconds.

        Returns:
            dict: The created smart order details.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/order-advance/create"

        reference_id = (
            reference_id
            if reference_id is not None
            else str(random.randint(10000000, 99999999))
        )

        headers = GrowwAPI._build_headers(self.token)
        request_body: dict[str, Any] = {
            "smart_order_type": smart_order_type,
            "reference_id": reference_id,
            "segment": segment,
            "trading_symbol": trading_symbol,
            "quantity": quantity,
            "product_type": product_type,
            "exchange": exchange,
            "duration": duration,
        }

        # GTT-specific fields
        if trigger_price is not None:
            request_body["trigger_price"] = trigger_price
        if trigger_direction is not None:
            request_body["trigger_direction"] = trigger_direction
        if order is not None:
            request_body["order"] = order
        if child_legs is not None:
            request_body["child_legs"] = child_legs

        # OCO-specific fields
        if net_position_quantity is not None:
            request_body["net_position_quantity"] = net_position_quantity
        if target is not None:
            request_body["target"] = target
        if stop_loss is not None:
            request_body["stop_loss"] = stop_loss
        if transaction_type is not None:
            request_body["transaction_type"] = transaction_type

        response = self._request_post(
            url=url,
            json=request_body,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def modify_smart_order(
        self,
        smart_order_id: str,
        smart_order_type: str,
        segment: str,
        quantity: Optional[int] = None,
        duration: Optional[str] = None,
        trigger_price: Optional[str] = None,
        trigger_direction: Optional[str] = None,
        order: Optional[dict] = None,
        child_legs: Optional[dict] = None,
        product_type: Optional[str] = None,
        target: Optional[dict] = None,
        stop_loss: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Modify a smart order (GTT or OCO).

        For GTT orders, you can modify: quantity, trigger_price, trigger_direction, order, duration, child_legs.
        For OCO orders, you can modify: quantity, product_type, target, stop_loss, duration.

        Args:
            smart_order_id (str): The smart order identifier (e.g., gtt_91a7f4, oco_a12bc3).
            smart_order_type (str): Smart order type (GTT or OCO).
            segment (str): Market segment (e.g., CASH, FNO).
            quantity (Optional[int]): Updated quantity.
            duration (Optional[str]): Updated validity.
            trigger_price (Optional[str]): GTT: Updated trigger price.
            trigger_direction (Optional[str]): GTT: Updated trigger direction.
            order (Optional[dict]): GTT: Updated order details with keys: order_type, price, transaction_type.
            child_legs (Optional[dict]): GTT: Updated child legs for bracket orders.
            product_type (Optional[str]): OCO: Updated product type.
            target (Optional[dict]): OCO: Updated target leg with keys: trigger_price, order_type, price.
            stop_loss (Optional[dict]): OCO: Updated stop-loss leg with keys: trigger_price, order_type, price.
            timeout (Optional[int]): Request timeout in seconds.

        Returns:
            dict: The modified smart order details.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/order-advance/modify/{smart_order_id}"
        headers = GrowwAPI._build_headers(self.token)
        request_body: dict[str, Any] = {
            "smart_order_type": smart_order_type,
            "segment": segment,
        }

        # Common modifiable fields
        if quantity is not None:
            request_body["quantity"] = quantity
        if duration is not None:
            request_body["duration"] = duration

        # GTT-specific modifiable fields
        if trigger_price is not None:
            request_body["trigger_price"] = trigger_price
        if trigger_direction is not None:
            request_body["trigger_direction"] = trigger_direction
        if order is not None:
            request_body["order"] = order
        if child_legs is not None:
            request_body["child_legs"] = child_legs

        # OCO-specific modifiable fields
        if product_type is not None:
            request_body["product_type"] = product_type
        if target is not None:
            request_body["target"] = target
        if stop_loss is not None:
            request_body["stop_loss"] = stop_loss

        response = self._request_put(
            url=url,
            json=request_body,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def cancel_smart_order(
        self,
        segment: str,
        smart_order_type: str,
        smart_order_id: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Cancel a smart order.

        Args:
            segment (str): Market segment (e.g., CASH, FNO).
            smart_order_type (str): Smart order type (GTT or OCO).
            smart_order_id (str): The smart order identifier.
            timeout (Optional[int]): Request timeout in seconds.

        Returns:
            dict: The cancelled smart order details.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/order-advance/cancel/{segment}/{smart_order_type}/{smart_order_id}"
        headers = GrowwAPI._build_headers(self.token)

        response = self._request_post(
            url=url,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_smart_order(
        self,
        segment: str,
        smart_order_type: str,
        smart_order_id: str,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Get a smart order by internal ID.

        Args:
            segment (str): Market segment (e.g., CASH, FNO).
            smart_order_type (str): Smart order type (GTT or OCO).
            smart_order_id (str): The smart order identifier.
            timeout (Optional[int]): Request timeout in seconds.

        Returns:
            dict: The smart order details.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/order-advance/status/{segment}/{smart_order_type}/internal/{smart_order_id}"
        headers = GrowwAPI._build_headers(self.token)

        response = self._request_get(
            url=url,
            headers=headers,
            timeout=timeout,
        )
        return self._parse_response(response)

    def get_smart_order_list(
        self,
        smart_order_type: Optional[str] = None,
        segment: Optional[str] = None,
        status: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        start_date_time: Optional[str] = None,
        end_date_time: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        List smart orders with filters.

        Args:
            smart_order_type (Optional[str]): Smart order type (GTT or OCO).
            segment (Optional[str]): Market segment (e.g., CASH, FNO).
            status (Optional[str]): Status filter (e.g., ACTIVE, CANCELLED).
            page (Optional[int]): Page number (min: 0, max: 500).
            page_size (Optional[int]): Items per page (min: 1, max: 50).
            start_date_time (Optional[str]): Inclusive start time (ISO 8601 format).
            end_date_time (Optional[str]): Inclusive end time (ISO 8601 format).
            timeout (Optional[int]): Request timeout in seconds.

        Returns:
            dict: List of smart orders.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = f"{self.domain}/order-advance/list"
        headers = GrowwAPI._build_headers(self.token)
        params = {}
        if smart_order_type is not None:
            params["smart_order_type"] = smart_order_type
        if segment is not None:
            params["segment"] = segment
        if status is not None:
            params["status"] = status
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        if start_date_time is not None:
            params["start_date_time"] = start_date_time
        if end_date_time is not None:
            params["end_date_time"] = end_date_time

        response = self._request_get(
            url=url,
            headers=headers,
            params=params,
            timeout=timeout,
        )
        return self._parse_response(response)
    
    def get_user_profile(self, timeout: Optional[int] = None) -> dict:
        """
        Get the user profile details.

        Args:
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).

        Returns:
            dict: The user profile details.

        Raises:
            GrowwAPIException: If the request fails.
        """
        url = self.domain + "/user/detail"
        response = self._request_get(
            url=url, headers=GrowwAPI._build_headers(self.token), timeout=timeout
        )
        return self._parse_response(response)

    def generate_socket_token(self, key_pair) -> dict:
        headers = self._build_headers(self.token)
        request_body = {
            "socketKey": key_pair.public_key.decode("utf-8"),
        }
        response = self._request_post(
            url=self._GROWW_GENERATE_SOCKET_TOKEN_URL,
            json=request_body,
            headers=headers,
        )
        return self._parse_response(response)

    @staticmethod
    def _build_headers(key_or_token: str) -> dict:
        """
        Build the headers for the API request.

        Returns:
            dict: The headers for the API request.
        """
        return {
            "x-request-id": str(uuid.uuid4()),
            "Authorization": "Bearer " + key_or_token,
            "Content-Type": "application/json",
            "x-client-id": "growwapi",
            "x-client-platform": "growwapi-python-client",
            "x-client-platform-version": "1.5.0",
            "x-api-version": "1.0",
        }

    def _request_get(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Send a GET request to the API.

        Args:
            url (str): The URL to send the request to.
            params (Optional[dict]): The parameters to send with the request.
            headers (Optional[dict]): The headers to send with the request.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).
            **kwargs: Optional arguments that ``request`` takes.

        Returns:
            requests.Response: The response from the API.

        Raises:
            GrowwAPIException: If the request fails.
        """
        try:
            return requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        except requests.Timeout as e:
            raise GrowwAPITimeoutException() from e

    def _request_post(
        self,
        url: str,
        json: Any = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Send a POST request to the API.

        Args:
            url (str): The URL to send the request to.
            json (Any): The JSON data to send with the request.
            headers (Optional[dict]): The headers to send with the request.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).
            **kwargs: Optional arguments that ``request`` takes.

        Returns:
            requests.Response: The response from the API.

        Raises:
            GrowwAPIException: If the request fails.
        """
        try:
            return requests.post(
                url=url,
                json=json,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        except requests.Timeout as e:
            raise GrowwAPITimeoutException() from e
    
    def _request_put(
        self,
        url: str,
        json: Any = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Send a PUT request to the API.

        Args:
            url (str): The URL to send the request to.
            json (Any): The JSON data to send with the request.
            headers (Optional[dict]): The headers to send with the request.
            timeout (Optional[int]): The timeout for the request in seconds. Defaults to None (infinite).
            **kwargs: Optional arguments that ``request`` takes.

        Returns:
            requests.Response: The response from the API.

        Raises:
            GrowwAPIException: If the request fails.
        """
        try:
            return requests.put(
                url=url,
                json=json,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
        except requests.Timeout as e:
            raise GrowwAPITimeoutException() from e

    def _parse_response(self, response: requests.Response) -> dict:
        """
        Parse the response from the API.

        Args:
            response (requests.Response): The response from the API.

        Returns:
            BaseGrowwResponse: The parsed response.

        Raises:
            GrowwAPIException: If the request fails.
        """
        response_map = response.json()
        if response_map.get("status") == "FAILURE":
            error = response_map["error"]
            raise GrowwAPIException(code=error["code"], msg=error["message"])
        if response.status_code in self._ERROR_MAP:
            raise self._ERROR_MAP[response.status_code]()
        if not response.ok:
            raise GrowwAPIException(
                code=str(response.status_code),
                msg="The request to the Groww API failed.",
            )
        return dict(
            response_map["payload"] if "payload" in response_map else response_map
        )

    @staticmethod
    def _build_request_data(
        totp: Optional[str] = None, secret: Optional[str] = None
    ) -> dict:
        """
        Builds the request data payload based on authentication method.
        """
        if totp is not None and secret is not None:
            raise ValueError("Either totp or secret should be provided, not both.")
        if totp is None and secret is None:
            raise ValueError("Either totp or secret should be provided.")

        if totp is not None:
            if not totp.strip():
                raise ValueError("TOTP cannot be empty")

            return {"key_type": "totp", "totp": totp.strip()}

        # secret is not None
        if not secret or not secret.strip():
            raise ValueError("Secret cannot be empty")

        timestamp = int(time.time())
        checksum = GrowwAPI._generate_checksum(secret, str(timestamp))
        return {"key_type": "approval", "checksum": checksum, "timestamp": timestamp}

    @staticmethod
    def get_access_token(
        api_key: str,
        totp: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> dict:
        """
        Args:
            api_key (str): Bearer token or API key for the Authorization header.
            totp (str): If TOTP api key is provided. The TOTP code as a string.
            secret (str): If approval api key is provided. The secret value as a string.
        Returns:
            dict: The JSON response from the API.
        Raises:
            requests.HTTPError: If the request fails.
        """
        import requests

        url = "https://api.groww.in/v1/token/api/access"
        headers = GrowwAPI._build_headers(api_key)
        data = GrowwAPI._build_request_data(totp=totp, secret=secret)
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 400:
            try:
                msg = (
                    response.json()
                    .get("error", {})
                    .get("displayMessage", "Bad Request")
                )
            except Exception:
                msg = "Bad Request"
            raise GrowwAPIException(
                code=str(response.status_code), msg=f"Groww API Error 400: {msg}"
            )
        if response.status_code in GrowwAPI._ERROR_MAP:
            raise GrowwAPI._ERROR_MAP[response.status_code]()
        if not response.ok:
            raise GrowwAPIException(
                code=str(response.status_code),
                msg="The request to the Groww API failed.",
            )
        return response.json()["token"]

    @staticmethod
    def _generate_checksum(data: str, salt: str) -> str:
        """
        Generates a SHA-256 checksum for the given data and salt.
        :param secret: The api secret value
        :return: Hexadecimal SHA-256 checksum
        """
        input_str = data + salt
        sha256 = hashlib.sha256()
        sha256.update(input_str.encode("utf-8"))
        return sha256.hexdigest()
