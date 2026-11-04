"""Local test-only helper. Read a token on stdin; never print signing keys.

Run with backend's venv from upstream/backend, not the requests test venv.
No database operations: keep the real token's user/session claims unchanged.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DEBUG"] = "True"
os.environ["DATABASE_URL"] = ":memory:"
import django

django.setup()
import jwt
from jwt_ninja.settings import jwt_settings

original = sys.stdin.read().strip()
claims = jwt.decode(original, jwt_settings.SECRET_KEY, algorithms=[jwt_settings.ALGORITHM],
                    options={"require": ["exp"]})
claims["exp"] = int(time.time()) - 60
expired = jwt.encode(claims, jwt_settings.SECRET_KEY, algorithm=jwt_settings.ALGORITHM)
try:
    jwt.decode(expired, jwt_settings.SECRET_KEY, algorithms=[jwt_settings.ALGORITHM])
except jwt.ExpiredSignatureError:
    print(json.dumps({"token": expired, "original_signature_verified": True,
                      "rejection": "ExpiredSignatureError"}))
else:
    raise AssertionError("Expired token construction failed")
