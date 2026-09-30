import math
import random
import time

from sources.base import BaseSourceAdapter


class SimulatorAdapter(BaseSourceAdapter):
    """Generates synthetic readings: a sine wave plus noise and optional spikes.

    Config keys: ``baseline``, ``amplitude`` and ``frequency`` (Hz) shape the
    signal; ``noise_std`` adds Gaussian noise; ``spike_probability`` (alias
    ``spike_prob``) and ``spike_magnitude`` inject outliers.
    """

    def read(self, at=None):
        """Return one reading.

        Args:
            at: Optional POSIX time to evaluate the wave at; defaults to now.

        Returns:
            The simulated value as a float.
        """
        baseline = self.config.get('baseline', 50.0)
        amplitude = self.config.get('amplitude', 0.0)
        frequency = self.config.get('frequency', 0.05)
        noise_std = self.config.get('noise_std', 2.0)
        spike_probability = self.config.get('spike_probability', self.config.get('spike_prob', 0.0))
        spike_magnitude = self.config.get('spike_magnitude', 10.0)

        moment = time.time() if at is None else at
        value = baseline + amplitude * math.sin(2 * math.pi * frequency * moment)
        value += random.gauss(0.0, noise_std)

        if spike_probability and random.random() < spike_probability:
            direction = random.choice([-1, 1])
            value += direction * spike_magnitude * max(noise_std, 1.0)

        return float(value)
