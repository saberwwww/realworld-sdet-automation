"""Explicit-only framework fault injection; never counted as a product bug."""
from playwright.sync_api import expect
from tests.ui.pages.articles import ArticlePage, EditorPage


def test_injected_wrong_title(page, logged_in):
    page.get_by_role("navigation").get_by_role("link", name="New Article", exact=True).click()
    editor = EditorPage(page)
    editor.fill("Diagnostic article - real browser", "Disposable diagnostic data", "Published before the intentional failure.")
    assert editor.publish("POST").status == 201
    ArticlePage(page).expect_content("Diagnostic article - real browser", "Published before the intentional failure.")
    # Deliberately false oracle: saves screenshot/trace and still cleans this article.
    expect(page.get_by_role("heading", name="INTENTIONAL WRONG TITLE", exact=True)).to_be_visible(timeout=1000)
