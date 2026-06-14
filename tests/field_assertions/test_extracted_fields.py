# TC-FA-01 through TC-FA-06: Field value assertions on the specimen ID card

from __future__ import annotations
import pytest
import allure
from api_framework.models.response_models import DocumentResponse


@allure.suite("Field Assertions")
@allure.feature("OCR Extracted Data")
class TestExtractedFields:

    @allure.title("TC-FA-01: Extracted last name = MARTIN")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.field_assertions
    @pytest.mark.slow
    def test_extracted_last_name(self, analysed_document: DocumentResponse) -> None:
        """
        GIVEN a completed analysis report
        WHEN  I read lastReport.persons[0].identityData.lastName.value
        THEN  the value equals 'MARTIN' (as printed on the specimen card)
        """
        assert analysed_document.last_report is not None, "lastReport must be present"
        last_name = analysed_document.last_report.get_last_name()

        allure.attach(
            f"Extracted last name: {last_name}",
            name="Last Name",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert last_name is not None, "lastName must not be null"
        assert last_name.upper() == "MARTIN", \
            f"Expected 'MARTIN', got '{last_name}'"

    @allure.title("TC-FA-02: Extracted first names contain Maëlys-Gaëlle and Marie")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.field_assertions
    @pytest.mark.slow
    def test_extracted_first_names(self, analysed_document: DocumentResponse) -> None:
        """
        GIVEN a completed analysis report
        WHEN  I read lastReport.persons[0].identityData.firstNames.values
        THEN  the list contains 'Maëlys-Gaëlle' and 'Marie'
        """
        assert analysed_document.last_report is not None
        first_names = analysed_document.last_report.get_first_names()

        allure.attach(
            f"Extracted first names: {first_names}",
            name="First Names",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert len(first_names) > 0, "firstNames.values must not be empty"

        all_names_upper = [n.upper() for n in first_names]
        # MRZ normalises Maëlys → MAELYS; OCR preserves accents
        found_first = any("MAELYS" in n or "MAËLYS" in n or "MAELYS-GAELLE" in n for n in all_names_upper)
        found_marie = any("MARIE" in n for n in all_names_upper)

        assert found_first, f"Expected 'Maëlys' variant in {first_names}"
        assert found_marie, f"Expected 'Marie' in {first_names}"

    @allure.title("TC-FA-03: Extracted document number = X4RTBPFW4")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.field_assertions
    @pytest.mark.slow
    def test_extracted_document_number(self, analysed_document: DocumentResponse) -> None:
        """
        GIVEN a completed analysis
        WHEN  I read lastReport.info.documentNumber.value
        THEN  it equals 'X4RTBPFW4' (as printed on the specimen card)
        """
        assert analysed_document.last_report is not None
        doc_num = analysed_document.last_report.get_document_number()

        allure.attach(f"Document number: {doc_num}", name="Doc Number", attachment_type=allure.attachment_type.TEXT)
        assert doc_num is not None, "documentNumber must not be null"
        assert doc_num.upper() == "X4RTBPFW4", \
            f"Expected 'X4RTBPFW4', got '{doc_num}'"

    @allure.title("TC-FA-04: Document validity globalStatus = OK")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.field_assertions
    @pytest.mark.slow
    def test_document_validity_status(self, analysed_document: DocumentResponse) -> None:
        """
        GIVEN a completed analysis on the specimen card
        WHEN  I read lastReport.globalStatus
        THEN  it equals 'OK' (document is valid)

        globalStatus values: OK = valid, KO = invalid/rejected
        """
        assert analysed_document.last_report is not None
        status = analysed_document.last_report.global_status

        allure.attach(f"globalStatus: {status}", name="Global Status", attachment_type=allure.attachment_type.TEXT)
        assert status == "OK", \
            f"Expected globalStatus='OK', got '{status}'"

    @allure.title("TC-FA-05: Expiration date = 11/02/2030")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.field_assertions
    @pytest.mark.slow
    def test_expiration_date(self, analysed_document: DocumentResponse) -> None:
        """
        GIVEN a completed analysis
        WHEN  I read lastReport.info.expirationDate.value
        THEN  it equals '11/02/2030'
        AND   expirationDate.year = 2030 (document is not expired)
        """
        assert analysed_document.last_report is not None
        expiry = analysed_document.last_report.get_expiration_date()
        expiry_year = None
        try:
            expiry_year = analysed_document.last_report.info.expiration_date.year
        except AttributeError:
            pass

        allure.attach(
            f"Expiration date: {expiry}\nYear: {expiry_year}",
            name="Expiry",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert expiry == "11/02/2030", f"Expected '11/02/2030', got '{expiry}'"
        assert expiry_year == 2030, f"Expected year 2030, got {expiry_year}"

    @allure.title("TC-FA-06: MRZ lines are extracted and correct")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.field_assertions
    @pytest.mark.slow
    def test_mrz_lines_extracted(self, analysed_document: DocumentResponse) -> None:
        """
        GIVEN a completed analysis
        WHEN  I read lastReport.info.extra[] where key starts with MRZ_LINE
        THEN  MRZ line 3 contains 'MARTIN' and 'MAELYS'
        """
        assert analysed_document.last_report is not None
        mrz_lines = analysed_document.last_report.get_mrz_lines()

        allure.attach(
            "\n".join(mrz_lines),
            name="MRZ Lines",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert len(mrz_lines) > 0, "Expected MRZ lines in lastReport.info.extra"
        all_mrz = " ".join(mrz_lines).upper()
        assert "MARTIN" in all_mrz, f"Expected MARTIN in MRZ. Got: {mrz_lines}"
        assert "MAELYS" in all_mrz, f"Expected MAELYS in MRZ. Got: {mrz_lines}"
        assert "IDFRAX4RTBPFW4" in all_mrz, f"Expected document number in MRZ. Got: {mrz_lines}"
