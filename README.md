# DataPulse

Real-time anomaly detection and alerting platform for time-series data.
Monitors IoT sensors, server metrics, and financial signals.
Detects statistical and ML-based outliers and pushes live alerts
to connected dashboards via WebSocket.

---

## Live demo

| Resource | URL |
|---|---|
| Dashboard | https://datapulse-frontend.onrender.com |
| API docs  | https://datapulse.onrender.com/api/schema/swagger-ui/ |

Sign in with `demo / demodemo1` — a seeded Simulator stream runs continuously.

> The `demo` account and its password are public and exist for demonstration only.
> Change the password (or delete the user) before any real deployment.

---

## What it does

DataPulse ingests time-series data from any configured source, runs
it through a pluggable anomaly detection pipeline, and delivers
real-time alerts to a live dashboard and external channels.

**Detection methods:**
- Z-Score — rolling mean / standard deviation baseline
- IQR — interquartile range outlier fences
- LSTM — PyTorch next-step predictor; anomaly score = reconstruction error
- Ensemble — weighted majority vote across all three

**Alerting:**
- Deduplication window (configurable, default 5 min)
- Severity classification: LOW / MEDIUM / HIGH / CRITICAL
- Webhook dispatch with per-endpoint severity filtering
- Slack Block Kit notifications
- PagerDuty Events API v2 incident trigger
- Daily digest email to workspace owners

**Workspace model:**
- Multi-tenant from the start: every resource belongs to a workspace
- Roles: OWNER / MEMBER / VIEWER
- Token-based email invitations (7-day expiry)
- Full audit log (owner-only access)

---

## Architecture

```
Data sources (Simulator / CSV / HTTP)
        │
        ▼  Celery Beat — every 5 s
Ingestion pipeline
        │
        ▼  dispatched per stream
Detection pipeline ──► Z-Score
                  ├──► IQR
                  ├──► LSTM (PyTorch)
                  └──► Ensemble
        │ anomaly detected
        ▼
Alert engine ──► dedup ──► severity
        │
        ├──► PostgreSQL (persist)
        ├──► Redis pub/sub
        │         │
        │         ▼
        │    Django Channels
        │    WebSocket push ──► React dashboard
        │
        ├──► Webhook endpoints
        ├──► Slack
        └──► PagerDuty
```

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Django 4.2, Django REST Framework |
| Async / WS | Django Channels 4, Daphne, ASGI |
| Task queue | Celery 5, Celery Beat, Redis 7 |
| ML / detection | PyTorch 2.2, scikit-learn, NumPy |
| Database | PostgreSQL 16 |
| Auth | JWT (djangorestframework-simplejwt) |
| API docs | drf-spectacular (OpenAPI 3, Swagger UI, ReDoc) |
| Observability | Prometheus client, structured JSON logs |
| Frontend | React 18, TypeScript, Recharts, Vite, Tailwind CSS |
| Container | Docker, Docker Compose |

---

## Quick start

### Docker (recommended)

```bash
git clone https://github.com/maryammahmoudi1993/DataPulse.git
cd DataPulse
cp .env.docker .env
docker compose up --build
```

Open http://localhost:3000 and sign in with `demo / demodemo1`.

### Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL and REDIS_URL
python manage.py migrate
python manage.py seed_demo
daphne datapulse.asgi:application &
celery -A datapulse worker -l info &
celery -A datapulse beat   -l info &
cd frontend && npm install && npm run dev
```

### Deployment

Manifests for Render (`render.yaml`), Fly.io (`fly.toml`) and Procfile-based
platforms (`Procfile`) are included. Production settings live in
`datapulse/settings_prod.py` and read every secret from the environment.
`seed_demo` runs on each release so the demo user and stream always exist —
remove it from the build/release command for a real deployment.

---

## API

Interactive docs: http://localhost:8000/api/schema/swagger-ui/

Key endpoints:

```
POST   /api/auth/register/             Register + create workspace
POST   /api/auth/token/                Obtain JWT pair
POST   /api/auth/token/refresh/        Refresh access token
GET    /api/auth/me/                   Current user + workspaces

GET    /api/streams/                   List streams
POST   /api/streams/                   Create stream
PATCH  /api/streams/{id}/              Update config, detector, retention
POST   /api/streams/{id}/pause/        Pause polling
POST   /api/streams/{id}/resume/       Resume polling
POST   /api/streams/{id}/train-lstm/   Trigger async LSTM training
POST   /api/streams/{id}/compare-detectors/  Compare two detector types
POST   /api/streams/{id}/export/       Request CSV export

GET    /api/streams/{id}/alerts/       List alerts (filter: severity, status)
POST   /api/streams/{id}/alerts/{id}/acknowledge/
POST   /api/streams/{id}/alerts/{id}/resolve/

GET    /api/workspaces/{id}/members/   List members
PATCH  /api/workspaces/{id}/members/{user_id}/  Change role
DELETE /api/workspaces/{id}/members/{user_id}/  Remove member
GET    /api/workspaces/{id}/invites/   List pending invites
POST   /api/workspaces/{id}/invites/   Send invite email
GET    /api/workspaces/{id}/audit/     Audit log (owner-only)

POST   /api/integrations/slack/        Configure Slack
POST   /api/integrations/pagerduty/    Configure PagerDuty

WS     /ws/streams/{id}/               Live feed — datapoints + alerts

GET    /health/                        Liveness
GET    /readiness/                     Readiness (DB + Redis)
GET    /metrics/                       Prometheus metrics
```

## GraphQL API

- `POST /graphql/` - queries and mutations
- `ws://.../graphql/` - subscriptions (`graphql-transport-ws`; send `Authorization` in `connection_init`)
- `GET /graphql/` - GraphiQL (only when `DEBUG` is on)

Auth: `Authorization: Bearer <jwt>` or `Authorization: Api-Key dp_live_...`. API keys are read-only
(plus `ingestDataPoint` with the `write:datapoints` scope) and confined to their workspace.
Mutations require the MEMBER or OWNER role; VIEWERs can only read.

Queries: `workspaces`, `streams`, `stream`, `alerts`
Mutations: `createStream`, `setStreamStatus`, `ingestDataPoint`, `acknowledgeAlert`, `resolveAlert`,
`createAnnotation`, `deleteAnnotation`
Subscription: `streamEvents(streamId)` - live data points and alerts

## Detector configuration

Each Stream stores `detector_config` as JSON:

| Type | Key params | Notes |
|---|---|---|
| `ZSCORE` | `window` (60), `threshold` (3.0) | Fastest; good for stable signals |
| `IQR` | `window` (100), `multiplier` (1.5) | Robust to non-normal distributions |
| `LSTM` | `seq_len` (30), `threshold` (2.0) | Needs ≥200 points; train via API |
| `ENSEMBLE` | `members` list with weights | Majority vote across sub-detectors |

Train the LSTM:

```bash
curl -X POST http://localhost:8000/api/streams/1/train-lstm/ \
     -H "Authorization: Bearer <token>"
# Returns {"task_id": "..."} — poll /api/streams/1/training-status/?task_id=...
```

## Workspace model

```
Workspace
├── Streams (1–N)
│   ├── DataPoints (ingested per interval)
│   ├── Alerts (anomaly events)
│   ├── ExportJobs
│   └── WebhookEndpoints
├── Members (UserWorkspace: OWNER / MEMBER / VIEWER)
├── Invites (token-based, 7-day expiry)
├── AuditEvents
├── SlackIntegration (one per workspace)
└── PagerDutyIntegration (one per workspace)
```

## Tests

```bash
pytest --cov=. --cov-report=term-missing -v
```

230+ tests · flake8 clean · OpenAPI schema validated in CI.

## Project structure

```
datapulse/           Django project root (settings, ASGI, Celery)
streams/             Stream and Workspace models, seed_demo command
ingestion/           DataPoint model, Celery polling and cleanup tasks
detection/           BaseDetector, ZScore, IQR, LSTM, Ensemble, factory, comparison
alerts/              Alert model, dedup engine, webhook dispatch
realtime/            Django Channels consumers, Redis publisher
accounts/            User auth, JWT, UserWorkspace, WorkspaceInvite
audit/               AuditEvent model, log_event service
exports/             CSV export jobs and cleanup
reports/             Daily alert digest email
integrations/        Slack and PagerDuty models, notification tasks
api/                 DRF views, serializers, pagination, throttles, health endpoints
frontend/            React 18 + TypeScript dashboard
screenshots/         Playwright screenshot automation
```
