SHELL := /bin/sh

.PHONY: frontend-install frontend-check backend-install backend-check config-check security-check secrets-check

frontend-install:
	cd frontend && npm ci

frontend-check:
	cd frontend && npm run typecheck && npm run lint && npm run format:check && npm test && npm run build

backend-install:
	python -m pip install -r backend/requirements/dev.txt

backend-check:
	PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test python backend/manage.py check
	PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test pytest backend
	cd backend && ruff check . && ruff format --check . && mypy config core identity

config-check:
	python scripts/validate_config.py

secrets-check:
	git ls-files -co --exclude-standard -z | xargs -0 detect-secrets-hook --json

security-check: secrets-check
	cd frontend && npm audit --audit-level=high
	pip-audit -r backend/requirements/dev.txt
