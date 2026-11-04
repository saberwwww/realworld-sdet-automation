"""Fault injection only, explicitly collected; never a product bug."""
import pytest
from tests.support.assertions import json_response


def test_reporting_pass(api):
    assert json_response(api.request("GET", "/tags"), 200) == {"tags": []}


def test_reporting_injected_failure(api, owner, article_factory):
    _, response = article_factory(owner)
    json_response(response, 418)  # Deliberate wrong expectation; also exercises teardown.


@pytest.mark.skip(reason="Reporting demo: intentional skip, not unimplemented product coverage")
def test_reporting_skip():
    pass
