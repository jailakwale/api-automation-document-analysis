# Base HTTP client wrapping httpx.Client

from __future__ import annotations

import logging

import httpx

from api_framework.auth.token_manager import TokenManager
from config.settings import Settings

logger = logging.getLogger(__name__)


class BearerAuth(httpx.Auth):
    """
    httpx Auth implementation that injects a Bearer token on every request,
    transparently refreshing via TokenManager when expired.
    """

    def __init__(self, token_manager: TokenManager) -> None:
        self._token_manager = token_manager

    def auth_flow(self, request: httpx.Request):  # type: ignore[override]
        token = self._token_manager.get_valid_token()
        request.headers["Authorization"] = f"Bearer {token}"
        response = yield request

        # If we get 401, invalidate the cached token and retry once.
        # This handles the edge case where the token expires between the
        # cache-validity check and the actual HTTP call.
        if response.status_code == 401:
            logger.warning("Received 401; invalidating token cache and retrying.")
            self._token_manager.invalidate()
            token = self._token_manager.get_valid_token()
            request.headers["Authorization"] = f"Bearer {token}"
            yield request


class BaseAPIClient:
    """
    Thin httpx wrapper shared by all concrete API clients.

    Responsibilities:
      - Maintain a single httpx.Client session for connection reuse.
      - Attach BearerAuth to every outgoing request.
      - Log all requests/responses at DEBUG level.
      - Normalise HTTP errors via raise_for_status().
    """

    def __init__(self, settings: Settings, token_manager: TokenManager) -> None:
        self._settings = settings
        self._token_manager = token_manager
        self._client = httpx.Client(
            base_url=settings.base_url,
            auth=BearerAuth(token_manager),
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            # Enable HTTP/2 if the server supports it (transparent upgrade)
            http2=False,  # set True if httpx[http2] is installed
        )

    # ── HTTP verbs ────────────────────────────────────────────────────────────

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> httpx.Response:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self._request("DELETE", path, **kwargs)

    # ── Core request handler ──────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        logger.debug("--> %s %s | params=%s", method, path, kwargs.get("params"))
        response = self._client.request(method, path, **kwargs)
        logger.debug(
            "<-- %s %s | status=%s | body_len=%s",
            method,
            path,
            response.status_code,
            len(response.content),
        )
        return response

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Release the underlying httpx connection pool."""
        self._client.close()

    def __enter__(self) -> "BaseAPIClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
