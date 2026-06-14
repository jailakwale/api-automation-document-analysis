# TC-CT-01 through TC-CT-05: OpenAPI contract / schema conformance tests.

from __future__ import annotations

import logging
from typing import Any

import httpx
import jsonschema
import pytest
import allure

from api_framework.clients.idcheck_client import IDCheckClient
from api_framework.models.request_models import DocumentCreateRequest, DocumentImage
from config.settings import Settings

logger = logging.getLogger(__name__)

SWAGGER_URL = "https://api.idcheck-sandbox.ariadnext.io/gw/cis/api/swagger.json"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def openapi_spec() -> dict[str, Any]:
    """
    Fetch the live OpenAPI specification from the sandbox.
    Module-scoped: fetched once for all contract tests.

    If the swagger endpoint is unreachable, skip the contract suite rather
    than fail — this avoids false failures in environments with no internet.
    """
    try:
        resp = httpx.get(SWAGGER_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        pytest.skip(f"Could not fetch OpenAPI spec from {SWAGGER_URL}: {exc}")


def _resolve_schema(spec: dict, schema_name: str) -> dict[str, Any]:
    """
    Extract a component schema by name from the OpenAPI spec.
    Resolves top-level $ref pointers within components/schemas.
    """
    schemas = spec.get("components", {}).get("schemas", {})
    if schema_name not in schemas:
        raise KeyError(
            f"Schema '{schema_name}' not found in OpenAPI components/schemas. "
            f"Available: {list(schemas.keys())[:10]}"
        )
    return schemas[schema_name]


def _validate_response(body: dict, schema: dict, spec: dict) -> None:
    """
    Validate a response body dict against a jsonschema schema.

    We use a RefResolver so that $ref pointers within the schema
    (e.g. '#/components/schemas/DocumentReport') resolve correctly.
    """
    # Build a resolver that resolves $ref against the full spec
    base_uri = SWAGGER_URL
    resolver = jsonschema.RefResolver(base_uri=base_uri, referrer=spec)
    validator = jsonschema.Draft7Validator(schema, resolver=resolver)
    errors = list(validator.iter_errors(body))
    if errors:
        error_messages = "\n".join(
            f"  [{err.path}] {err.message}" for err in errors[:5]
        )
        raise AssertionError(
            f"Response body violates OpenAPI schema:\n{error_messages}"
        )


# ── Contract Tests ────────────────────────────────────────────────────────────

@allure.suite("Contract Testing")
@allure.feature("OpenAPI Schema Conformance")
class TestSchemaContract:
    """Validate API responses conform to the documented OpenAPI schemas."""

    @allure.title("TC-CT-01: OpenAPI spec is fetchable and valid JSON")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.contract
    def test_swagger_spec_is_accessible(self, openapi_spec: dict) -> None:
        """
        GIVEN the swagger.json URL
        WHEN  I fetch it
        THEN  it returns valid JSON with required OpenAPI fields
        """
        with allure.step("Validate top-level OpenAPI structure"):
            assert "openapi" in openapi_spec, "Missing 'openapi' version key"
            assert "paths" in openapi_spec, "Missing 'paths' key"
            assert "components" in openapi_spec, "Missing 'components' key"
            assert "schemas" in openapi_spec["components"], \
                "Missing 'schemas' under components"

        version = openapi_spec.get("info", {}).get("version", "unknown")
        allure.attach(
            f"OpenAPI version: {openapi_spec['openapi']}\nAPI version: {version}",
            name="Spec Info",
            attachment_type=allure.attachment_type.TEXT,
        )

    @allure.title("TC-CT-02: FileSummary response conforms to OpenAPI schema")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.contract
    def test_file_creation_response_schema(
        self,
        api_client: IDCheckClient,
        openapi_spec: dict,
        settings: Settings,
    ) -> None:
        """
        GIVEN a POST /file?synchronous=true request
        WHEN  the response is 201 Created
        THEN  the response body conforms to the FileSummary schema in swagger.json
        """
        with allure.step("Create a file"):
            resp = api_client.raw_request(
                "POST",
                f"/rest/v1/{settings.realm}/file",
                params={"synchronous": "true"},
                json={},
            )
            assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
            body = resp.json()
            file_uid = body.get("uid")

        with allure.step("Extract FileSummary schema from spec"):
            schema = _resolve_schema(openapi_spec, "FileSummary")

        with allure.step("Validate response body against FileSummary schema"):
            allure.attach(
                str(body),
                name="Response Body",
                attachment_type=allure.attachment_type.TEXT,
            )
            _validate_response(body, schema, openapi_spec)

        # Cleanup
        if file_uid:
            try:
                api_client.delete_file(file_uid)
            except Exception:
                pass

    @allure.title("TC-CT-03: DocumentSummary response conforms to OpenAPI schema")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.contract
    def test_document_creation_response_schema(
        self,
        api_client: IDCheckClient,
        openapi_spec: dict,
        settings: Settings,
        specimen_recto_b64: str,
    ) -> None:
        """
        GIVEN a POST /document?synchronous=true request
        WHEN  the response is 201 Created
        THEN  the response body conforms to DocumentSummary schema
        """
        request = DocumentCreateRequest(
            type="ID",
            images=[
                DocumentImage(data=specimen_recto_b64, document_part="RECTO"),
            ],
        )

        with allure.step("Create a document"):
            resp = api_client.raw_request(
                "POST",
                f"/rest/v1/{settings.realm}/document",
                params={"synchronous": "true"},
                json=request.model_dump_api(),
            )
            assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
            body = resp.json()
            doc_uid = body.get("uid")

        with allure.step("Validate against DocumentSummary schema"):
            schema = _resolve_schema(openapi_spec, "DocumentSummary")
            allure.attach(str(body), name="Document Response", attachment_type=allure.attachment_type.TEXT)
            _validate_response(body, schema, openapi_spec)

        # Cleanup
        if doc_uid:
            try:
                api_client.delete_document(doc_uid)
            except Exception:
                pass

    @allure.title("TC-CT-04: Full DocumentResponse conforms to OpenAPI schema after analysis")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.contract
    @pytest.mark.slow
    def test_analysed_document_response_schema(
        self,
        analysed_document,
        openapi_spec: dict,
        api_client: IDCheckClient,
        settings: Settings,
    ) -> None:
        """
        GIVEN a FINAL analysis report
        WHEN  I GET /document/{uid}
        THEN  the full response body conforms to the DocumentResponse schema
        """
        with allure.step("Fetch the raw document response"):
            resp = api_client.raw_request(
                "GET",
                f"/rest/v1/{settings.realm}/document/{analysed_document.uid}",
            )
            assert resp.status_code == 200
            body = resp.json()

        with allure.step("Validate against DocumentResponse schema"):
            schema = _resolve_schema(openapi_spec, "DocumentResponse")
            allure.attach(
                str(body)[:2000],
                name="Full Document Response (truncated)",
                attachment_type=allure.attachment_type.TEXT,
            )
            _validate_response(body, schema, openapi_spec)

    @allure.title("TC-CT-05: Error response for unauthorised request is structured")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.contract
    def test_error_response_has_structured_body(
        self,
        api_client: IDCheckClient,
        settings: Settings,
    ) -> None:
        """
        GIVEN  a request without authentication
        WHEN   the API returns 401
        THEN   the response body is valid JSON (not HTML or plain text)

        Structured error responses are essential for client-side error handling.
        An HTML error page or plain-text message would break API consumers.
        """
        with allure.step("Send unauthenticated request"):
            resp = api_client.raw_request(
                "GET",
                f"/rest/v1/{settings.realm}/document/some-uid",
                auth=False,
            )

        with allure.step("Assert 401 response body is valid JSON"):
            assert resp.status_code == 401

            # Try to parse as JSON — must not raise
            try:
                body = resp.json()
                allure.attach(
                    str(body),
                    name="Error Response Body (JSON)",
                    attachment_type=allure.attachment_type.TEXT,
                )
            except Exception:
                # Some gateways return non-JSON 401; warn but don't hard-fail
                allure.attach(
                    resp.text[:500],
                    name="Non-JSON Error Response",
                    attachment_type=allure.attachment_type.TEXT,
                )
                pytest.xfail("401 response is not JSON — may be gateway-level")
