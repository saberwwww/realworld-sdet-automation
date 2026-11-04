import pytest

from tests.support.assertions import article_response, error_response
from tests.support.data import make_article
from tests.support.database import assert_stored_article


@pytest.mark.db
def test_article_crud(api, owner, user_factory, article_factory, db):
    # Independent author's control row must survive every operation unchanged.
    other = user_factory()
    control_payload, control_response = article_factory(other)
    control = article_response(control_response, 201, control_payload, other["username"])
    control_row = db.by_slug(control["slug"])
    assert_stored_article(control_row, control_payload, control["slug"], other["username"])
    assert db.count_for_author(owner["username"]) == 0

    payload, response = article_factory(owner)
    article = article_response(response, 201, payload, owner["username"])
    row = db.by_slug(article["slug"])
    assert_stored_article(row, payload, article["slug"], owner["username"])
    assert db.count_for_author(owner["username"]) == 1
    original_path = f"/articles/{article['slug']}"
    article_response(api.request("GET", original_path), 200, payload, owner["username"])

    updated = {**payload, "title": payload["title"] + " revised", "body": "edited content", "description": "edited summary"}
    changed = article_response(api.request("PUT", original_path, token=owner["token"],
                               json={"article": {key: updated[key] for key in ("title", "body", "description")}}),
                               200, updated, owner["username"])
    assert changed["slug"] != article["slug"]
    stored = db.by_id(row["id"])
    assert_stored_article(stored, updated, changed["slug"], owner["username"])
    assert stored["id"] == row["id"] and stored["author_id"] == row["author_id"]
    assert stored["created"] == row["created"]
    assert db.by_slug(article["slug"]) is None
    assert db.count_for_author(owner["username"]) == 1  # UPDATE, not INSERT a replacement row.
    assert db.by_id(control_row["id"]) == control_row
    path = f"/articles/{changed['slug']}"
    article_response(api.request("GET", path), 200, updated, owner["username"])
    deleted = api.request("DELETE", path, token=owner["token"])
    assert deleted.status_code == 204 and deleted.content == b""
    assert db.by_id(row["id"]) is None  # Physical deletion, not a guessed soft-delete flag.
    assert db.by_slug(changed["slug"]) is None
    assert db.count_for_author(owner["username"]) == 0
    assert db.by_id(control_row["id"]) == control_row
    error_response(api.request("GET", path), 404, "article")


@pytest.mark.parametrize("field,value", [("title", ""), ("description", None), ("body", None)],
                         ids=["empty-title", "missing-description", "missing-body"])
def test_create_invalid(api, owner, field, value):
    payload = make_article()
    if value is None:
        payload.pop(field)
    else:
        payload[field] = value
    error_response(api.request("POST", "/articles", token=owner["token"], json={"article": payload}), 422, field)


@pytest.mark.db
def test_update_invalid(api, owner, article_factory, db):
    payload, response = article_factory(owner)
    article = article_response(response, 201, payload, owner["username"])
    path = f"/articles/{article['slug']}"
    before = db.by_slug(article["slug"])
    assert before is not None
    error_response(api.request("PUT", path, token=owner["token"], json={"article": {"title": ""}}), 422, "title")
    assert db.by_id(before["id"]) == before
    article_response(api.request("GET", path), 200, payload, owner["username"])


@pytest.mark.parametrize("method", ["POST", "PUT"], ids=["create", "update"])
def test_article_requires_login(api, owner, article_factory, method):
    payload, response = article_factory(owner)
    article = article_response(response, 201, payload, owner["username"])
    path = "/articles" if method == "POST" else f"/articles/{article['slug']}"
    error_response(api.request(method, path, json={"article": make_article()}), 401, "token")
    article_response(api.request("GET", f"/articles/{article['slug']}"), 200, payload, owner["username"])


@pytest.mark.parametrize("method", ["PUT", "DELETE"], ids=["update", "delete"])
@pytest.mark.db
def test_non_owner_forbidden(api, owner, user_factory, article_factory, method, db):
    stranger = user_factory()
    payload, response = article_factory(owner)
    article = article_response(response, 201, payload, owner["username"])
    path = f"/articles/{article['slug']}"
    kwargs = {"json": {"article": {"body": "unauthorized edit"}}} if method == "PUT" else {}
    before = db.by_slug(article["slug"])
    assert before is not None
    error_response(api.request(method, path, token=stranger["token"], **kwargs), 403, "article")
    assert db.by_id(before["id"]) == before
    article_response(api.request("GET", path), 200, payload, owner["username"])
