# High-level IDcheck API client

from __future__ import annotations

import logging
from typing import Any

import httpx

from api_framework.clients.base_client import BaseAPIClient
from api_framework.models.request_models import DocumentCreateRequest, FileCreateRequest
from api_framework.models.response_models import (
    DocumentResponse,
    DocumentSummary,
    FileSummary,
    TaskResponse,
)
from api_framework.auth.token_manager import TokenManager
from config.settings import Settings

logger = logging.getLogger(__name__)


class IDCheckClient(BaseAPIClient):
    """
    Concrete client for the IDcheck CIS REST API.

    All methods accept/return typed models and raise httpx.HTTPStatusError
    on non-2xx responses (caller decides how to handle).
    """

    def __init__(self, settings: Settings, token_manager: TokenManager) -> None:
        super().__init__(settings, token_manager)
        self._realm = settings.realm
        # Base path prefix used by every endpoint
        self._prefix = f"/rest/v1/{self._realm}"

    # ── Health ────────────────────────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """
        GET /rest/health — does not require authentication.
        Useful as a smoke test to verify sandbox reachability.
        """
        resp = self._client.get("/rest/health")
        resp.raise_for_status()
        return resp.json()

    # ── File operations ───────────────────────────────────────────────────────

    def create_file(self, request: FileCreateRequest | None = None) -> FileSummary:
        """
        POST /rest/v1/{realm}/file?synchronous=true

        Creates an empty file container. We use synchronous mode because
        file creation is fast — no analysis is triggered here.
        """
        body = request.model_dump_api() if request else {}
        resp = self.post(
            f"{self._prefix}/file",
            params={"synchronous": "true"},
            json=body,
        )
        resp.raise_for_status()
        return FileSummary.model_validate(resp.json())

    def get_file(self, file_uid: str) -> dict[str, Any]:
        """GET /rest/v1/{realm}/file/{uid}"""
        resp = self.get(f"{self._prefix}/file/{file_uid}")
        resp.raise_for_status()
        return resp.json()

    #  File deletion with sandbox permission handling
    # def delete_file(self, file_uid: str) -> None:
    #     """DELETE /rest/v1/{realm}/file/{uid}?synchronous=true"""
    #     resp = self.delete(
    #         f"{self._prefix}/file/{file_uid}",
    #         params={"synchronous": "true"},
    #     )
    #     resp.raise_for_status()
        
    def delete_file(self, file_uid: str) -> None:
        """
        DELETE /rest/v1/{realm}/file/{uid}

        NOTE: Sandbox may return 403 for file deletion due to account
        permission restrictions. We log and continue — not a test failure.
        """
        resp = self.delete(
            f"{self._prefix}/file/{file_uid}",
            params={"synchronous": "true"},
        )
        if resp.status_code == 403:
            logger.warning(
                "DELETE file/%s returned 403 — sandbox permission restriction. "
                "Skipping cleanup.", file_uid
            )
            return
        resp.raise_for_status()

    # ── Document operations ───────────────────────────────────────────────────

    def create_document(
        self,
        request: DocumentCreateRequest,
        file_uid: str | None = None,
    ) -> DocumentSummary:
        """
        POST /rest/v1/{realm}/document?synchronous=true[&fileUid=...]

        Creates a document with images. Pass file_uid to automatically
        link the document to an existing file.

        We always use synchronous=true here — document creation is fast
        (just storage, no analysis).
        """
        params: dict[str, Any] = {"synchronous": "true"}
        if file_uid:
            params["fileUid"] = file_uid

        resp = self.post(
            f"{self._prefix}/document",
            params=params,
            json=request.model_dump_api(),
        )
        resp.raise_for_status()
        return DocumentSummary.model_validate(resp.json())

    def get_document(self, document_uid: str) -> DocumentResponse:
        """
        GET /rest/v1/{realm}/document/{uid}

        Returns the full document including its latest report.
        Used for polling until analysis is FINAL.
        """
        resp = self.get(f"{self._prefix}/document/{document_uid}")
        resp.raise_for_status()
        return DocumentResponse.model_validate(resp.json())

    def delete_document(self, document_uid: str) -> None:
        """DELETE /rest/v1/{realm}/document/{uid}?synchronous=true"""
        resp = self.delete(
            f"{self._prefix}/document/{document_uid}",
            params={"synchronous": "true"},
        )
        resp.raise_for_status()

    # ── Analysis ──────────────────────────────────────────────────────────────

    def trigger_document_check(self, document_uid: str) -> TaskResponse | dict:
        """
        POST /rest/v1/{realm}/document/{uid}/check (async mode — recommended)

        Kicks off the full analysis pipeline.
        Returns a TaskResponse (202 Accepted) — caller must poll.

        WHY ASYNC?
          The developer guide strongly recommends async for check operations.
          Sync mode would block until analysis completes AND disables manual
          review. We implement polling in PollingHelper instead.
        """
        resp = self.post(
            f"{self._prefix}/document/{document_uid}/check",
            params={"synchronous": "false", "manualAnalysis": "DISABLE"},
        )
        resp.raise_for_status()
        if resp.status_code == 202:
            return TaskResponse.model_validate(resp.json())
        # Synchronous fallback (200) — return raw dict
        return resp.json()

    def trigger_file_check(self, file_uid: str) -> TaskResponse | dict:
        """
        POST /rest/v1/{realm}/file/{uid}/check (async mode)
        """
        resp = self.post(
            f"{self._prefix}/file/{file_uid}/check",
            params={"synchronous": "false", "manualAnalysis": "DISABLE"},
        )
        resp.raise_for_status()
        if resp.status_code == 202:
            return TaskResponse.model_validate(resp.json())
        return resp.json()

    # ── Raw request (used in error-case tests) ────────────────────────────────

    def raw_request(
        self,
        method: str,
        path: str,
        auth: bool = True,
        **kwargs,
    ) -> httpx.Response:
        """
        Send a raw HTTP request bypassing all convenience wrappers.

        Used by error-case tests that need to:
          - Omit the Authorization header (auth=False)
          - Send a malformed body
          - Hit non-existent endpoints

        auth=False creates a one-off client without BearerAuth.
        """
        if auth:
            return self._request(method, path, **kwargs)

        # No auth: use a plain httpx client (no BearerAuth)
        with httpx.Client(
            base_url=self._settings.base_url,
            timeout=self._settings.request_timeout_seconds,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        ) as plain_client:
            resp = plain_client.request(method, path, **kwargs)
        logger.debug("<-- (no-auth) %s %s | status=%s", method, path, resp.status_code)
        return resp
