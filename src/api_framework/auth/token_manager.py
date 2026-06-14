from __future__ import annotations
import logging, threading, time
from dataclasses import dataclass
import httpx
from config.settings import Settings

logger = logging.getLogger(__name__)
_EXPIRY_BUFFER_SECONDS = 30

@dataclass
class _TokenCache:
    access_token: str = ""
    expires_at: float = 0.0

class TokenManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache = _TokenCache()
        self._lock = threading.Lock()

    def get_valid_token(self) -> str:
        if self._is_token_valid():
            return self._cache.access_token
        with self._lock:
            if self._is_token_valid():
                return self._cache.access_token
            self._refresh_token()
        return self._cache.access_token

    def invalidate(self) -> None:
        with self._lock:
            self._cache = _TokenCache()

    def _is_token_valid(self) -> bool:
        return (
            bool(self._cache.access_token)
            and time.time() < self._cache.expires_at - _EXPIRY_BUFFER_SECONDS
        )

    def _refresh_token(self) -> None:
        logger.debug("Requesting token for username=%s", self._settings.username)
        with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
            response = client.post(
                self._settings.token_url,
                data={
                    "grant_type": "password",
                    "client_id":  self._settings.oauth_client_id,
                    "username":   self._settings.username,
                    "password":   self._settings.password,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept":       "application/json",
                },
            )
        response.raise_for_status()
        data = response.json()
        self._cache.access_token = data["access_token"]
        expires_in = data.get("expires_in", 300)
        self._cache.expires_at = time.time() + expires_in
        logger.info("Token obtained. Expires in %ds", expires_in)
