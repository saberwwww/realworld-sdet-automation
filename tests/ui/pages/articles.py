import re
from playwright.sync_api import expect


class EditorPage:
    def __init__(self, page):
        self.page = page
        self.title = page.get_by_placeholder("Article Title", exact=True)
        self.description = page.get_by_placeholder("What's this article about?", exact=True)
        self.body = page.get_by_placeholder("Write your article (in markdown)", exact=True)

    def fill(self, title, description, body):
        self.title.fill(title)
        self.description.fill(description)
        self.body.fill(body)

    def publish(self, method):
        with self.page.expect_response(lambda r: "/api/articles" in r.url and r.request.method == method) as event:
            self.page.get_by_role("button", name="Publish Article", exact=True).click()
        return event.value

    def expect_error(self, text):
        expect(self.page.locator(".error-messages")).to_contain_text(text)
        expect(self.page.get_by_role("button", name="Publish Article", exact=True)).to_be_enabled()


class ArticlePage:
    def __init__(self, page):
        self.page = page
        # The page deliberately duplicates actions at top and bottom; scope to top banner.
        self.banner = page.locator(".article-page .banner")
        self.content = page.locator(".article-content")

    def expect_content(self, title, body):
        expect(self.page).to_have_url(re.compile(r"/article/[^/?]+$"))
        expect(self.page.get_by_role("heading", name=title, exact=True)).to_be_visible()
        expect(self.content).to_contain_text(body)

    def edit(self):
        self.banner.get_by_role("link", name="Edit Article", exact=True).click()

    def delete(self):
        with self.page.expect_response(lambda r: "/api/articles/" in r.url and r.request.method == "DELETE") as event:
            self.banner.get_by_role("button", name="Delete Article", exact=True).click()
        return event.value
