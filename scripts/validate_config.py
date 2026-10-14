#!/usr/bin/env python3
"""Validate checked-in CI, local Compose and Railway configuration structure."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"configuration validation failed: {message}")


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        document = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    except yaml.YAMLError as error:
        raise SystemExit(
            f"invalid YAML in {path.relative_to(ROOT)}: {error}"
        ) from error
    require(
        isinstance(document, dict), f"{path.relative_to(ROOT)} must be a YAML mapping"
    )
    return document


def validate_workflow() -> None:
    path = ROOT / ".github/workflows/ci.yml"
    workflow = read_yaml(path)
    require(workflow.get("name") == "Engineering checks", "CI workflow name missing")
    require(isinstance(workflow.get("on"), dict), "CI triggers are missing")
    jobs = workflow.get("jobs")
    require(isinstance(jobs, dict), "CI jobs are missing")
    expected_jobs = {"frontend", "backend", "security", "dependency-review"}
    require(expected_jobs.issubset(jobs), "required CI jobs are missing")

    backend = jobs["backend"]
    services = backend.get("services", {})
    postgres = services.get("postgres", {})
    require(
        postgres.get("image") == "postgres:16-alpine",
        "backend CI must use the disposable PostgreSQL 16 service",
    )
    require(
        postgres.get("env", {}).get("POSTGRES_HOST_AUTH_METHOD") == "trust",
        "CI PostgreSQL trust auth is permitted only for its isolated ephemeral service",
    )
    backend_env = backend.get("env", {})
    require(
        backend_env.get("DJANGO_SETTINGS_MODULE") == "config.settings.ci_postgres",
        "backend CI must run tests against PostgreSQL settings",
    )
    require(
        str(backend_env.get("EDUTRACK_CI_TEST_DATABASE_URL", "")).startswith(
            "postgresql://"
        ),
        "backend CI must provide a test-only PostgreSQL URL",
    )

    all_run_commands: list[str] = []
    for job_name, job in jobs.items():
        require(isinstance(job, dict), f"job {job_name} must be a mapping")
        require(isinstance(job.get("runs-on"), str), f"job {job_name} has no runner")
        steps = job.get("steps")
        require(isinstance(steps, list) and steps, f"job {job_name} has no steps")
        for step in steps:
            require(isinstance(step, dict), f"job {job_name} contains a malformed step")
            action = step.get("uses")
            if action:
                ref = str(action).rsplit("@", maxsplit=1)[-1]
                require(
                    re.fullmatch(r"[0-9a-f]{40}", ref) is not None,
                    f"third-party action in {job_name} must be pinned to a full commit SHA",
                )
            all_run_commands.append(str(step.get("run", "")))

    commands = " ".join(all_run_commands)
    for required_command, label in (
        ("npm run typecheck", "frontend typecheck"),
        ("npm run lint", "frontend lint"),
        ("npm test", "frontend tests"),
        ("npm run build", "frontend build"),
        ("pytest backend", "backend tests"),
        ("mypy config core identity institutional academic", "backend typecheck"),
        ("makemigrations --check --dry-run academic institutional", "migration drift"),
        ("migrate academic zero --noinput", "disposable migration reversal"),
        ("pip-audit", "backend dependency audit"),
        ("npm audit", "frontend dependency audit"),
        ("detect-secrets-hook", "source secret scan"),
    ):
        require(required_command in commands, f"{label} is absent from CI")


def validate_railway_config(path: Path, dockerfile: str, healthcheck: str) -> None:
    try:
        config = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as error:
        raise SystemExit(
            f"invalid TOML in {path.relative_to(ROOT)}: {error}"
        ) from error
    build = config.get("build", {})
    deploy = config.get("deploy", {})
    require(build.get("builder") == "DOCKERFILE", f"{path.name} builder is invalid")
    require(
        build.get("dockerfilePath") == dockerfile,
        f"{path.name} Dockerfile path is invalid",
    )
    require(
        deploy.get("healthcheckPath") == healthcheck,
        f"{path.name} health check is invalid",
    )
    require(
        deploy.get("restartPolicyType") == "ON_FAILURE",
        f"{path.name} restart policy is missing",
    )
    require(
        (ROOT / dockerfile).is_file(), f"referenced Dockerfile {dockerfile} is missing"
    )


def validate_environment_template() -> None:
    path = ROOT / ".env.example"
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", maxsplit=1)
        values[key] = value
    for secret_key in (
        "DJANGO_SECRET_KEY",
        "MFA_ENCRYPTION_KEY",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "IDENTITY_RECOVERY_DELIVERY_BACKEND",
        "ACADEMIC_MOCK_PREPARER_ROLE_CODE",
        "ACADEMIC_MOCK_APPROVER_ROLE_CODE",
        "ACADEMIC_BECE_LEVEL_CODE",
    ):
        require(
            values.get(secret_key, "") == "",
            f"{secret_key} must stay blank in the template",
        )
    require(
        values.get("IDENTITY_RECOVERY_TOKEN_TTL_SECONDS") == "0",
        "recovery token issuance must remain disabled in the template",
    )


def validate_package_lock() -> None:
    package = json.loads((ROOT / "frontend/package.json").read_text())
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    require(
        lock.get("name") == package.get("name"),
        "npm lockfile name does not match package.json",
    )
    require(
        lock.get("lockfileVersion", 0) >= 3, "npm lockfile must use a supported version"
    )
    require(
        lock.get("packages", {}).get("", {}).get("version") == package.get("version"),
        "npm lockfile root version does not match package.json",
    )


def validate_compose() -> None:
    compose = read_yaml(ROOT / "compose.yaml")
    services = compose.get("services", {})
    require(
        set(services) == {"db", "redis"}, "Compose may contain local dependencies only"
    )
    for service_name, service in services.items():
        ports = service.get("ports", [])
        require(
            all(str(port).startswith("127.0.0.1:") for port in ports),
            f"Compose service {service_name} ports must bind to loopback only",
        )


def validate_shell_entrypoint() -> None:
    path = ROOT / "deploy/web-entrypoint.sh"
    completed = subprocess.run(
        ["sh", "-n", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    require(
        completed.returncode == 0, f"invalid shell syntax: {completed.stderr.strip()}"
    )


def main() -> None:
    validate_workflow()
    validate_railway_config(
        ROOT / "railway.toml", "deploy/api.Dockerfile", "/api/v1/health/ready/"
    )
    validate_railway_config(
        ROOT / "deploy/railway-web.toml", "deploy/web.Dockerfile", "/"
    )
    validate_environment_template()
    validate_package_lock()
    validate_compose()
    validate_shell_entrypoint()
    print(
        "CI YAML, disposable PostgreSQL test service, action pins, Compose YAML, Railway TOML, shell syntax, environment template and npm lockfile are structurally valid."
    )


if __name__ == "__main__":
    main()
