import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_settings_prod_importable():
    """settings_prod.py imports without error when SECRET_KEY is set."""
    env = {**os.environ, 'SECRET_KEY': 'test-secret', 'ALLOWED_HOSTS': 'localhost'}
    result = subprocess.run(
        [sys.executable, '-c', 'import datapulse.settings_prod as s; assert s.DEBUG is False'],
        env=env, cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_env_example_has_required_keys():
    """Every key the deployment depends on is documented in .env.example."""
    required = [
        'DATABASE_URL', 'REDIS_URL', 'SECRET_KEY',
        'SMTP_USER', 'INVITE_BASE_URL', 'EXPORT_ROOT',
    ]
    content = (ROOT / '.env.example').read_text()
    for key in required:
        assert key in content, f'{key} missing from .env.example'


def test_render_yaml_present():
    assert (ROOT / 'render.yaml').exists(), 'render.yaml missing'


def test_procfile_has_three_processes():
    lines = [ln for ln in (ROOT / 'Procfile').read_text().splitlines() if ln.strip()]
    processes = {ln.split(':')[0] for ln in lines}
    assert {'web', 'worker', 'beat'}.issubset(processes)
