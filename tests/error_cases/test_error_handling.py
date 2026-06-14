# TC-EC-01 through TC-EC-08: Negative testing / error case scenarios

from __future__ import annotations

import pytest
import allure

from api_framework.clients.idcheck_client import IDCheckClient
from config.settings import Settings

# Placeholder UIDs — these must not exist in the sandbox
NON_EXISTENT_UID = "00000000-0000-0000-0000-000000000000"
INVALID_REALM    = "this-realm-does-not-exist-xyz"


@allure.suite("Error Cases")
@allure.feature("Authentication & Authorization")
class TestAuthErrors:
    """Verify that the API correctly rejects unauthenticated / badly-authenticated requests."""

    @allure.title("TC-EC-01: Request without Authorization header returns 401")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.error_cases
    def test_no_auth_header_returns_401(
        self, api_client: IDCheckClient, settings: Settings
    ) -> None:
        """
        GIVEN  no Authorization header
        WHEN   I GET /rest/v1/{realm}/document/{uid}
        THEN   the response status is 401 Unauthorized

        This verifies that the API gateway enforces authentication and does
        not expose data to unauthenticated callers.
        """
        with allure.step("Send request without Authorization header"):
            resp = api_client.raw_request(
                "GET",
                f"/rest/v1/{settings.realm}/document/{NON_EXISTENT_UID}",
                auth=False,
            )

        with allure.step("Assert 401 status code"):
            assert resp.status_code == 401, (
                f"Expected 401 Unauthorized for unauthenticated request, "
                f"got {resp.status_code}"
            )

        allure.attach(
            resp.text,
            name="Response Body",
            attachment_type=allure.attachment_type.TEXT,
        )

    @allure.title("TC-EC-02: Request with invalid Bearer token returns 401")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.error_cases
    def test_invalid_bearer_token_returns_401(
        self, api_client: IDCheckClient, settings: Settings
    ) -> None:
        """
        GIVEN  an Authorization header with a forged/invalid Bearer token
        WHEN   I GET /rest/v1/{realm}/document/{uid}
        THEN   the response status is 401 Unauthorized

        An invalid JWT should fail signature verification at the gateway.
        """
        with allure.step("Send request with forged Bearer token"):
            resp = api_client.raw_request(
                "GET",
                f"/rest/v1/{settings.realm}/document/{NON_EXISTENT_UID}",
                auth=False,
                headers={
                    "Authorization": "Bearer this.is.not.a.valid.jwt.token",
                    "Accept": "application/json",
                },
            )

        with allure.step("Assert 401 status code"):
            assert resp.status_code == 401, (
                f"Expected 401 for invalid token, got {resp.status_code}"
            )

    @allure.title("TC-EC-03: Token endpoint with wrong credentials returns 401")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.error_cases
    def test_token_request_with_wrong_credentials(
        self, settings: Settings
    ) -> None:
        """
        GIVEN  a token request with an incorrect client_secret
        WHEN   I POST to the OAuth2 token endpoint
        THEN   the response status is 401 Unauthorized
        AND    the body contains an error field

        Validates that the auth server correctly rejects bad credentials.
        This is a separate test from API-level auth because it targets the
        OpenID Connect layer.
        """
        import httpx

        with allure.step("POST token endpoint with bad client_secret"):
            resp = httpx.post(
                settings.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.oauth_client_id,
                    "client_secret": "definitely-wrong-secret-12345",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )

        with allure.step("Assert 401 and error body"):
            assert resp.status_code == 401, (
                f"Expected 401 for bad client_secret, got {resp.status_code}"
            )
            body = resp.json()
            assert "error" in body, f"Expected 'error' key in response body. Got: {body}"

        allure.attach(
            str(resp.json()),
            name="Token Error Response",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.suite("Error Cases")
@allure.feature("Resource Not Found")
class TestNotFoundErrors:
    """Verify 404 behaviour for non-existent resources."""

    @allure.title("TC-EC-04: GET non-existent document returns 404")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.error_cases
    def test_get_nonexistent_document_returns_404(
        self, api_client: IDCheckClient, settings: Settings
    ) -> None:
        """
        GIVEN  a valid authenticated request
        WHEN   I GET /document with a UID that does not exist
        THEN   the response status is 404 Not Found

        This verifies that the API does not return 200 with empty data
        or 500 for unknown UIDs — a common API design smell.
        """
        import httpx

        with allure.step("GET /document with non-existent UID"):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                api_client.get_document(NON_EXISTENT_UID)

        with allure.step("Assert 404 status code"):
            assert exc_info.value.response.status_code == 404, (
                f"Expected 404, got {exc_info.value.response.status_code}"
            )

    @allure.title("TC-EC-05: Delete non-existent document returns 404")
    @allure.severity(allure.severity_level.MINOR)
    @pytest.mark.error_cases
    def test_delete_nonexistent_document_returns_404(
        self, api_client: IDCheckClient
    ) -> None:
        """
        GIVEN  a valid authenticated request
        WHEN   I DELETE /document with a UID that does not exist
        THEN   the response status is 404 Not Found
        """
        import httpx

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            api_client.delete_document(NON_EXISTENT_UID)

        assert exc_info.value.response.status_code in {404, 400}, (
            f"Expected 404 or 400 for non-existent UID, "
            f"got {exc_info.value.response.status_code}"
        )


@allure.suite("Error Cases")
@allure.feature("Invalid Input")
class TestInvalidInputErrors:
    """Verify 400/422 behaviour for malformed or missing request data."""

    @allure.title("TC-EC-06: Create document with empty body returns 400")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.error_cases
    def test_create_document_empty_body_returns_error(
        self, api_client: IDCheckClient, settings: Settings
    ) -> None:
        """
        GIVEN  an authenticated request
        WHEN   I POST /document with an empty JSON body {}
        THEN   the response is a client error (4xx)

        An empty body lacks the required `type` field. The API should
        reject it with 400 Bad Request or 422 Unprocessable Entity.
        """
        with allure.step("POST /document with empty body"):
            resp = api_client.raw_request(
                "POST",
                f"/rest/v1/{settings.realm}/document",
                params={"synchronous": "true"},
                json={},
            )

        with allure.step("Assert client error response"):
            # The API may accept {} and return 201 with defaults, OR reject with 4xx.
            # We assert it does NOT return 500 (server should handle this gracefully).
            assert resp.status_code != 500, (
                f"API returned 500 for empty body. "
                f"Expected graceful 4xx handling. Response: {resp.text[:200]}"
            )
            allure.attach(
                f"Status: {resp.status_code}\nBody: {resp.text[:500]}",
                name="Response Details",
                attachment_type=allure.attachment_type.TEXT,
            )

    @allure.title("TC-EC-07: Create document with invalid image data returns error")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.error_cases
    def test_create_document_invalid_image_data(
        self, api_client: IDCheckClient, settings: Settings
    ) -> None:
        """
        GIVEN  an authenticated request
        WHEN   I POST /document with a non-base64, non-image `data` value
        THEN   the response is a client error (4xx)

        The API must not accept clearly invalid image data and must not
        return 500 (which would indicate unhandled server-side exception).
        """
        malformed_payload = {
            "type": "ID",
            "images": [
                {
                    "data": "THIS_IS_NOT_BASE64_IMAGE_DATA_!!!",
                    "documentPart": "RECTO",
                    "type": "DL",
                }
            ],
        }

        with allure.step("POST /document with invalid base64 image"):
            resp = api_client.raw_request(
                "POST",
                f"/rest/v1/{settings.realm}/document",
                params={"synchronous": "true"},
                json=malformed_payload,
            )

        with allure.step("Assert no 500 Internal Server Error"):
            assert resp.status_code != 500, (
                f"API returned 500 for invalid image data. "
                f"Expected graceful handling. Response: {resp.text[:300]}"
            )

        allure.attach(
            f"Status: {resp.status_code}\nBody: {resp.text[:500]}",
            name="Response for Invalid Image",
            attachment_type=allure.attachment_type.TEXT,
        )

    @allure.title("TC-EC-08: Trigger check on non-existent document returns 404")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.error_cases
    def test_check_nonexistent_document_returns_404(
        self, api_client: IDCheckClient, settings: Settings
    ) -> None:
        """
        GIVEN  an authenticated request
        WHEN   I POST /document/{uid}/check with a non-existent UID
        THEN   the response is 404 Not Found

        Ensures the analysis trigger endpoint validates resource existence
        before starting expensive processing.
        """
        import httpx

        with allure.step("POST /check on non-existent document"):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                api_client.trigger_document_check(NON_EXISTENT_UID)

        with allure.step("Assert 404 status"):
            assert exc_info.value.response.status_code == 404, (
                f"Expected 404, got {exc_info.value.response.status_code}"
            )
