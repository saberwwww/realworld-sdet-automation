import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from tests.support.frontend import local_frontend

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".runtime/pw-browsers"))


@pytest.fixture(scope="session")
def frontend_url(api_url, pytestconfig):
    with local_frontend(api_url, Path(pytestconfig.getoption("--evidence-dir")).resolve()) as url:
        yield url


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1280, "height": 900}, "locale": "en-US"}


@pytest.fixture(autouse=True)
def ui_audit(page, frontend_url, api_url, request, pytestconfig, context_lifecycle):
    context_lifecycle["created"].append(request.node.nodeid)
    page.context.on("close", lambda _: context_lifecycle["closed"].append(request.node.nodeid))
    expect.set_options(timeout=5000)
    allowed = {urlsplit(frontend_url).netloc, urlsplit(api_url).netloc}
    events, console, violations, blocked, failed = [], [], [], [], []

    def guard(route):
        req = route.request
        if urlsplit(req.url).netloc not in allowed:
            blocked.append({"url": req.url, "type": req.resource_type})
            if req.resource_type in ("xhr", "fetch"):
                violations.append(req.url)
            route.abort()
        else:
            route.continue_()

    page.context.route("**/*", guard)
    page.on("response", lambda response: events.append({
        "method": response.request.method, "url": response.url, "status": response.status,
        "type": response.request.resource_type,
    }) if response.request.resource_type in ("xhr", "fetch") else None)
    page.on("requestfailed", lambda req: failed.append({"url": req.url, "failure": req.failure}))
    page.on("pageerror", lambda error: console.append({"type": "pageerror", "message": str(error)}))
    page.on("console", lambda message: console.append({"type": message.type, "message": message.text})
            if message.type == "error" else None)
    # Inspect each newly created context before login: no inherited cookie/storage auth.
    assert page.context.cookies() == []
    page.goto(frontend_url + "/login")
    expect(page.get_by_role("heading", name="Sign in", exact=True)).to_be_visible()
    assert page.evaluate("localStorage.getItem('jwtToken')") is None
    yield
    out = Path(pytestconfig.getoption("--evidence-dir")) / "browser"
    out.mkdir(parents=True, exist_ok=True)
    name = request.node.name.replace("/", "_")
    (out / f"{name}.json").write_text(json.dumps({
        "nodeid": request.node.nodeid, "api_url": api_url, "frontend_url": frontend_url,
        "started_without_auth": True, "responses": events, "console": console,
        "foreign_api_requests": violations, "blocked_external_assets": blocked, "failed_requests": failed,
    }, indent=2) + "\n")
    assert not violations, f"Browser tried non-local API: {violations}"


@pytest.fixture(scope="session")
def context_lifecycle():
    return {"created": [], "closed": []}


@pytest.fixture(scope="session")
def browser(browser, pytestconfig, context_lifecycle):
    import subprocess
    version = browser.version
    yield browser
    contexts_before_close = len(browser.contexts)
    browser.close()
    rows = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True).splitlines()
    remaining = [int(row.strip().split(None, 1)[0]) for row in rows
                 if row.strip().split(None, 1)[1].startswith(str(ROOT / ".runtime/pw-browsers"))]
    report = {**context_lifecycle, "chromium_version": version,
              "contexts_before_browser_close": contexts_before_close,
              "browser_disconnected": not browser.is_connected(),
              "remaining_chromium_pids": remaining}
    out = Path(pytestconfig.getoption("--evidence-dir"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "browser-lifecycle.json").write_text(json.dumps(report, indent=2) + "\n")
    assert contexts_before_close == 0
    assert context_lifecycle["created"] == context_lifecycle["closed"]
    assert not remaining


@pytest.fixture(scope="session")
def base_url(frontend_url):
    # Explicit plugin extension point; avoids its fallback bound-method warning on pytest 9.2.
    return frontend_url


@pytest.fixture
def ui_user(owner, api, request, pytestconfig):
    """API registration is preparation; browser login stays a UI action."""
    yield owner
    response = api.request("GET", "/articles", params={"author": owner["username"], "limit": 100})
    assert response.status_code == 200, "Could not enumerate this test user's articles for cleanup"
    data = response.json()
    assert data["articlesCount"] <= 100, "Unexpected resource count; refusing unbounded cleanup"
    deleted = []
    for article in data["articles"]:
        assert article["author"]["username"] == owner["username"]
        result = api.request("DELETE", f"/articles/{article['slug']}", token=owner["token"])
        assert result.status_code in (204, 404), "UI article cleanup failed"
        deleted.append(article["slug"])
    remaining = api.request("GET", "/articles", params={"author": owner["username"]})
    assert remaining.status_code == 200 and remaining.json()["articlesCount"] == 0
    out = Path(pytestconfig.getoption("--evidence-dir")) / "ui-cleanup"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{request.node.name}.json").write_text(json.dumps({
        "username": owner["username"], "deleted_articles": deleted, "remaining_articles": 0,
    }, indent=2) + "\n")


@pytest.fixture
def logged_in(page, frontend_url, api_url, ui_user):
    from tests.ui.pages.auth import HomePage, LoginPage
    result = LoginPage(page, frontend_url).submit(ui_user["email"], ui_user["password"])
    assert result.url == api_url + "/users/login" and result.status == 200
    HomePage(page, frontend_url).expect_logged_in(ui_user["username"])
    return ui_user


@pytest.fixture
def prepared_article(api, ui_user):
    from tests.support.data import make_article
    from tests.support.assertions import article_response
    payload = make_article()
    response = api.request("POST", "/articles", token=ui_user["token"], json={"article": payload})
    article = article_response(response, 201, payload, ui_user["username"])
    return article
