# Poll until lastAnalysisStatus == "OK" and lastReport is populated.

from __future__ import annotations
import logging
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed, RetryCallState
from api_framework.clients.idcheck_client import IDCheckClient
from api_framework.models.response_models import DocumentResponse
from config.settings import Settings

logger = logging.getLogger(__name__)


class AnalysisNotCompleteError(Exception):
    pass


class PollingTimeoutError(TimeoutError):
    pass


def _log_attempt(retry_state: RetryCallState) -> None:
    logger.info("Polling attempt #%d — not yet complete, retrying...", retry_state.attempt_number)


def poll_until_complete(
    client: IDCheckClient,
    document_uid: str,
    timeout_seconds: int,
    interval_seconds: int,
) -> DocumentResponse:
    """
    Poll GET /document/{uid} until lastAnalysisStatus == OK.

    The IDcheck API signals completion via lastAnalysisStatus="OK"
    and a populated lastReport object — NOT via a "FINAL" state field.
    """
    @retry(
        retry=retry_if_exception_type(AnalysisNotCompleteError),
        wait=wait_fixed(interval_seconds),
        stop=stop_after_delay(timeout_seconds),
        after=_log_attempt,
        reraise=False,
    )
    def _poll() -> DocumentResponse:
        doc = client.get_document(document_uid)
        logger.debug(
            "Poll: uid=%s lastAnalysisStatus=%s lastReport=%s",
            document_uid,
            doc.last_analysis_status,
            "present" if doc.last_report else "null",
        )
        if doc.is_complete():
            return doc
        raise AnalysisNotCompleteError(
            f"Document {document_uid}: lastAnalysisStatus={doc.last_analysis_status!r}, "
            f"lastReport={'present' if doc.last_report else 'null'}"
        )

    try:
        return _poll()
    except AnalysisNotCompleteError as exc:
        raise PollingTimeoutError(
            f"Document {document_uid} did not complete within {timeout_seconds}s. "
            f"Last: {exc}"
        ) from exc
