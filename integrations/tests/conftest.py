import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from alerts.models import Alert
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(name='W', slug='w', owner=owner)


@pytest.fixture
def stream(workspace):
    return Stream.objects.create(
        workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR,
        detector_type=Stream.DETECTOR_ZSCORE,
    )


@pytest.fixture
def make_alert(stream):
    def _make(severity='HIGH'):
        return Alert.objects.create(
            stream=stream, timestamp=timezone.now(), value=42.0, anomaly_score=4.0,
            severity=severity, detector_type='ZSCORE',
        )
    return _make
