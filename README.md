# IDnow IDcheck API — Test Automation Framework

[![CI](https://github.com/YOUR_USERNAME/idnow-api-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/idnow-api-automation/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![pytest](https://img.shields.io/badge/tested_with-pytest-green.svg)](https://pytest.org)

Production-grade API test automation framework for the **IDcheck CIS API** (sandbox environment).  
Designed, built, and documented for the IDnow QA Engineering Challenge.

---

## Architecture at a Glance

```
idnow-api-automation/
├── config/
│   └── settings.py              ← Pydantic BaseSettings (env-var driven config)
├── src/api_framework/
│   ├── auth/
│   │   └── token_manager.py     ← Thread-safe OAuth2 Client Credentials
│   ├── clients/
│   │   ├── base_client.py       ← httpx wrapper (auth injection, logging)
│   │   └── idcheck_client.py    ← IDcheck API operations (Page Object for APIs)
│   ├── models/
│   │   ├── request_models.py    ← Pydantic v2 request payloads
│   │   └── response_models.py   ← Pydantic v2 response contracts
│   └── utils/
│       ├── polling.py           ← tenacity-backed async poll-until-FINAL
│       └── file_utils.py        ← Image loading + base64 encoding
├── tests/
│   ├── conftest.py              ← Session fixtures (token, client, analysed_document)
│   ├── happy_path/              ← TC-HP-01..05: End-to-end submission flow
│   ├── field_assertions/        ← TC-FA-01..06: OCR field value assertions
│   ├── error_cases/             ← TC-EC-01..08: Auth, 404, bad input scenarios
│   └── contract/                ← TC-CT-01..05: OpenAPI schema conformance
├── test_data/images/            ← Specimen French ID card (recto + verso)
├── .github/workflows/ci.yml     ← GitHub Actions CI pipeline
└── Makefile                     ← Developer convenience targets
```

---

## Technology Choices & Rationale

| Technology | Why |
|---|---|
| **Python 3.11** | Mature, team-standard; `tomllib` built-in, `Self` type, `ExceptionGroup` |
| **pytest** | Industry standard; fixture DI, parametrize, plugin ecosystem |
| **httpx** | Modern `requests` replacement; type-annotated, HTTP/2-ready, connection pooling |
| **Pydantic v2** | Type-safe config + response deserialization; fail-fast on schema drift |
| **tenacity** | Declarative retry/polling — no error-prone while-loops |
| **jsonschema** | Industry-standard JSON Schema validation for contract testing |
| **allure-pytest** | Rich visual reports with steps, attachments, severity levels |
| **pytest-xdist** | Parallel test execution — cuts CI wall-clock time |
| **GitHub Actions** | Zero-friction CI; matrix builds across Python versions |

---

## API Flow Understanding

The IDcheck CIS API follows an **async document analysis pipeline**:

```
1. POST /document?synchronous=true    → Create document with base64 images → 201 + UID
2. POST /document/{uid}/check         → Trigger analysis → 202 + Task UID
3. GET  /document/{uid}  (poll loop)  → Monitor until report.state == "FINAL"
4. GET  /document/{uid}               → Retrieve final report + extracted fields
```

Authentication uses **OAuth2 Client Credentials** grant:
```
POST /auth/realms/customer-identity/protocol/openid-connect/token
  grant_type=client_credentials
  client_id=...
  client_secret=...
→ { access_token, expires_in: 300 }
```

---

## Test Coverage

### Happy Path (TC-HP-01..05)
| ID | Assertion |
|---|---|
| TC-HP-01 | Create document returns 201 with a UID |
| TC-HP-02 | Trigger analysis returns 202 Accepted with task UID |
| TC-HP-03 | Document analysis reaches FINAL state |
| TC-HP-04 | Analysis produces a validity verdict |
| TC-HP-05 | Analysis produces extracted data fields |

### Field Assertions (TC-FA-01..06) — on specimen card
| ID | Assertion |
|---|---|
| TC-FA-01 | Extracted surname = MARTIN |
| TC-FA-02 | Extracted first name contains MAELYS |
| TC-FA-03 | Document number = X4RTBPFW4 |
| TC-FA-04 | Validity verdict is not INVALID |
| TC-FA-05 | MRZ zone is extracted and non-empty |
| TC-FA-06 | All extracted fields have a validity status |

### Error Cases (TC-EC-01..08)
| ID | Scenario |
|---|---|
| TC-EC-01 | No Authorization header → 401 |
| TC-EC-02 | Invalid Bearer token → 401 |
| TC-EC-03 | Wrong client_secret → 401 from token endpoint |
| TC-EC-04 | GET non-existent document → 404 |
| TC-EC-05 | DELETE non-existent document → 404 |
| TC-EC-06 | Empty body on create document → 4xx (not 500) |
| TC-EC-07 | Invalid base64 image data → no 500 |
| TC-EC-08 | Trigger check on non-existent document → 404 |

### Contract Testing (TC-CT-01..05) — Bonus
| ID | Assertion |
|---|---|
| TC-CT-01 | swagger.json is fetchable and valid OpenAPI |
| TC-CT-02 | FileSummary response conforms to schema |
| TC-CT-03 | DocumentSummary response conforms to schema |
| TC-CT-04 | Full DocumentResponse (post-analysis) conforms to schema |
| TC-CT-05 | 401 error response is structured JSON |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/idnow-api-automation.git
cd idnow-api-automation
pip install -e ".[dev]"
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env:
# IDNOW_CLIENT_ID=candidate.2
# IDNOW_CLIENT_SECRET=<your_secret>
# IDNOW_REALM=<your_realm>
```

### 3. Run tests

```bash
# Full suite
make test

# Only fast (non-polling) tests
make test-fast

# By category
make test-happy
make test-errors
make test-contract

# Parallel execution
make test-parallel

# Open Allure report
make allure-serve
```

---

## CI Pipeline

GitHub Actions runs on every push and PR:

1. Matrix build across Python 3.11 + 3.12
2. Installs dependencies
3. Runs full test suite with Allure reporting
4. Uploads artifacts (allure-results, junit.xml, test log)
5. On `main` branch: publishes Allure HTML to GitHub Pages

### Required GitHub Secrets

Set in **Settings → Secrets → Actions**:
```
IDNOW_CLIENT_ID
IDNOW_CLIENT_SECRET
IDNOW_REALM
```

---

## ISTQB Alignment

This framework is designed to ISTQB Advanced Level Test Analyst standards:

- **Test Design Techniques**: EP, BVA, Decision Table, State Transition, Error Guessing
- **Test Data Management**: Externalised fixtures, env-var config, session-scoped shared data
- **Test Environment Management**: Config-driven, environment-agnostic (sandbox/production toggle)
- **Test Monitoring**: tenacity polling with structured logging and timeout handling
- **Component Interface Testing**: Pydantic model contracts + jsonschema validation
- **Defect Management**: Allure steps, severity levels, attachments for each test

---

## Author
Jaiprakash Lakwale (Jay)
Built for the IDnow QA Engineering Challenge
