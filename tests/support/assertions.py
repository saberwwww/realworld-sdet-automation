"""Contract assertions without printing passwords or access tokens."""
def json_response(response, status):
    assert response.status_code == status, (
        f"{response.request.method} {response.request.url}: "
        f"expected HTTP {status}, got {response.status_code}; "
        f"content-type={response.headers.get('Content-Type')}"
    )
    assert response.headers.get("Content-Type", "").startswith("application/json")
    body = response.json()
    assert isinstance(body, dict)
    return body


def error_response(response, status, field):
    body = json_response(response, status)
    assert isinstance(body.get("errors"), dict), "missing errors object"
    messages = body["errors"].get(field)
    assert isinstance(messages, list) and messages, f"missing errors.{field}"
    assert all(isinstance(value, str) and value for value in messages)
    assert "user" not in body and "article" not in body
    return body


def user_response(response, status, expected):
    body = json_response(response, status)
    user = body.get("user")
    assert isinstance(user, dict)
    assert {"username", "email", "token", "bio", "image"} <= user.keys()
    for key in ("username", "email"):
        assert user[key] == expected[key]
    assert isinstance(user["token"], str) and user["token"]
    assert "password" not in user
    return user


def article_response(response, status, expected, author):
    article = json_response(response, status).get("article")
    assert isinstance(article, dict)
    for key in ("title", "description", "body", "tagList"):
        assert article[key] == expected[key], f"article.{key} mismatch"
    assert isinstance(article["slug"], str) and article["slug"]
    assert isinstance(article["author"], dict)
    assert article["author"]["username"] == author
    assert isinstance(article["favorited"], bool)
    assert type(article["favoritesCount"]) is int
    assert article["favoritesCount"] == 0
    for key in ("createdAt", "updatedAt"):
        assert isinstance(article[key], str) and article[key]
    return article
