"""Local exception-dispatch fault injection; not HTTP/business test coverage."""
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
baseline = json.loads((ROOT / "config/upstream.json").read_text())["backend"]["commit"]
probe = '''
import django, json
django.setup()
from config.urls import api
from django.test import RequestFactory
from jwt_ninja.errors import APIError
request = RequestFactory().get('/api/user')
results = []
for error, expected in [(APIError('invalid_token', 401), 401),
                        (APIError('invalid_token_type', 400), 400),
                        (RuntimeError('intentional dispatch probe'), 500)]:
    response = api.on_exception(request, error)
    assert response.status_code == expected
    results.append({'exception': type(error).__name__, 'expected': expected,
                    'actual': response.status_code, 'content_type': response['Content-Type']})
print(json.dumps(results))
'''
with tempfile.TemporaryDirectory(prefix="bug001-dispatch-") as directory:
    archive = subprocess.check_output(["git", "-C", str(ROOT / "upstream/backend"), "archive", baseline])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(directory, filter="data")
    subprocess.run(["git", "apply", str(ROOT / "patches/BUG-001.patch")], cwd=directory, check=True)
    result = subprocess.run([str(ROOT / ".venv-backend/bin/python"), "-c", probe], cwd=directory,
                            env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings",
                                 "DEBUG": "True", "DATABASE_URL": ":memory:"},
                            text=True, capture_output=True, check=True, timeout=20)
    print(result.stdout.strip())
