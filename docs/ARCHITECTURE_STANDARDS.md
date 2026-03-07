# Architecture Standards

This document defines architecture, modularization, and configuration standards for PLOS Backend. The goals are security, maintainability, and future-proofing.

---

## Objectives

- Keep each service independently testable and deployable.
- Enforce clear dependency direction between layers.
- Centralize configuration and secrets handling.
- Standardize logging, errors, and health checks.
- Minimize coupling across services and shared utilities.

---

## Service Layout (Recommended)

Each service should follow this structure:

```
service-name/
  src/
    api/              FastAPI routers, request/response schemas
    application/      Use cases, orchestration, DTOs
    infrastructure/   DB, cache, kafka, external clients
    dependencies/     FastAPI deps and wiring
    core/             Settings, logging, constants, utilities
    main.py           Entrypoint only (no business logic)
    [workers/]        Background jobs (optional)
```

Notes:
- `main.py` only wires dependencies and routers.
- Business logic must not live in `api/` or `main.py`.
- `domain/` and `repositories/` directories are planned for future implementation but not currently required.

---

## Dependency Direction

Allowed dependencies:

- `api` -> `application`
- `application` -> `infrastructure`
- `infrastructure` -> external SDKs
- `dependencies` -> any layer for wiring only
- `core` -> used by any layer

Disallowed dependencies:

- `application` -> `api` or `infrastructure` directly

---

## Configuration Standard

Single source of truth: `shared/utils/unified_config.py`

Rules:
- Do not create new settings classes in services.
- Use `get_unified_settings()` everywhere.
- Secrets must only come from environment variables.
- Never hardcode credentials in code or docs.

---

## Error Handling

- Define domain errors in `domain/errors.py`.
- Use shared response models from `shared/utils/errors.py`.
- Translate domain errors to HTTP errors in `api/` only.
- Avoid raising `HTTPException` outside `api/`.

---

## Observability

Required in each service:
- Structured logging using `shared.utils.logging_config`.
- Prometheus metrics endpoint at `/metrics`.
- Health check endpoint at `/health`.

Logging rules:
- Use consistent log fields for service name and request id.
- Log errors with full context, avoid leaking secrets.

---

## Security

- Validate all input at API boundary.
- Use typed schemas for requests and responses.
- Enforce auth in routers, not in domain logic.
- Use least-privilege credentials for DB and Kafka.

---

## Naming Conventions

- Routers: `router.py`
- Schemas: `schemas.py`
- Services: `service.py`
- Repositories: `repository.py`
- Clients: `client.py`
- Tests: `test_*.py`

---

## Migration Plan

Current status: All services (journal-parser, context-broker, knowledge-base, api-gateway) follow the recommended layout structure. The `domain/` and `repositories/` layers are planned for future implementation when business logic complexity increases.

Future enhancements:
- Add `domain/` layer for complex business rules
- Add `repositories/` layer for data access abstractions
- Implement domain-driven design patterns as needed
