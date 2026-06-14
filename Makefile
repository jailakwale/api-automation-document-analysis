# ─── IDnow API Automation — Developer Makefile ────────────────────────────────
# Usage: make <target>
# Requires: Python 3.11+, pip

.PHONY: install install-dev test test-fast test-happy test-fields test-errors \
        test-contract test-parallel lint format typecheck allure-serve clean help

PYTHON   := python3
PIP      := pip
PYTEST   := python -m pytest
SRC      := src
REPORTS  := reports/allure-results

# ── Setup ──────────────────────────────────────────────────────────────────────

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"
	pre-commit install

# ── Test execution ─────────────────────────────────────────────────────────────

## Run the full suite (all markers)
test:
	PYTHONPATH=$(SRC) $(PYTEST) --alluredir=$(REPORTS) -v

## Run only fast tests (excludes @pytest.mark.slow)
test-fast:
	PYTHONPATH=$(SRC) $(PYTEST) -m "not slow" --alluredir=$(REPORTS) -v

## Run happy path tests only
test-happy:
	PYTHONPATH=$(SRC) $(PYTEST) -m happy_path --alluredir=$(REPORTS) -v

## Run field assertion tests only
test-fields:
	PYTHONPATH=$(SRC) $(PYTEST) -m field_assertions --alluredir=$(REPORTS) -v

## Run error case tests only
test-errors:
	PYTHONPATH=$(SRC) $(PYTEST) -m error_cases --alluredir=$(REPORTS) -v

## Run contract / schema tests only
test-contract:
	PYTHONPATH=$(SRC) $(PYTEST) -m contract --alluredir=$(REPORTS) -v

## Run full suite in parallel (4 workers)
test-parallel:
	PYTHONPATH=$(SRC) $(PYTEST) -n 4 --alluredir=$(REPORTS) -v

## Run with verbose output and no capture (useful for debugging a single test)
test-debug:
	PYTHONPATH=$(SRC) $(PYTEST) -s -v --tb=long --alluredir=$(REPORTS)

# ── Code quality ───────────────────────────────────────────────────────────────

lint:
	ruff check $(SRC) tests

format:
	black $(SRC) tests

typecheck:
	mypy $(SRC)

# ── Reporting ──────────────────────────────────────────────────────────────────

## Open Allure HTML report in browser (requires allure CLI: brew install allure)
allure-serve:
	allure serve $(REPORTS)

## Generate static Allure HTML report
allure-generate:
	allure generate $(REPORTS) -o reports/allure-html --clean

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf reports/allure-results/* reports/allure-html reports/junit.xml

# ── Help ───────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "IDnow API Automation — Available targets:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install all dependencies incl. dev tools"
	@echo "  make test             Run full test suite"
	@echo "  make test-fast        Run only non-slow tests"
	@echo "  make test-happy       Run happy path tests"
	@echo "  make test-fields      Run field assertion tests"
	@echo "  make test-errors      Run error case tests"
	@echo "  make test-contract    Run OpenAPI contract tests"
	@echo "  make test-parallel    Run suite with 4 parallel workers"
	@echo "  make lint             Ruff linting"
	@echo "  make format           Black auto-formatting"
	@echo "  make allure-serve     Open live Allure report in browser"
	@echo "  make clean            Remove cache and report artifacts"
	@echo ""
