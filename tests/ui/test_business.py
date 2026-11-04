import pytest
from playwright.sync_api import expect
from tests.support.database import assert_stored_article

from tests.support.data import make_article
from tests.ui.pages.auth import HomePage, LoginPage
from tests.ui.pages.articles import ArticlePage, EditorPage


def test_login_success(page, frontend_url, api_url, ui_user):
    login = LoginPage(page, frontend_url)
    login.open()
    response = login.submit(ui_user["email"], ui_user["password"])
    assert response.url == api_url + "/users/login"
    assert response.status == 200
    HomePage(page, frontend_url).expect_logged_in(ui_user["username"])
    page.reload()
    HomePage(page, frontend_url).expect_logged_in(ui_user["username"])


def test_login_wrong_password(page, frontend_url, ui_user):
    response = LoginPage(page, frontend_url).submit(ui_user["email"], "definitely-wrong")
    assert response.status == 401
    expect(page.locator(".error-messages")).to_contain_text("credentials invalid")
    expect(page).to_have_url(frontend_url + "/login")
    expect(page.get_by_role("navigation").get_by_role("link", name="New Article", exact=True)).to_have_count(0)


def test_logout(page, frontend_url, logged_in):
    page.get_by_role("navigation").get_by_role("link", name="Settings", exact=True).click()
    expect(page.get_by_role("heading", name="Your Settings", exact=True)).to_be_visible()
    page.get_by_role("button", name="Or click here to logout.", exact=True).click()
    expect(page).to_have_url(frontend_url + "/")
    expect(page.get_by_role("navigation").get_by_role("link", name="Sign in", exact=True)).to_be_visible()
    expect(page.get_by_role("navigation").get_by_role("link", name=logged_in["username"], exact=True)).to_have_count(0)
    page.goto(frontend_url + "/settings")
    expect(page).to_have_url(frontend_url + "/login")


def test_publish_article(page, logged_in):
    payload = make_article()
    page.get_by_role("navigation").get_by_role("link", name="New Article", exact=True).click()
    editor = EditorPage(page)
    editor.fill(payload["title"], payload["description"], payload["body"])
    assert editor.publish("POST").status == 201
    article = ArticlePage(page)
    article.expect_content(payload["title"], payload["body"])
    page.reload()
    article.expect_content(payload["title"], payload["body"])


@pytest.mark.db
def test_edit_article(page, frontend_url, logged_in, prepared_article, db):
    before = db.by_slug(prepared_article["slug"])
    assert_stored_article(before, prepared_article, prepared_article["slug"], logged_in["username"])
    page.goto(frontend_url + "/article/" + prepared_article["slug"])
    article = ArticlePage(page)
    article.expect_content(prepared_article["title"], prepared_article["body"])
    article.edit()
    editor = EditorPage(page)
    expect(editor.body).to_have_value(prepared_article["body"])
    editor.body.fill("Updated by the real browser")
    assert editor.publish("PUT").status == 200
    article.expect_content(prepared_article["title"], "Updated by the real browser")
    page.reload()
    article.expect_content(prepared_article["title"], "Updated by the real browser")
    expect(article.content).not_to_contain_text(prepared_article["body"])
    stored = db.by_id(before["id"])
    assert_stored_article(stored, {**prepared_article, "body": "Updated by the real browser"},
                          prepared_article["slug"], logged_in["username"])
    assert stored["author_id"] == before["author_id"] and stored["created"] == before["created"]
    assert db.count_for_author(logged_in["username"]) == 1


def test_delete_article(page, frontend_url, logged_in, prepared_article, api):
    page.goto(frontend_url + "/article/" + prepared_article["slug"])
    article = ArticlePage(page)
    article.expect_content(prepared_article["title"], prepared_article["body"])
    assert article.delete().status == 204
    expect(page).to_have_url(frontend_url + "/")
    page.reload()
    expect(page.get_by_text("No articles are here... yet.", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name=prepared_article["title"], exact=True)).to_have_count(0)
    # Supplemental API assertion, after UI deletion and visible feed verification.
    assert api.request("GET", "/articles/" + prepared_article["slug"]).status_code == 404


def test_guest_editor_redirect(page, frontend_url):
    page.goto(frontend_url + "/editor")
    expect(page).to_have_url(frontend_url + "/login")
    expect(page.get_by_role("heading", name="Sign in", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Publish Article", exact=True)).to_have_count(0)


def test_publish_empty_title(page, frontend_url, logged_in):
    page.get_by_role("navigation").get_by_role("link", name="New Article", exact=True).click()
    editor = EditorPage(page)
    editor.fill("", "Valid description", "Valid body")
    assert editor.publish("POST").status == 422
    editor.expect_error("can't be blank")
    expect(page.locator(".error-messages")).to_contain_text("title")
    expect(page).to_have_url(frontend_url + "/editor")
    expect(editor.body).to_have_value("Valid body")
