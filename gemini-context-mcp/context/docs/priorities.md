# Sprint Priorities — Q1 2026

**Sprint 7** (2026-02-17 → 2026-02-28) · Tech Lead: Maya Chen

---

## 🔴 P0 — Must Ship This Sprint

### AUTH-112: Refresh-token rotation vulnerability
- **Owner**: Priya Nair
- **Status**: In review (PR #441)
- **Summary**: Tokens are not invalidated after rotation. An attacker who
  intercepts a used refresh token can obtain new access tokens indefinitely.
- **Fix**: Implement single-use token families with server-side revocation list
  in Redis (TTL = refresh token lifetime).
- **Tests**: `tests/auth/test_token_rotation.py` — 14 new test cases.

### INFRA-89: Database connection pool exhaustion under load
- **Owner**: Tomás Novák
- **Status**: In progress
- **Summary**: Under 500+ concurrent requests, asyncpg pool hits its limit and
  new requests hang until timeout. Causes cascading failures.
- **Fix**: Increase pool size from 10 → 50; add circuit breaker via `tenacity`;
  expose pool metrics to Prometheus.
- **Related**: INFRA-91 (Grafana dashboard for pool metrics)

---

## 🟡 P1 — High Priority

### API-203: Paginate `/users` endpoint
- **Owner**: Lucas Ferreira
- **Status**: Not started
- **Summary**: Endpoint currently returns all users in a single response,
  causing OOM on large accounts (>10k users).
- **Fix**: Cursor-based pagination; default page size 50, max 500.
- **Breaking change**: Yes — coordinate with @jordanlee for API versioning.

### FRONT-77: Skeleton loading states
- **Owner**: Sam Okafor
- **Status**: In progress (60%)
- **Summary**: Replace spinner-of-doom with skeleton screens on dashboard,
  user list, and workflow detail pages. Design spec in Figma (link in PR #438).

---

## 🟢 P2 — Nice to Have

### DOCS-14: OpenAPI spec for v2 endpoints
- **Owner**: Lucas Ferreira (paired with Jordan Lee for copy)
- **Status**: Not started

### PERF-22: Query optimisation for workflow search
- **Owner**: Priya Nair
- **Status**: Blocked on INFRA-89 metrics (need baseline first)

---

## Upcoming (Sprint 8)

- ML-01: First pass of recommendation engine (feature-flagged)
- AUTH-120: SAML SSO for enterprise customers
- INFRA-95: Migrate staging to Kubernetes
