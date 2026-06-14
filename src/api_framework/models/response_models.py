# Pydantic v2 models matching the ACTUAL IDcheck API response structure.

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class LabelValue(BaseModel):
    label: str | None = None
    value: Any = None
    model_config = {"extra": "allow"}


class LabelValues(BaseModel):
    label: str | None = None
    values: list[Any] = Field(default_factory=list)
    model_config = {"extra": "allow"}


class DateField(BaseModel):
    label: str | None = None
    value: str | None = None
    day: int | None = None
    month: int | None = None
    year: int | None = None
    model_config = {"extra": "allow"}


class ExtraField(BaseModel):
    key: str | None = None
    label: str | None = None
    value: str | None = None
    model_config = {"extra": "allow"}


class IdentityData(BaseModel):
    first_names: LabelValues | None = Field(None, alias="firstNames")
    last_name: LabelValue | None = Field(None, alias="lastName")
    birth_date: DateField | None = Field(None, alias="birthDate")
    birth_day: LabelValue | None = Field(None, alias="birthDay")
    birth_month: LabelValue | None = Field(None, alias="birthMonth")
    birth_year: LabelValue | None = Field(None, alias="birthYear")
    birth_place: LabelValue | None = Field(None, alias="birthPlace")
    gender: LabelValue | None = None
    nationality: LabelValue | None = None
    usage_name: LabelValue | None = Field(None, alias="usageName")
    extra: list[ExtraField] = Field(default_factory=list)
    model_config = {"extra": "allow", "populate_by_name": True}


class Person(BaseModel):
    identity_data: IdentityData | None = Field(None, alias="identityData")
    model_config = {"extra": "allow", "populate_by_name": True}


class ReportInfo(BaseModel):
    document_number: LabelValue | None = Field(None, alias="documentNumber")
    expiration_date: DateField | None = Field(None, alias="expirationDate")
    document_type: LabelValue | None = Field(None, alias="documentType")
    card_access_number: LabelValue | None = Field(None, alias="cardAccessNumber")
    extra: list[ExtraField] = Field(default_factory=list)
    model_config = {"extra": "allow", "populate_by_name": True}


class ReportIssuance(BaseModel):
    issue_date: DateField | None = Field(None, alias="issueDate")
    issuing_country: LabelValue | None = Field(None, alias="issuingCountry")
    model_config = {"extra": "allow", "populate_by_name": True}


class Check(BaseModel):
    identifier: str | None = None
    title: str | None = None
    message: str | None = None
    status: str | None = None
    type: str | None = None
    sub_checks: list["Check"] = Field(default_factory=list, alias="subChecks")
    model_config = {"extra": "allow", "populate_by_name": True}


class LastReport(BaseModel):
    uid: str | None = None
    generation_date: str | None = Field(None, alias="generationDate")
    global_status: str | None = Field(None, alias="globalStatus")
    checks: list[Check] = Field(default_factory=list)
    persons: list[Person] = Field(default_factory=list)
    info: ReportInfo | None = None
    issuance: ReportIssuance | None = None
    backend_result_id: str | None = Field(None, alias="backendResultId")
    model_config = {"extra": "allow", "populate_by_name": True}

    # ── Convenience helpers ───────────────────────────────────────────────────

    def get_last_name(self) -> str | None:
        try:
            return self.persons[0].identity_data.last_name.value
        except (IndexError, AttributeError):
            return None

    def get_first_names(self) -> list[str]:
        try:
            return self.persons[0].identity_data.first_names.values or []
        except (IndexError, AttributeError):
            return []

    def get_document_number(self) -> str | None:
        try:
            return self.info.document_number.value
        except AttributeError:
            return None

    def get_expiration_date(self) -> str | None:
        try:
            return self.info.expiration_date.value
        except AttributeError:
            return None

    def get_mrz_lines(self) -> list[str]:
        try:
            return [e.value for e in self.info.extra if e.value and "MRZ" in (e.key or "")]
        except AttributeError:
            return []

    def get_check(self, identifier: str) -> Check | None:
        for check in self.checks:
            if check.identifier == identifier:
                return check
            for sub in check.sub_checks:
                if sub.identifier == identifier:
                    return sub
        return None


class DocumentResponse(BaseModel):
    """
    Full document response from GET /document/{uid}.
    Maps to the ACTUAL API response structure discovered from live calls.
    """
    uid: str
    owner: str | None = None
    type: str | None = None
    sub_type: str | None = Field(None, alias="subType")
    class_id: str | None = Field(None, alias="classId")
    pretty_name: str | None = Field(None, alias="prettyName")
    last_report: LastReport | None = Field(None, alias="lastReport")
    last_analysis_status: str | None = Field(None, alias="lastAnalysisStatus")
    creation_date: str | None = Field(None, alias="creationDate")
    last_update_date: str | None = Field(None, alias="lastUpdateDate")

    model_config = {"extra": "allow", "populate_by_name": True}

    def is_complete(self) -> bool:
        """Analysis is complete when lastAnalysisStatus=OK and lastReport is populated."""
        return self.last_analysis_status == "OK" and self.last_report is not None

    def is_valid(self) -> bool:
        """Document is valid when globalStatus=OK."""
        return (
            self.last_report is not None
            and self.last_report.global_status == "OK"
        )


class DocumentSummary(BaseModel):
    uid: str
    owner: str | None = None
    type: str | None = None
    creation_date: str | None = Field(None, alias="creationDate")
    model_config = {"extra": "allow", "populate_by_name": True}


class FileSummary(BaseModel):
    uid: str
    model_config = {"extra": "allow"}


class TaskResponse(BaseModel):
    uid: str | None = None
    status: str | None = None
    model_config = {"extra": "allow"}


class APIErrorResponse(BaseModel):
    error_code: str | None = Field(None, alias="errorCode")
    error_message: str | None = Field(None, alias="errorMessage")
    error: str | None = None
    message: str | None = None
    model_config = {"extra": "allow", "populate_by_name": True}
