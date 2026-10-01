from prometheus_client import Counter, Gauge, Histogram

datapoints_ingested = Counter(
    'datapulse_datapoints_ingested_total',
    'Total data points ingested',
    ['stream_id'],
)

anomalies_detected = Counter(
    'datapulse_anomalies_detected_total',
    'Total anomalies detected',
    ['severity', 'detector_type'],
)

detection_latency = Histogram(
    'datapulse_detection_latency_seconds',
    'Time spent running anomaly detection',
    ['detector_type'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

alerts_created = Counter(
    'datapulse_alerts_created_total',
    'Total root alerts created (after dedup)',
    ['severity'],
)

active_streams = Gauge(
    'datapulse_active_streams',
    'Number of streams with status ACTIVE',
)

webhooks_dispatched = Counter(
    'datapulse_webhooks_dispatched_total',
    'Total webhook POST calls made',
    ['status'],
)
