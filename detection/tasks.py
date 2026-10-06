import logging
import os

from celery import shared_task
from django.conf import settings

from api.cache_keys import invalidate_workspace_stream_cache
from streams.models import Stream

from detection.detectors.lstm import train_model

logger = logging.getLogger(__name__)

TRAINING_POINT_LIMIT = 5000
MIN_TRAINING_POINTS = 200


@shared_task(bind=True, name='detection.train_lstm_for_stream')
def train_lstm_for_stream(self, stream_id, epochs=20):
    """Train the LSTM forecaster for a stream and register its model path.

    Progress is published through Celery task state so the API can report it.

    Args:
        stream_id: Primary key of the stream.
        epochs: Training epochs.

    Returns:
        Dict with ``status`` (``ok``, ``skipped`` or ``missing``). A successful
        run also carries the model ``path`` and the training ``samples``.
    """
    try:
        stream = Stream.objects.get(pk=stream_id)
    except Stream.DoesNotExist:
        return {'status': 'missing', 'reason': 'stream not found'}

    _report(self, 'loading data', 0)
    seq_len = stream.detector_config.get('seq_len', 30)
    rows = stream.data_points.order_by('-timestamp', '-id').values_list('value', flat=True)[:TRAINING_POINT_LIMIT]
    values = list(reversed(list(rows)))

    if len(values) < MIN_TRAINING_POINTS:
        logger.info('LSTM training skipped', extra={'stream_id': stream.id, 'task': self.name})
        return {
            'status': 'skipped',
            'reason': f'need at least {MIN_TRAINING_POINTS} points, got {len(values)}',
        }

    _report(self, 'training', 50)
    model_path = os.path.join(settings.LSTM_MODEL_DIR, f'stream_{stream.id}.pt')
    stats = train_model(values, model_path, seq_len=seq_len, epochs=epochs)

    stream.detector_config = {**stream.detector_config, 'model_path': model_path}
    stream.save(update_fields=['detector_config', 'updated_at'])
    invalidate_workspace_stream_cache(stream.workspace)
    logger.info('LSTM training complete', extra={'stream_id': stream.id, 'task': self.name})
    return {'status': 'ok', 'path': model_path, 'samples': stats['samples']}


def _report(task, step, pct):
    """Publish progress unless the task is being called outside a worker."""
    if task.request.id and not task.request.called_directly:
        task.update_state(state='PROGRESS', meta={'step': step, 'pct': pct})
