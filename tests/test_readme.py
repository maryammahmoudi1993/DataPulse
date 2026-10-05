from pathlib import Path

README = (Path(__file__).resolve().parent.parent / 'README.md').read_text(encoding='utf-8')


def test_readme_has_live_demo_section():
    assert 'Live demo' in README


def test_readme_has_architecture_diagram():
    assert 'Celery Beat' in README
    assert 'Django Channels' in README


def test_readme_has_api_reference():
    for endpoint in ['/api/auth/token/', '/api/streams/', '/ws/streams/']:
        assert endpoint in README, f'{endpoint} missing from README'
