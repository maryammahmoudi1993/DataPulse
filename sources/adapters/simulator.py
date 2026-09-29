import random

from sources.base import BaseSourceAdapter


class SimulatorAdapter(BaseSourceAdapter):
    """Generates synthetic readings around a baseline, with optional spikes."""

    def read(self):
        baseline = self.config.get('baseline', 50.0)
        noise_std = self.config.get('noise_std', 2.0)
        spike_probability = self.config.get('spike_probability', 0.0)
        spike_magnitude = self.config.get('spike_magnitude', 10.0)

        value = random.gauss(baseline, noise_std)

        if spike_probability and random.random() < spike_probability:
            direction = random.choice([-1, 1])
            value += direction * spike_magnitude * max(noise_std, 1.0)

        return float(value)
