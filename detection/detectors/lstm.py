import os

import numpy as np

from detection.base import BaseDetector, DetectionResult

_MODEL_CACHE = {}


def _build_model(hidden_size):
    """Create the next-value prediction network."""
    import torch.nn as nn

    class Forecaster(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=hidden_size, batch_first=True)
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    return Forecaster()


def train_model(values, model_path, seq_len=30, hidden_size=16, epochs=20):
    """Train a forecaster on a value series and save it to disk.

    Args:
        values: Sequence of floats, at least ``seq_len + 10`` long.
        model_path: Destination of the checkpoint file.
        seq_len: Number of past points used to predict the next one.
        hidden_size: LSTM hidden units.
        epochs: Training epochs.

    Returns:
        Dict with the training ``error_std`` and sample count.

    Raises:
        ValueError: If there is not enough data to train.
    """
    import torch

    data = np.asarray(values, dtype=np.float32)
    if len(data) < seq_len + 10:
        raise ValueError(f'Need at least {seq_len + 10} points to train, got {len(data)}')

    mean, std = float(data.mean()), float(data.std()) or 1.0
    norm = (data - mean) / std
    windows = np.stack([norm[i:i + seq_len] for i in range(len(norm) - seq_len)])
    targets = norm[seq_len:]
    x = torch.from_numpy(windows).unsqueeze(-1)
    y = torch.from_numpy(targets)

    torch.manual_seed(0)
    model = _build_model(hidden_size)
    optimiser = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = torch.nn.MSELoss()
    for _ in range(epochs):
        optimiser.zero_grad()
        loss = loss_fn(model(x), y)
        loss.backward()
        optimiser.step()

    with torch.no_grad():
        residuals = (model(x) - y).numpy()
    error_std = float(residuals.std()) or 1e-6

    os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
    torch.save({
        'state': model.state_dict(),
        'mean': mean,
        'std': std,
        'error_std': error_std,
        'seq_len': seq_len,
        'hidden_size': hidden_size,
    }, model_path)
    _MODEL_CACHE.pop(model_path, None)
    return {'error_std': error_std, 'samples': len(x)}


def _load_model(model_path):
    """Load a checkpoint, caching by file modification time."""
    import torch

    mtime = os.path.getmtime(model_path)
    cached = _MODEL_CACHE.get(model_path)
    if cached and cached[0] == mtime:
        return cached[1]

    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    model = _build_model(checkpoint['hidden_size'])
    model.load_state_dict(checkpoint['state'])
    model.eval()
    _MODEL_CACHE[model_path] = (mtime, (model, checkpoint))
    return model, checkpoint


class LSTMDetector(BaseDetector):
    """Flags values that the trained forecaster failed to predict.

    Config keys: ``seq_len`` (default 30), ``threshold`` (default 2.0, in
    forecast-error standard deviations) and ``model_path``. Without a trained
    model the detector never fires.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.seq_len = self.config.get('seq_len', 30)
        self.threshold = self.config.get('threshold', 2.0)
        self.model_path = self.config.get('model_path')
        self._window = None
        self._loaded = None

    def fit(self, history):
        self._window = None
        self._loaded = None
        if not self.model_path or not os.path.exists(self.model_path):
            return
        if len(history) < self.seq_len:
            return
        self._loaded = _load_model(self.model_path)
        self._window = np.asarray(list(history)[-self.seq_len:], dtype=np.float32)

    def detect(self, value):
        if self._loaded is None or self._window is None:
            return DetectionResult(
                is_anomaly=False,
                score=0.0,
                severity=self.SEVERITY_LOW,
                value=value,
            )

        import torch

        model, checkpoint = self._loaded
        norm = (self._window - checkpoint['mean']) / checkpoint['std']
        with torch.no_grad():
            predicted = float(model(torch.from_numpy(norm).view(1, -1, 1)))
        actual = (value - checkpoint['mean']) / checkpoint['std']
        score = abs(actual - predicted) / checkpoint['error_std']

        return DetectionResult(
            is_anomaly=score >= self.threshold,
            score=score,
            severity=self._classify_severity(score),
            value=value,
        )
