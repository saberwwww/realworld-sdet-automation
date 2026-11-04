from playwright.sync_api import expect


class LoginPage:
    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url

    def open(self):
        self.page.goto(self.base_url + "/login")
        expect(self.page.get_by_role("heading", name="Sign in", exact=True)).to_be_visible()

    def submit(self, email, password):
        # Upstream inputs have placeholders, but no accessible <label>.
        self.page.get_by_placeholder("Email", exact=True).fill(email)
        self.page.get_by_placeholder("Password", exact=True).fill(password)
        with self.page.expect_response(lambda r: r.url.endswith("/api/users/login") and r.request.method == "POST") as event:
            self.page.get_by_role("button", name="Sign in", exact=True).click()
        return event.value


class HomePage:
    def __init__(self, page, base_url):
        self.page, self.base_url = page, base_url
        self.nav = page.get_by_role("navigation")

    def expect_logged_in(self, username):
        expect(self.page).to_have_url(self.base_url + "/")
        expect(self.nav.get_by_role("link", name=username, exact=True)).to_be_visible()
        expect(self.nav.get_by_role("link", name="New Article", exact=True)).to_be_visible()
        expect(self.nav.get_by_role("link", name="Sign in", exact=True)).to_have_count(0)
