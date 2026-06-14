"""
tests/conftest.py
Session-scoped fixtures wiring the entire framework together.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from api_framework.auth.token_manager import TokenManager
from api_framework.clients.idcheck_client import IDCheckClient
from api_framework.models.request_models import DocumentCreateRequest, DocumentImage
from api_framework.models.response_models import DocumentResponse
from api_framework.utils.file_utils import get_specimen_back, get_specimen_front
from api_framework.utils.polling import PollingTimeoutError, poll_until_complete
from config.settings import Settings, get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def token_manager(settings: Settings) -> TokenManager:
    return TokenManager(settings)


@pytest.fixture(scope="function")
def api_client(settings: Settings, token_manager: TokenManager) -> IDCheckClient:
    client = IDCheckClient(settings, token_manager)
    yield client
    client.close()


@pytest.fixture(scope="session")
def specimen_recto_b64() -> str:
    return get_specimen_front()


@pytest.fixture(scope="session")
def specimen_verso_b64() -> str:
    return get_specimen_back()


@pytest.fixture(scope="session")
def analysed_document(
    settings: Settings,
    token_manager: TokenManager,
    specimen_recto_b64: str,
    specimen_verso_b64: str,
) -> DocumentResponse:
    """
    Session-scoped fixture: runs full submission + analysis flow ONCE.
    All happy_path, field_assertions, and contract tests share this result.

    ACTUAL API COMPLETION SIGNAL:
      lastAnalysisStatus == "OK" AND lastReport is populated.
      No "FINAL" state — the API uses globalStatus="OK" for validity.
    """
    client = IDCheckClient(settings, token_manager)
    document_uid: str | None = None
    log = logging.getLogger(__name__)

    try:
        # 1. Build request with both sides of the ID card
        request = DocumentCreateRequest(
            type="ID",
            images=[
                DocumentImage(data=specimen_recto_b64, document_part="RECTO", type="DL"),
                DocumentImage(data=specimen_verso_b64, document_part="VERSO", type="DL"),
            ],
        )

        # 2. Create document
        summary = client.create_document(request)
        document_uid = summary.uid
        log.info("[session fixture] Document created: uid=%s", document_uid)

        # 3. Trigger analysis
        client.trigger_document_check(document_uid)
        log.info("[session fixture] Analysis triggered for uid=%s", document_uid)

        # 4. Poll until lastAnalysisStatus == OK
        doc = poll_until_complete(
            client=client,
            document_uid=document_uid,
            timeout_seconds=settings.poll_timeout_seconds,
            interval_seconds=settings.poll_interval_seconds,
        )
        log.info(
            "[session fixture] Analysis complete: globalStatus=%s prettyName=%s",
            doc.last_report.global_status if doc.last_report else "N/A",
            doc.pretty_name or "N/A",
        )
        yield doc

    finally:
        if document_uid:
            try:
                client.delete_document(document_uid)
                log.info("[session fixture] Cleaned up document uid=%s", document_uid)
            except Exception as exc:
                log.warning("Could not delete document %s: %s", document_uid, exc)
        client.close()
