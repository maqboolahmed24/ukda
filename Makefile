SHELL := /bin/bash
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
HELM_IMAGE ?= alpine/helm:3.17.3
ROOT_DIR := $(CURDIR)

.PHONY: install-js install-python lint format-check typecheck test test-browser test-preprocess-gold update-preprocess-gold-baseline build audit ci ci-js ci-python verify-images render-manifests dev-db-up dev-db-down dev-stack-up dev-stack-down smoke-health clean

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
	$(PYTHON) -m pytest api/tests --ignore=api/tests/test_preprocessing_gold_set.py
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
	docker build -f workers/Dockerfile -t ukde/workers:local workers

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
