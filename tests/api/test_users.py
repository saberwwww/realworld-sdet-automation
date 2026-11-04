import pytest

from tests.support.assertions import error_response, user_response


def test_register_user(api, new_user):
    user_response(api.request("POST", "/users", json={"user": new_user}), 201, new_user)


def test_login_user(api, owner):
    credentials = {key: owner[key] for key in ("email", "password")}
    user = user_response(api.request("POST", "/users/login", json={"user": credentials}), 200, owner)
    user_response(api.request("GET", "/user", token=user["token"]), 200, owner)


@pytest.mark.parametrize("field,value", [("email", "not-an-email"), ("password", None), ("username", None)],
                         ids=["invalid-email", "missing-password", "missing-username"])
def test_register_invalid(api, new_user, field, value):
    if value is None:
        new_user.pop(field)
    else:
        new_user[field] = value
    error_response(api.request("POST", "/users", json={"user": new_user}), 422, field)


@pytest.mark.parametrize("field", ["email", "username"])
def test_register_duplicate(api, owner, new_user, field):
    new_user[field] = owner[field]
    error_response(api.request("POST", "/users", json={"user": new_user}), 409, field)


@pytest.mark.parametrize("scenario", ["wrong-password", "unknown-user"])
def test_login_rejected(api, owner, new_user, scenario):
    credentials = {"email": owner["email"], "password": "definitely-wrong"}
    if scenario == "unknown-user":
        credentials = {key: new_user[key] for key in ("email", "password")}
    error_response(api.request("POST", "/users/login", json={"user": credentials}), 401, "credentials")


@pytest.mark.parametrize("token", [None, "not-a-valid-jwt"], ids=["missing-token", "invalid-token"])
def test_protected_user(api, token):
    error_response(api.request("GET", "/user", token=token), 401, "token")
