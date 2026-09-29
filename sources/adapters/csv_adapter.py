import csv

from sources.base import BaseSourceAdapter


class CSVAdapter(BaseSourceAdapter):
    """Reads readings from a CSV file, looping back to the start once exhausted."""

    def __init__(self, stream):
        super().__init__(stream)
        self._values = None
        self._index = 0

    def _load(self):
        file_path = self.config.get('file_path')
        column = self.config.get('value_column', 'value')
        values = []
        with open(file_path, newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    values.append(float(row[column]))
                except (KeyError, ValueError):
                    continue
        self._values = values

    def read(self):
        if self._values is None:
            self._load()

        if not self._values:
            raise ValueError('CSV source has no readable values')

        value = self._values[self._index % len(self._values)]
        self._index += 1
        return value
