"""Deliberately wrong expectation for teaching, NOT a discovered product defect.

Run explicitly: .venv-test/bin/python -m pytest examples/failure_demo.py -v
This self-contained example is excluded from the normal tests/api suite.
"""
import os
from uuid import uuid4

import requests


def test_demo_wrong_registration_status():
    url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
    with requests.Session() as http:
        http.trust_env = False
        response = http.post(
            f"{url}/users",
            json={"user": {"email": "not-an-email", "username": f"demo_{uuid4().hex}",
                           "password": "Local-Sdet-2026!"}},
            timeout=10,
        )
    # Intentional fault: malformed input should be rejected with 422, not 201.
    assert response.status_code == 201
