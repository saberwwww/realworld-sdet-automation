"""Status from RealWorld contract; exact error codes from the local patch design."""
import base64
import json
from pathlib import Path
import subprocess

import pytest

from tests.support.assertions import error_response, user_response

ROOT = Path(__file__).resolve().parents[2]


def tamper_signature(token):
    header, payload, signature = token.split(".")
    raw = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    changed = bytes([raw[0] ^ 1]) + raw[1:]
    signature = base64.urlsafe_b64encode(changed).decode().rstrip("=")
    return f"{header}.{payload}.{signature}"


def expired_token(token):
    result = subprocess.run(
        [str(ROOT / ".venv-backend/bin/python"), str(ROOT / "tests/support/mint_expired.py")],
        cwd=ROOT / "upstream/backend", input=token, text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, "Expired-token helper failed; no credential output logged"
    proof = json.loads(result.stdout)
    assert proof["original_signature_verified"] is True
    assert proof["rejection"] == "ExpiredSignatureError"
    return proof["token"]


@pytest.mark.parametrize("scenario,expected", [
    ("missing", "is missing"),
    ("invalid", "invalid_token"),
    ("malformed-header", "is missing"),
    ("malformed-jwt", "invalid_token"),
    ("tampered-signature", "invalid_token"),
    ("expired", "expired_token"),
    ("valid", None),
])
def test_auth_boundary(api, owner, scenario, expected):
    # Control: the source token and user/session are really usable before mutation.
    user_response(api.request("GET", "/user", token=owner["token"]), 200, owner)
    kwargs = {}
    if scenario == "invalid":
        kwargs["token"] = "eyJhbGciOiJIUzI1NiJ9.e30.AAAA"
    elif scenario == "malformed-header":
        kwargs["headers"] = {"Authorization": "Basic not-a-real-credential"}
    elif scenario == "malformed-jwt":
        kwargs["token"] = "only.two"
    elif scenario == "tampered-signature":
        kwargs["token"] = tamper_signature(owner["token"])
    elif scenario == "expired":
        kwargs["token"] = expired_token(owner["token"])
    elif scenario == "valid":
        kwargs["token"] = owner["token"]
    response = api.request("GET", "/user", **kwargs)
    if scenario == "valid":
        user_response(response, 200, owner)
    else:
        body = error_response(response, 401, "token")
        assert body["errors"]["token"] == [expected]
