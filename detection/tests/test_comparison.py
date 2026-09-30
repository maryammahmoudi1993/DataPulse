import datetime
import math
import random

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from detection.comparison import compare_detectors
from ingestion.models import DataPoint
from streams.models import Stream, Workspace


@pytest.fixture
def stream(db):
    owner = get_user_model().objects.create_user('owner', password='x')
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


def _seed(stream, values):
    start = timezone.now() - datetime.timedelta(seconds=5 * len(values))
    DataPoint.objects.bulk_create(
        DataPoint(stream=stream, timestamp=start + datetime.timedelta(seconds=5 * i), value=v)
        for i, v in enumerate(values)
    )


@pytest.fixture
def client(stream):
    client = APIClient()
    client.force_authenticate(user=stream.workspace.owner)
    return client


def test_comparison_returns_agreement_pct(stream):
    rng = random.Random(1)
    _seed(stream, [rng.gauss(50, 2) for _ in range(200)])

    result = compare_detectors(stream, Stream.DETECTOR_ZSCORE, Stream.DETECTOR_IQR)

    assert result['agreement_pct'] > 50
    assert result['total_evaluated'] == 195
    total = result['both_anomaly'] + result['neither_anomaly'] + result['only_a_count'] + result['only_b_count']
    assert total == result['total_evaluated']


def test_comparison_same_detector_rejected(client, stream):
    response = client.post(
        f'/api/streams/{stream.id}/compare-detectors/', {'a': 'ZSCORE', 'b': 'ZSCORE'}, format='json',
    )

    assert response.status_code == 400


def test_comparison_unknown_detector_rejected(client, stream):
    response = client.post(
        f'/api/streams/{stream.id}/compare-detectors/', {'a': 'ZSCORE', 'b': 'MAGIC'}, format='json',
    )

    assert response.status_code == 400


def test_comparison_insufficient_data(client, stream):
    _seed(stream, [1.0, 2.0, 3.0])

    response = client.post(
        f'/api/streams/{stream.id}/compare-detectors/', {'a': 'ZSCORE', 'b': 'IQR'}, format='json',
    )

    assert response.status_code == 422
    assert 'Insufficient data' in response.data['error']


def test_comparison_endpoint_returns_result(client, stream):
    _seed(stream, [10 * math.sin(i * 0.1) for i in range(120)])

    response = client.post(
        f'/api/streams/{stream.id}/compare-detectors/', {'a': 'ZSCORE', 'b': 'IQR'}, format='json',
    )

    assert response.status_code == 200
    assert response.data['detector_a'] == 'ZSCORE'


def test_comparison_agreement_on_identical_signals(stream):
    _seed(stream, [10 * math.sin(i * 0.1) for i in range(300)])

    result = compare_detectors(stream, Stream.DETECTOR_ZSCORE, Stream.DETECTOR_IQR)

    assert result['agreement_pct'] >= 80
