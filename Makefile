SHELL := /bin/bash
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
HELM_IMAGE ?= alpine/helm:3.17.3
ROOT_DIR := $(CURDIR)

.PHONY: install-js install-python lint format-check typecheck test test-browser test-preprocess-gold test-privacy-regression test-governance-integrity test-provenance-readiness test-discovery-safety test-security-readiness test-capacity-recovery-readiness test-accessibility-readiness test-cross-phase-readiness readiness-audit smoke-release seed-nonprod-validate seed-nonprod-refresh release-gate launch-package test-export-hardening update-preprocess-gold-baseline build audit ci ci-js ci-python verify-images render-manifests dev-db-up dev-db-down dev-stack-up dev-stack-down smoke-health clean

install-js:
	pnpm install --frozen-lockfile

install-python:
	$(PIP) install -r requirements/python-ci.lock -e "./api[dev]" -e "./workers[dev]"

lint:
	pnpm lint
	$(PYTHON) -m ruff check api workers

format-check:
	pnpm format:check
	$(PYTHON) -m ruff format --check api workers

typecheck:
	pnpm typecheck
	$(PYTHON) -c "import app.main"
	$(PYTHON) -c "import ukde_workers.runtime"

test:
	pnpm test
	$(PYTHON) -m pytest api/tests
	$(PYTHON) -m pytest workers/tests

test-browser:
	pnpm test:browser

test-preprocess-gold:
	$(PYTHON) -m pytest api/tests/test_preprocessing_gold_set.py

test-privacy-regression:
	$(PYTHON) -m pytest \
		api/tests/test_privacy_regression_pack.py \
		api/tests/test_redaction_detection.py \
		api/tests/test_redaction_preview.py \
		api/tests/test_documents_redaction_routes.py

test-governance-integrity:
	$(PYTHON) -m pytest \
		api/tests/test_governance_integrity.py \
		api/tests/test_evidence_ledger.py \
		api/tests/test_documents_governance_routes.py

test-provenance-readiness:
	$(PYTHON) -m pytest \
		api/tests/test_bundle_verification.py \
		api/tests/test_export_provenance.py \
		api/tests/test_exports_replay.py

test-discovery-safety:
	$(PYTHON) -m pytest \
		api/tests/test_search_routes.py \
		api/tests/test_search_service.py \
		api/tests/test_indexes_routes.py \
		api/tests/test_indexes_service.py

test-security-readiness:
	$(PYTHON) -m pytest \
		api/tests/test_security_findings_service.py \
		api/tests/test_security_routes.py \
		api/tests/test_model_stack.py

test-capacity-recovery-readiness:
	$(PYTHON) -m pytest \
		api/tests/test_capacity_routes.py \
		api/tests/test_capacity_service.py \
		api/tests/test_recovery_routes.py \
		api/tests/test_recovery_service.py

test-accessibility-readiness:
	pnpm -s vitest run \
		web/components/authenticated-shell.a11y.test.tsx \
		web/components/route-states.a11y.test.tsx

test-cross-phase-readiness:
	$(MAKE) test-accessibility-readiness
	$(MAKE) test-privacy-regression PYTHON=$(PYTHON)
	$(MAKE) test-governance-integrity PYTHON=$(PYTHON)
	$(MAKE) test-provenance-readiness PYTHON=$(PYTHON)
	$(MAKE) test-export-hardening PYTHON=$(PYTHON)
	$(MAKE) test-discovery-safety PYTHON=$(PYTHON)
	$(MAKE) test-security-readiness PYTHON=$(PYTHON)
	$(MAKE) test-capacity-recovery-readiness PYTHON=$(PYTHON)

readiness-audit:
	$(PYTHON) scripts/run_readiness_audit.py --strict --python-bin "$(PYTHON)"

TARGET_ENV ?= dev
SOURCE_ENV ?= dev
RELEASE_MODE ?= promote
DATABASE_URL ?=

smoke-release:
	$(PYTHON) scripts/run_release_smoke_suite.py \
		--profile "$(TARGET_ENV)" \
		--strict \
		--python-bin "$(PYTHON)"

seed-nonprod-validate:
	$(PYTHON) scripts/refresh_nonprod_seed_data.py \
		--environment "$(TARGET_ENV)" \
		--strict

seed-nonprod-refresh:
	$(PYTHON) scripts/refresh_nonprod_seed_data.py \
		--environment "$(TARGET_ENV)" \
		--apply \
		--database-url "$(DATABASE_URL)" \
		--strict

release-gate:
	$(PYTHON) scripts/run_release_gate.py \
		--mode "$(RELEASE_MODE)" \
		--source-env "$(SOURCE_ENV)" \
		--target-env "$(TARGET_ENV)" \
		--strict

launch-package:
	$(PYTHON) scripts/build_launch_readiness_package.py --strict

test-export-hardening:
	$(PYTHON) -m pytest api/tests/test_export_hardening_regression.py

APPROVED_BY ?= local
APPROVAL_REFERENCE ?= local
APPROVAL_SUMMARY ?= Local preprocessing baseline refresh

update-preprocess-gold-baseline:
	$(PYTHON) scripts/update_preprocessing_gold_set_baseline.py \
		--approved-by "$(APPROVED_BY)" \
		--approval-reference "$(APPROVAL_REFERENCE)" \
		--approval-summary "$(APPROVAL_SUMMARY)"

build:
	pnpm build

audit:
	pnpm audit --audit-level high --prod
	$(PYTHON) -m pip_audit -r requirements/python-ci.lock --strict

ci-js:
	pnpm lint
	pnpm format:check
	pnpm typecheck
	pnpm test
	pnpm test:browser
	pnpm build

ci-python:
	$(PYTHON) -m ruff check api workers
	$(PYTHON) -m ruff format --check api workers
	$(PYTHON) -c "import app.main"
	$(PYTHON) -c "import ukde_workers.runtime"
	$(MAKE) test-preprocess-gold PYTHON=$(PYTHON)
	$(MAKE) test-privacy-regression PYTHON=$(PYTHON)
	$(MAKE) test-governance-integrity PYTHON=$(PYTHON)
	$(MAKE) test-export-hardening PYTHON=$(PYTHON)
	$(PYTHON) -m pytest \
		api/tests \
		--ignore=api/tests/test_preprocessing_gold_set.py \
		--ignore=api/tests/test_privacy_regression_pack.py \
		--ignore=api/tests/test_governance_integrity.py \
		--ignore=api/tests/test_export_hardening_regression.py \
		--ignore=api/tests/test_redaction_detection.py \
		--ignore=api/tests/test_redaction_preview.py \
		--ignore=api/tests/test_documents_redaction_routes.py
	$(PYTHON) -m pytest workers/tests
	$(PYTHON) -m pip_audit -r requirements/python-ci.lock --strict

ci:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) build
	$(MAKE) audit

verify-images:
	docker build -f web/Dockerfile -t ukde/web:local .
	docker build -f api/Dockerfile -t ukde/api:local api
	docker build -f workers/Dockerfile -t ukde/workers:local .

render-manifests:
	docker run --rm -v "$(ROOT_DIR)/infra/helm/ukde:/chart" $(HELM_IMAGE) template ukde-preview /chart -f /chart/values.yaml -f /chart/values-preview.yaml >/dev/null
	docker run --rm -v "$(ROOT_DIR)/infra/helm/ukde:/chart" $(HELM_IMAGE) template ukde-dev /chart -f /chart/values.yaml -f /chart/values-dev.yaml >/dev/null
	docker run --rm -v "$(ROOT_DIR)/infra/helm/ukde:/chart" $(HELM_IMAGE) template ukde-staging /chart -f /chart/values.yaml -f /chart/values-staging.yaml >/dev/null
	docker run --rm -v "$(ROOT_DIR)/infra/helm/ukde:/chart" $(HELM_IMAGE) template ukde-prod /chart -f /chart/values.yaml -f /chart/values-prod.yaml >/dev/null

dev-db-up:
	docker compose up -d db

dev-db-down:
	docker compose down

dev-stack-up:
	docker compose --profile smoke up --build

dev-stack-down:
	docker compose --profile smoke down

smoke-health:
	./scripts/health-smoke.sh

clean:
	rm -rf web/.next api/.pytest_cache workers/.pytest_cache
