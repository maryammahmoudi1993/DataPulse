import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(shutil.which('docker') is None, reason='docker is not installed')
def test_docker_compose_config_valid():
    """docker-compose.yml is syntactically valid."""
    result = subprocess.run(
        ['docker', 'compose', 'config', '--quiet'],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, f'docker compose config failed:\n{result.stderr}'


@pytest.mark.skipif(shutil.which('npm') is None, reason='npm is not installed')
def test_frontend_builds_cleanly():
    """React frontend builds without TypeScript or Vite errors."""
    result = subprocess.run(
        ['npm', 'run', 'build'],
        capture_output=True, text=True, cwd=os.path.join(ROOT, 'frontend'),
        shell=(os.name == 'nt'),
    )
    assert result.returncode == 0, f'Frontend build failed:\n{result.stderr}\n{result.stdout}'


def test_flake8_clean():
    """Codebase passes flake8 with no errors."""
    result = subprocess.run(
        [sys.executable, '-m', 'flake8', '.'],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, f'Flake8 errors:\n{result.stdout}'
