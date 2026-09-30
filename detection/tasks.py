import os

from celery import shared_task
from django.conf import settings

from streams.models import Stream

from detection.detectors.lstm import train_model

TRAINING_POINT_LIMIT = 5000


@shared_task
def train_lstm_for_stream(stream_id, epochs=20):
    """Train the LSTM forecaster for a stream and register its model path.

    Args:
        stream_id: Primary key of the stream.
        epochs: Training epochs.

    Returns:
        Path of the saved model, or None when the stream does not exist.

    Raises:
        ValueError: If the stream has too little history to train on.
    """
    try:
        stream = Stream.objects.get(pk=stream_id)
    except Stream.DoesNotExist:
        return None

    seq_len = stream.detector_config.get('seq_len', 30)
    rows = stream.data_points.order_by('-timestamp', '-id').values_list('value', flat=True)[:TRAINING_POINT_LIMIT]
    values = list(reversed(list(rows)))

    model_path = os.path.join(settings.LSTM_MODEL_DIR, f'stream_{stream.id}.pt')
    train_model(values, model_path, seq_len=seq_len, epochs=epochs)

    stream.detector_config = {**stream.detector_config, 'model_path': model_path}
    stream.save(update_fields=['detector_config', 'updated_at'])
    return model_path
