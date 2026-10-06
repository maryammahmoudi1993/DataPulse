# Changelog

All notable changes to DataPulse are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-10-06

### Added

**Core (Phase 1)**
- `streams` app — Workspace and Stream models with pluggable detector config
- `ingestion` app — DataPoint model, Celery Beat polling every 5 s
- `detection` — ZScoreDetector with rolling baseline
- `sources` — SimulatorAdapter (sinusoidal + noise + spike injection), CSVAdapter
- REST API — DRF endpoints for workspaces, streams, data points

**Anomaly Detection (Phase 2)**
- IQRDetector with configurable outlier fences
- LSTMDetector — PyTorch next-step predictor, graceful fallback to ZScore
- `train_lstm_for_stream` Celery task — on-demand per-stream training
- `alerts` app — Alert model with deduplication window, severity routing
- Webhook dispatch task with per-endpoint severity filtering
- Django Channels WebSocket consumers — real-time alert push

**Frontend & Docker (Phase 3)**
- React 18 + TypeScript + Recharts live dashboard
- `seed_demo` management command — synthetic data points + demo user
- Docker Compose stack (postgres, redis, web, worker, beat, frontend)
- WhiteNoise static file serving

**Auth & Isolation (Phase 4)**
- JWT authentication (register, login, refresh, logout, token blacklist)
- UserWorkspace model — OWNER / MEMBER / VIEWER roles
- Workspace-scoped API access (stream and alert isolation per user)
- `/train-lstm/` and `/training-status/` API actions
- `/compare-detectors/` — agreement statistics across two detector types
- `/health/` and `/readiness/` endpoints

**Observability & Export (Phase 5)**
- Ensemble detection — weighted majority vote across detectors
- Prometheus `/metrics/` — ingestion counter, detection latency, alert counter
- `exports` app — async CSV export (DataPoints + Alerts), download endpoint
- `reports` app — daily alert digest email to workspace owners (Celery Beat)
- `retention_days` field on Stream — automated DataPoint cleanup task
- Cursor pagination on DataPoints; workspace-level write throttle

**User Management (Phase 6)**
- WorkspaceInvite model — token-based email invites, 7-day expiry
- Invite service: create, accept, revoke, email dispatch
- Member management API — list, change role, remove (with last-owner guard)
- `audit` app — AuditEvent model (13 action types), `log_event()` service
- Audit log API — owner-only, filterable by action

**Integrations (Phase 7)**
- SlackIntegration — Block Kit alert notifications per workspace
- PagerDutyIntegration — Events API v2 incident trigger
- NotificationLog — per-alert, per-channel delivery record
- `/alerts/{id}/resolve/` endpoint + ALERT_RESOLVED audit event
- OpenAPI 3 schema via drf-spectacular — Swagger UI + ReDoc
- Invite accept page at `/invite/:token` (frontend + backend)

**Portfolio (Phase 8)**
- `render.yaml`, `fly.toml`, `Procfile` — one-click cloud deployment
- `settings_prod.py` — HTTPS headers, CORS, production guards
- GitHub Actions CI — test, lint, OpenAPI validate, frontend build
- Playwright screenshot automation

**Production Hardening (Phase 9)**
- Redis query cache — stream list (60 s TTL) and alert list (30 s TTL), invalidated on every write and on new alerts; alert cache is access-checked per request
- Sentry SDK — Django + Celery + Redis integrations, PII disabled
- SecurityHeadersMiddleware — CSP, X-Frame-Options, Permissions-Policy
- `select_related` on stream and alert list endpoints; query-count regression tests
- `production_check` management command — 14 automated deployment checks
- Postman collection generator (`scripts/generate_postman.py`)
- `CHANGELOG.md`

### Stats

- 12 Django apps
- 40 API paths (60 operations)
- 3 detector types (Z-Score, IQR, LSTM) plus ensemble voting
- 3 notification channels (Webhook, Slack, PagerDuty)
- 13 audit event types
- 257 tests · 96% coverage · flake8 clean
