"""Explicit stage-4 fault injection; default collection excludes this file."""
from tests.support.assertions import article_response


def test_failure_after_title_change(api, owner, article_factory, db):
    payload, response = article_factory(owner)
    article = article_response(response, 201, payload, owner["username"])
    changed = {**payload, "title": payload["title"] + " renamed before failure"}
    response = api.request("PUT", f"/articles/{article['slug']}", token=owner["token"],
                           json={"article": {"title": changed["title"]}})
    current = article_response(response, 200, changed, owner["username"])
    assert current["slug"] != article["slug"]
    row = db.by_slug(current["slug"])
    assert row is not None
    assert row["title"] == "INTENTIONAL WRONG DATABASE TITLE"  # Fault injection only.
