"""One small HTTP wrapper; no retries that could hide failures."""
import requests


class ApiClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.trust_env = False

    def request(self, method, path, *, token=None, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        if token is not None:
            headers["Authorization"] = f"Token {token}"
        return self.session.request(method, self.base_url + path,
                                    headers=headers, timeout=10, **kwargs)

    def close(self):
        self.session.close()
