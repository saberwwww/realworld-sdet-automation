from pathlib import Path
import json

import pytest

from tests.support.assertions import user_response
from tests.support.client import ApiClient
from tests.support.data import make_article, make_user
from tests.support.server import isolated_backend


def pytest_addoption(parser):
    parser.addoption("--evidence-dir", default=".runtime/latest")
    parser.addoption("--backend-variant", choices=("baseline", "fixed"), default="fixed")
    parser.addoption("--reverse-order", action="store_true", help="Verify independence in reverse collection order")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--reverse-order"):
        items.reverse()


@pytest.fixture(scope="session")
def backend_environment(pytestconfig):
    # Stage 2 deliberately ignores API_BASE_URL: cannot target an existing user DB.
    with isolated_backend(Path(pytestconfig.getoption("--evidence-dir")).resolve(),
                          pytestconfig.getoption("--backend-variant")) as environment:
        yield environment


@pytest.fixture(scope="session")
def api_url(backend_environment):
    return backend_environment.api_url


@pytest.fixture
def db(backend_environment, request, pytestconfig):
    from tests.support.database import ArticleDatabase
    inspector = ArticleDatabase(backend_environment)
    yield inspector
    out = Path(pytestconfig.getoption("--evidence-dir")) / "database"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{request.node.name}.json").write_text(json.dumps({
        "database": str(inspector.path), "access": "mode=ro; connection per query",
        "nodeid": request.node.nodeid, "queries": inspector.observations,
    }, indent=2) + "\n")


@pytest.fixture
def api(api_url):
    client = ApiClient(api_url)
    yield client
    client.close()


@pytest.fixture
def new_user():
    return make_user()


@pytest.fixture
def user_factory(api):
    def create():
        payload = make_user()
        result = user_response(api.request("POST", "/users", json={"user": payload}), 201, payload)
        return {**payload, "token": result["token"]}
    return create


@pytest.fixture
def owner(user_factory):
    return user_factory()


@pytest.fixture
def article_factory(api, db):
    owned = {}

    def create(user):
        payload = make_article()
        # Register this fixture-created owner before the request can fail.
        owned[user["username"]] = user["token"]
        response = api.request("POST", "/articles", token=user["token"], json={"article": payload})
        return payload, response

    yield create
    errors = []
    for username, token in owned.items():
        # Read current slugs: title updates legitimately change the original slug.
        for row in db.for_author(username):
            try:
                response = api.request("DELETE", f"/articles/{row['slug']}", token=token)
                if response.status_code not in (204, 404):
                    errors.append(f"article {row['id']}: HTTP {response.status_code}")
            except Exception as exc:
                errors.append(f"article {row['id']}: {type(exc).__name__}")
        if db.count_for_author(username) != 0:
            errors.append(f"{username}: persisted articles remain after cleanup")
    assert not errors, "Article teardown failed: " + "; ".join(errors)
