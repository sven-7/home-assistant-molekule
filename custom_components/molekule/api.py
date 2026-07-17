import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor
from warrant import Cognito
from .const import API_CLIENT_ID, API_POOL_ID, API_URL, API_REGION
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

_LOGGER = logging.getLogger(__name__)

def clean_none_values(d):
    """Recursively remove all None values from dictionaries and lists, and convert to empty string"""
    if isinstance(d, dict):
        return {k: clean_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [clean_none_values(v) for v in d if v is not None]
    elif d is None:
        return ""
    else:
        return d

class MolekuleApiError(Exception):
    """Base exception for Molekule API errors."""
    pass

class AuthenticationError(MolekuleApiError):
    """Authentication related errors."""
    pass

class ApiConnectionError(MolekuleApiError):
    """Connection related errors."""
    pass

class MolekuleApi:
    """Molekule API client with improved error handling and session management."""
    
    def __init__(self, email: str, password: str):
        """Initialize the API client."""
        self.email = email
        self.password = password
        self.cognito: Optional[Cognito] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self.token: Optional[str] = None
        self.token_expiration: Optional[datetime] = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._session_lock = asyncio.Lock()
        self._auth_lock = asyncio.Lock()
        self._request_timeout = aiohttp.ClientTimeout(total=30)
        self._retry_attempts = 3
        self._retry_delay = 1  # seconds

    @property
    async def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with locking."""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=self._request_timeout,
                    headers={
                        "x-api-version": "1.0",
                        "Content-Type": "application/json",
                    }
                )
            return self._session

    async def authenticate(self) -> None:
        """Authenticate with the Molekule API."""
        async with self._auth_lock:
            try:
                loop = asyncio.get_running_loop()
                self.cognito = await loop.run_in_executor(
                    self.executor, self._create_and_authenticate_cognito
                )
                self.token = self.cognito.id_token
                self.token_expiration = datetime.now() + timedelta(hours=1)
                _LOGGER.debug("Successfully authenticated with Molekule API")
            except Exception as err:
                _LOGGER.error("Authentication failed: %s", str(err))
                raise AuthenticationError(f"Failed to authenticate: {err}") from err

    def _create_and_authenticate_cognito(self) -> Cognito:
        """Create and authenticate Cognito client in executor."""
        try:
            cognito = Cognito(
                API_POOL_ID,
                API_CLIENT_ID,
                username=self.email,
                user_pool_region=API_REGION
            )
            cognito.authenticate(password=self.password)
            return cognito
        except Exception as err:
            _LOGGER.error("Cognito authentication failed: %s", str(err))
            raise

    async def refresh_token(self) -> None:
        """Refresh the authentication token."""
        async with self._auth_lock:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    self.executor, self.cognito.renew_access_token
                )
                self.token = self.cognito.id_token
                self.token_expiration = datetime.now() + timedelta(hours=1)
                _LOGGER.debug("Successfully refreshed Molekule API token")
            except Exception as err:
                _LOGGER.warning("Token refresh failed, re-authenticating: %s", str(err))
                await self.authenticate()

    async def ensure_token_valid(self) -> None:
        """Ensure the authentication token is valid."""
        if not self.token or not self.token_expiration:
            await self.authenticate()
        elif datetime.now() >= self.token_expiration - timedelta(minutes=5):
            await self.refresh_token()

    async def _make_request(
        self, method: str, url: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Make an API request with retry logic."""
        await self.ensure_token_valid()
        client_session = await self.session
        headers = {"Authorization": self.token, **client_session.headers}
        
        for attempt in range(self._retry_attempts):
            try:
                async with client_session.request(
                    method, url, headers=headers, **kwargs
                ) as response:
                    if response.status == 401:
                        await self.authenticate()
                        headers["Authorization"] = self.token
                        continue
                    
                    if response.status == 204:
                        return None
                        
                    if response.status != 200:
                        _LOGGER.error(
                            "API request failed with status %s: %s",
                            response.status,
                            await response.text()
                        )
                        return None
                        
                    return await response.json()
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.error("Request failed (attempt %d/%d): %s",
                            attempt + 1, self._retry_attempts, str(err))
                if attempt + 1 < self._retry_attempts:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    await self.close()  # Force session recreation
                    client_session = await self.session
                else:
                    raise ApiConnectionError(f"Failed after {self._retry_attempts} attempts: {err}")
        
        return None

    async def get_devices(self) -> Optional[Dict[str, Any]]:
        """Get all devices associated with the account."""
        try:
            data = await self._make_request("GET", API_URL)
            return clean_none_values(data) if data else None
        except Exception as err:
            _LOGGER.error("Failed to get devices: %s", str(err))
            return None

    async def get_sensor_data(self, serial: str) -> Optional[Dict[str, Any]]:
        """Get sensor data for a specific device."""
        end_time = int(time.time() * 1000)
        start_time = end_time - 3600000  # 1 hour ago
        
        url = (f"{API_URL}{serial}/sensordata"
               f"?aggregation=false&fromDate={start_time}"
               f"&resolution=5&toDate={end_time}")
        
        try:
            data = await self._make_request("GET", url)
            return self._process_sensor_data(data) if data else None
        except Exception as err:
            _LOGGER.error("Failed to get sensor data for %s: %s", serial, str(err))
            return None

    def _process_sensor_data(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Optional[float]]]:
        """Process raw sensor data into a cleaned format."""
        if not data or 'sensorData' not in data:
            return None

        processed_data = {
            "PM2_5": None,
            "PM10": None,
            "RH": None,
            "TVOC": None,
            "CO2": None,
        }

        try:
            for pollutant in data['sensorData']:
                pollutant_type = pollutant['type']
                if pollutant_type in processed_data:
                    values = pollutant.get('sensorDataValue', [])
                    valid_values = [v['v'] for v in values if v['v'] != -1]
                    if valid_values:
                        processed_data[pollutant_type] = valid_values[-1]
            
            return processed_data
        except Exception as err:
            _LOGGER.error("Error processing sensor data: %s", str(err))
            return None

    async def set_power_status(self, serial: str, status: bool) -> bool:
        """Set device power status."""
        url = f"{API_URL}{serial}/actions/set-power-status"
        try:
            await self._make_request(
                "POST",
                url,
                json={"status": "on" if status else "off"}
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set power status: %s", str(err))
            return False

    async def set_fan_speed(self, serial: str, speed: int) -> bool:
        """Set device fan speed."""
        url = f"{API_URL}{serial}/actions/set-fan-speed"
        try:
            await self._make_request(
                "POST",
                url,
                json={"fanSpeed": speed}
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set fan speed: %s", str(err))
            return False

    async def set_mode_action(
        self, serial: str, action: str, body: dict | None = None
    ) -> bool:
        """Invoke a device-mode action with its API request body."""
        url = f"{API_URL}{serial}/actions/{action}"
        try:
            await self._make_request("POST", url, json=body or {})
            return True
        except Exception as err:
            _LOGGER.error("Failed action %s: %s", action, err)
            return False

    async def _post_action(
        self, url: str, body: dict | None = None
    ) -> bool:
        """POST a device action. Return True only for HTTP 200/204."""
        await self.ensure_token_valid()
        client_session = await self.session
        headers = {
            "Authorization": self.token,
            "x-api-version": "1.0",
            "Content-Type": "application/json",
        }
        request_kwargs: Dict[str, Any] = {"headers": headers}
        if body is not None:
            request_kwargs["json"] = body
        else:
            # Mini Auto Protect (homebridge AutoFunctionality=1) expects an empty body.
            request_kwargs["data"] = b""

        for attempt in range(self._retry_attempts):
            try:
                async with client_session.request(
                    "POST", url, **request_kwargs
                ) as response:
                    if response.status == 401:
                        await self.authenticate()
                        headers["Authorization"] = self.token
                        request_kwargs["headers"] = headers
                        continue
                    if response.status in (200, 204):
                        return True
                    text = await response.text()
                    _LOGGER.error(
                        "Action POST %s failed with status %s: %s",
                        url,
                        response.status,
                        text,
                    )
                    return False
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.error(
                    "Action POST failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._retry_attempts,
                    err,
                )
                if attempt + 1 < self._retry_attempts:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    await self.close()
                    client_session = await self.session
                else:
                    return False
        return False

    async def set_auto_mode(
        self, serial: str, auto: bool, silent: bool = False
    ) -> bool:
        """Enable or leave Auto Protect / smart mode.

        Mini Plus accepts ``enable-smart-mode`` with an empty body. Air Pro
        may want ``{"silent": "0"|"1"}``. Fall back through known variants
        and only report success on HTTP 200/204.
        """
        if auto:
            enable_url = f"{API_URL}{serial}/actions/enable-smart-mode"
            if silent:
                if await self._post_action(enable_url, {"silent": "1"}):
                    return True
            else:
                # Empty body first — required for Air Mini Plus.
                if await self._post_action(enable_url, None):
                    return True
                if await self._post_action(enable_url, {"silent": "0"}):
                    return True
            # jpcaldwell-style fallback
            if await self._post_action(f"{API_URL}{serial}/actions/smart", None):
                return True
            _LOGGER.error("Failed to enable smart mode for %s", serial)
            return False

        # Leaving auto: prefer /actions/manual, else set an explicit fan speed
        # (homebridge exits auto by posting set-fan-speed).
        if await self._post_action(f"{API_URL}{serial}/actions/manual", None):
            return True
        return await self.set_fan_speed(serial, 1)

    async def get_aqi(self, serial: str) -> Optional[Dict[str, Any]]:
        """Get air quality index for a device."""
        url = f"{API_URL}{serial}/air-quality-index"
        try:
            data = await self._make_request("GET", url)
            return clean_none_values(data) if data else None
        except Exception as err:
            _LOGGER.error("Failed to get AQI: %s", str(err))
            return None

    async def close(self) -> None:
        """Close all connections."""
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
        
        if self.executor:
            self.executor.shutdown(wait=False)
