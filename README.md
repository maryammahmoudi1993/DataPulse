# DataPulse

Real-time anomaly detection pipeline for time-series streams.
Detects statistical outliers and pattern deviations, pushes live
alerts to connected dashboards via WebSocket.

## Architecture

- **Ingestion** — Celery Beat polls configured sources every 5 s
- **Detection** — pluggable detectors: Z-score, IQR, LSTM (PyTorch)
- **Alerts**    — deduplication window, severity routing, webhook dispatch
- **Real-time** — Django Channels + Redis pub/sub → WebSocket push
- **Frontend**  — React + Recharts, live chart and alert feed

## Stack

Python 3.11 · Django 4.2 · Django Channels 4 · Celery 5 · Redis 7
PostgreSQL 16 · PyTorch 2 · scikit-learn · React 18 · Recharts · Vite

## Quick start (Docker)

```bash
docker compose up --build
```

Open `http://localhost:3000` — the dashboard starts with a seeded demo stream.
The Django API is served on `http://localhost:8000`.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in DATABASE_URL and REDIS_URL
python manage.py migrate
python manage.py seed_demo
daphne datapulse.asgi:application &
celery -A datapulse worker -l info &
celery -A datapulse beat   -l info &
cd frontend && npm install && npm run dev
```

Set `CELERY_TASK_ALWAYS_EAGER=False` when running a separate worker; by
default tasks run inline, which suits tests and quick experiments.

## API

| Endpoint | Description |
|---|---|
| `GET/POST /api/streams/` | List and create streams |
| `GET /api/streams/{id}/datapoints/?limit=N` | Latest data points |
| `GET /api/streams/{id}/alerts/?severity=HIGH&status=OPEN` | Filtered alerts |
| `POST /api/streams/{id}/alerts/{alert_id}/acknowledge/` | Acknowledge an alert |
| `GET/POST /api/webhooks/` | Manage webhook endpoints |
| `WS /ws/streams/{id}/` | Live `datapoint` and `alert` events |

Webhook payloads are signed with HMAC-SHA256 in the `X-DataPulse-Signature`
header when the endpoint has a secret.

Setting `DEMO_PUBLIC_ACCESS=True` lets anonymous visitors read (and PATCH)
the `demo` workspace only. It is off by default and enabled in `.env.docker`.

## Tests

```bash
pytest --cov=. --cov-report=term-missing -v
```

## Detector configuration

Each `Stream` stores `detector_config` as JSON:

| Detector | Key params |
|---|---|
| `ZSCORE` | `window` (default 60), `threshold` (default 3.0) |
| `IQR`    | `window` (default 100), `multiplier` (default 1.5) |
| `LSTM`   | `seq_len` (default 30), `threshold` (default 2.0), `model_path` |

To train the LSTM for a stream:

```python
from detection.tasks import train_lstm_for_stream
train_lstm_for_stream.delay(stream_id=1)
```
