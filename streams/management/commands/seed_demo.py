import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ingestion.models import DataPoint
from sources.adapters.simulator import SimulatorAdapter
from streams.models import Stream, Workspace

STEP_SECONDS = 5


class Command(BaseCommand):
    help = 'Seeds the database with a demo workspace and synthetic time-series data.'

    def add_arguments(self, parser):
        parser.add_argument('--points', type=int, default=500,
                            help='Number of historical data points to generate')
        parser.add_argument('--flush', action='store_true',
                            help='Delete existing demo data before seeding')

    def handle(self, *args, **options):
        slug = settings.DEMO_WORKSPACE_SLUG
        if options['flush']:
            Workspace.objects.filter(slug=slug).delete()
            self.stdout.write('Existing demo data removed.')

        workspace, _ = Workspace.objects.get_or_create(
            slug=slug,
            defaults={'name': 'Demo Workspace'},
        )

        stream, created = Stream.objects.get_or_create(
            workspace=workspace,
            name='Sensor Alpha',
            defaults={
                'source_type': Stream.SOURCE_SIMULATOR,
                'source_config': {
                    'baseline': 0.0,
                    'amplitude': 10.0,
                    'frequency': 0.05,
                    'noise_std': 0.8,
                    'spike_prob': 0.04,
                    'spike_magnitude': 4.0,
                },
                'sampling_interval': STEP_SECONDS,
                'detector_type': Stream.DETECTOR_ZSCORE,
                'detector_config': {'window': 60, 'threshold': 3.0},
            },
        )
        if created:
            self.stdout.write(f'Stream created: {stream}')

        adapter = SimulatorAdapter(stream)
        count = options['points']
        now = timezone.now()
        points = []
        for i in range(count):
            moment = now - datetime.timedelta(seconds=(count - i) * STEP_SECONDS)
            points.append(DataPoint(
                stream=stream,
                timestamp=moment,
                value=adapter.read(at=moment.timestamp()),
            ))
        DataPoint.objects.bulk_create(points)

        self.stdout.write(
            self.style.SUCCESS(f'Seeded {count} data points for stream "{stream.name}".')
        )
        self.stdout.write(f'Stream ID: {stream.id}  (use in frontend: WS /ws/streams/{stream.id}/)')
