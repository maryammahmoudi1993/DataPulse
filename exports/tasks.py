import csv
import logging
import os
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000


@shared_task
def run_export(job_id):
    """Write the CSV file for an export job and record the outcome.

    Args:
        job_id: Primary key of the ExportJob.

    Raises:
        Exception: Any error raised while writing the file, after the job has
            been marked FAILED.
    """
    from exports.models import ExportJob

    try:
        job = ExportJob.objects.select_related('stream').get(pk=job_id)
    except ExportJob.DoesNotExist:
        return

    job.status = ExportJob.STATUS_PROCESSING
    job.save(update_fields=['status'])

    try:
        os.makedirs(settings.EXPORT_ROOT, exist_ok=True)
        file_path = os.path.join(settings.EXPORT_ROOT, f'export_{job_id}.csv')

        if job.export_type == ExportJob.TYPE_DATAPOINTS:
            rows = _export_datapoints(job.stream, file_path)
        else:
            rows = _export_alerts(job.stream, file_path)
    except Exception as e:
        job.status = ExportJob.STATUS_FAILED
        job.error = str(e)
        job.save(update_fields=['status', 'error'])
        logger.exception('Export failed', extra={'job_id': job_id})
        raise

    job.status = ExportJob.STATUS_DONE
    job.file_path = file_path
    job.row_count = rows
    job.completed_at = timezone.now()
    job.save(update_fields=['status', 'file_path', 'row_count', 'completed_at'])


def _export_datapoints(stream, path):
    """Write a stream's data points to ``path`` and return the row count."""
    from ingestion.models import DataPoint

    queryset = DataPoint.objects.filter(stream=stream).order_by('timestamp', 'id')
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'timestamp', 'value'])
        count = 0
        for row in queryset.iterator(chunk_size=CHUNK_SIZE):
            writer.writerow([row.id, row.timestamp.isoformat(), row.value])
            count += 1
    return count


def _export_alerts(stream, path):
    """Write a stream's alerts to ``path`` and return the row count."""
    from alerts.models import Alert

    queryset = Alert.objects.filter(stream=stream).order_by('created_at', 'id')
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'timestamp', 'value', 'anomaly_score', 'severity', 'detector_type', 'status'])
        count = 0
        for row in queryset.iterator(chunk_size=CHUNK_SIZE):
            writer.writerow([
                row.id, row.timestamp.isoformat(), row.value,
                row.anomaly_score, row.severity, row.detector_type, row.status,
            ])
            count += 1
    return count


@shared_task
def cleanup_stale_exports():
    """Delete export files and job records older than ``EXPORT_TTL_HOURS``.

    Returns:
        Number of jobs deleted.
    """
    from exports.models import ExportJob

    cutoff = timezone.now() - timedelta(hours=settings.EXPORT_TTL_HOURS)
    deleted = 0
    for job in ExportJob.objects.filter(created_at__lt=cutoff):
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except OSError as e:
                logger.warning('Could not remove export file %s: %s', job.file_path, e)
        job.delete()
        deleted += 1
    return deleted
