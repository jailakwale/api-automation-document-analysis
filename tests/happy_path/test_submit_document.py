# TC-HP-01 through TC-HP-05: Happy path end-to-end flows

from __future__ import annotations
import pytest
import allure
from api_framework.clients.idcheck_client import IDCheckClient
from api_framework.models.request_models import DocumentCreateRequest, DocumentImage
from api_framework.models.response_models import DocumentResponse, TaskResponse


@allure.suite("Happy Path")
@allure.feature("Document Submission")
class TestHappyPath:

    @allure.title("TC-HP-01: Create document returns 201 with a UID")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.happy_path
    def test_create_document_returns_uid(
        self, api_client: IDCheckClient,
        specimen_recto_b64: str, specimen_verso_b64: str,
    ) -> None:
        """
        GIVEN a valid ID card image (recto + verso)
        WHEN  POST /document?synchronous=true
        THEN  201 Created with a non-empty UID string
        """
        request = DocumentCreateRequest(
            type="ID",
            images=[
                DocumentImage(data=specimen_recto_b64, document_part="RECTO", type="DL"),
                DocumentImage(data=specimen_verso_b64, document_part="VERSO", type="DL"),
            ],
        )
        with allure.step("POST /document with specimen ID card"):
            summary = api_client.create_document(request)

        with allure.step("Assert UID is present and non-empty"):
            assert summary.uid, "Document UID must not be empty"
            assert isinstance(summary.uid, str)
            assert len(summary.uid) > 8, f"UID looks too short: {summary.uid!r}"

        allure.attach(f"Document UID: {summary.uid}", name="UID", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Cleanup"):
            try:
                api_client.delete_document(summary.uid)
            except Exception as e:
                allure.attach(str(e), name="Cleanup note", attachment_type=allure.attachment_type.TEXT)

    @allure.title("TC-HP-02: Trigger analysis returns 202 Accepted")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.happy_path
    def test_trigger_check_returns_task(
        self, api_client: IDCheckClient,
        specimen_recto_b64: str, specimen_verso_b64: str,
    ) -> None:
        """
        GIVEN an existing document
        WHEN  POST /document/{uid}/check?synchronous=false
        THEN  202 Accepted with a task/confirmation response

        NOTE: No DELETE in teardown — the API returns 409 Conflict when
        trying to delete a document while analysis is in progress.
        This is correct state-machine behaviour: the document is locked
        during processing. This is documented, not a bug.
        """
        request = DocumentCreateRequest(
            type="ID",
            images=[
                DocumentImage(data=specimen_recto_b64, document_part="RECTO", type="DL"),
                DocumentImage(data=specimen_verso_b64, document_part="VERSO", type="DL"),
            ],
        )
        summary = api_client.create_document(request)

        with allure.step("Trigger document analysis"):
            task = api_client.trigger_document_check(summary.uid)

        with allure.step("Assert task response received"):
            assert task is not None, "Expected a response from /check"
            if isinstance(task, TaskResponse):
                assert task.uid, "Task UID must not be empty"

        allure.attach(str(task), name="Task Response", attachment_type=allure.attachment_type.TEXT)

    @allure.title("TC-HP-03: Analysis completes with lastAnalysisStatus=OK")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.happy_path
    @pytest.mark.slow
    def test_analysis_reaches_final_state(
        self, analysed_document: DocumentResponse,
    ) -> None:
        """
        GIVEN a submitted document with analysis triggered
        WHEN  polling until lastAnalysisStatus == OK
        THEN  the document is complete and lastReport is populated

        The IDcheck API uses lastAnalysisStatus="OK" (not a "FINAL" state)
        to signal that analysis is complete and results are available.
        """
        with allure.step("Assert lastAnalysisStatus is OK"):
            assert analysed_document.last_analysis_status == "OK", \
                f"Expected lastAnalysisStatus='OK', got '{analysed_document.last_analysis_status}'"

        with allure.step("Assert lastReport is populated"):
            assert analysed_document.last_report is not None, \
                "lastReport must be present when analysis is complete"

        allure.attach(
            f"lastAnalysisStatus: {analysed_document.last_analysis_status}\n"
            f"prettyName: {analysed_document.pretty_name}\n"
            f"classId: {analysed_document.class_id}",
            name="Analysis Result",
            attachment_type=allure.attachment_type.TEXT,
        )

    @allure.title("TC-HP-04: Analysis produces globalStatus verdict")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.happy_path
    @pytest.mark.slow
    def test_analysis_has_validity_verdict(
        self, analysed_document: DocumentResponse,
    ) -> None:
        """
        GIVEN a completed analysis report
        WHEN  I read lastReport.globalStatus
        THEN  it contains a recognised verdict: OK or KO

        globalStatus="OK"  → document is valid
        globalStatus="KO"  → document rejected
        """
        assert analysed_document.last_report is not None
        status = analysed_document.last_report.global_status

        known = {"OK", "KO"}
        assert status in known, \
            f"Unexpected globalStatus: {status!r}. Expected one of {known}"

        allure.attach(
            f"globalStatus: {status}",
            name="Validity Verdict",
            attachment_type=allure.attachment_type.TEXT,
        )

    @allure.title("TC-HP-05: Analysis extracts identity data fields")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.happy_path
    @pytest.mark.slow
    def test_analysis_extracts_data_fields(
        self, analysed_document: DocumentResponse,
    ) -> None:
        """
        GIVEN a completed analysis report
        THEN  lastReport.persons contains at least one person
        AND   lastReport.checks contains validation results

        The core value of IDcheck is data extraction. An empty persons list
        on a readable ID card signals an OCR or classification regression.
        """
        assert analysed_document.last_report is not None

        with allure.step("Assert persons data is extracted"):
            persons = analysed_document.last_report.persons
            assert len(persons) > 0, \
                "Expected at least one person extracted from ID card"

        with allure.step("Assert checks were performed"):
            checks = analysed_document.last_report.checks
            assert len(checks) > 0, \
                "Expected at least one check in the report"

        last_name = analysed_document.last_report.get_last_name()
        first_names = analysed_document.last_report.get_first_names()
        doc_num = analysed_document.last_report.get_document_number()

        allure.attach(
            f"Last name : {last_name}\n"
            f"First names: {first_names}\n"
            f"Doc number : {doc_num}\n"
            f"Persons    : {len(persons)}\n"
            f"Checks     : {len(checks)}",
            name="Extracted Data Summary",
            attachment_type=allure.attachment_type.TEXT,
        )
