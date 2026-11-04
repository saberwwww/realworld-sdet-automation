from uuid import uuid4


def make_user():
    suffix = uuid4().hex
    return {"username": f"sdet_{suffix}", "email": f"sdet_{suffix}@example.com",
            "password": "Local-Sdet-2026!"}


def make_article():
    return {"title": f"sdet article {uuid4().hex}", "description": "test summary",
            "body": "test content", "tagList": []}
