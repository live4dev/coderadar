"""
Unit tests for the pure / mockable helper functions in scripts/import_github.py.

Covered:
- _parse_github_url  — pure URL parsing, no network
- _make_session      — header construction, no network
- _paginate          — pagination logic with mocked HTTP responses
"""
import re
from unittest.mock import MagicMock, patch, call

import pytest
import requests

from scripts.import_github import _parse_github_url, _make_session, _paginate


# ---------------------------------------------------------------------------
# _parse_github_url
# ---------------------------------------------------------------------------

class TestParseGitHubUrl:
    def test_https_org_url(self):
        assert _parse_github_url("https://github.com/wemake-services") == "wemake-services"

    def test_https_org_url_trailing_slash(self):
        assert _parse_github_url("https://github.com/wemake-services/") == "wemake-services"

    def test_without_scheme(self):
        assert _parse_github_url("github.com/myorg") == "myorg"

    def test_extra_path_segment_ignored(self):
        # Repo URLs like https://github.com/org/repo — we only need the org part
        assert _parse_github_url("https://github.com/org/repo") == "org"

    def test_wrong_host_raises(self):
        with pytest.raises(ValueError, match="Cannot parse GitHub URL"):
            _parse_github_url("https://gitlab.com/org")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            _parse_github_url("https://github.com/")

    def test_no_path_raises(self):
        with pytest.raises(ValueError):
            _parse_github_url("https://github.com")


# ---------------------------------------------------------------------------
# _make_session
# ---------------------------------------------------------------------------

class TestMakeSession:
    def test_bearer_token_set(self):
        session = _make_session("ghp_secrettoken")
        assert session.headers["Authorization"] == "Bearer ghp_secrettoken"

    def test_github_accept_header(self):
        session = _make_session("token")
        assert session.headers["Accept"] == "application/vnd.github+json"

    def test_api_version_header(self):
        session = _make_session("token")
        assert session.headers["X-GitHub-Api-Version"] == "2022-11-28"

    def test_no_token_no_auth_header(self):
        session = _make_session("")
        assert "Authorization" not in session.headers

    def test_returns_requests_session(self):
        assert isinstance(_make_session("t"), requests.Session)


# ---------------------------------------------------------------------------
# _paginate
# ---------------------------------------------------------------------------

def _mock_response(json_data, link_header="", status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.headers = {"Link": link_header}
    resp.raise_for_status = MagicMock()
    return resp


class TestPaginate:
    def test_single_page_no_link_header(self):
        session = MagicMock()
        session.get.return_value = _mock_response([{"id": 1}, {"id": 2}])

        items = list(_paginate(session, "https://api.github.com/orgs/acme/repos"))

        assert items == [{"id": 1}, {"id": 2}]
        assert session.get.call_count == 1

    def test_two_pages_via_link_header(self):
        page1 = _mock_response(
            [{"id": 1}],
            link_header='<https://api.github.com/orgs/acme/repos?page=2>; rel="next"',
        )
        page2 = _mock_response([{"id": 2}])

        session = MagicMock()
        session.get.side_effect = [page1, page2]

        items = list(_paginate(session, "https://api.github.com/orgs/acme/repos"))

        assert items == [{"id": 1}, {"id": 2}]
        assert session.get.call_count == 2
        # Second request should use the URL from the Link header, no extra params
        second_call_url = session.get.call_args_list[1][0][0]
        assert "page=2" in second_call_url

    def test_three_pages(self):
        page1 = _mock_response(
            [{"id": 1}],
            link_header='<https://api.github.com/repos?page=2>; rel="next", <https://api.github.com/repos?page=3>; rel="last"',
        )
        page2 = _mock_response(
            [{"id": 2}],
            link_header='<https://api.github.com/repos?page=3>; rel="next"',
        )
        page3 = _mock_response([{"id": 3}])

        session = MagicMock()
        session.get.side_effect = [page1, page2, page3]

        items = list(_paginate(session, "https://api.github.com/repos"))
        assert [i["id"] for i in items] == [1, 2, 3]

    def test_empty_page_yields_nothing(self):
        session = MagicMock()
        session.get.return_value = _mock_response([])

        items = list(_paginate(session, "https://api.github.com/repos"))
        assert items == []

    def test_http_error_propagates(self):
        resp = _mock_response(None, status=403)
        resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        session = MagicMock()
        session.get.return_value = resp

        with pytest.raises(requests.HTTPError):
            list(_paginate(session, "https://api.github.com/repos"))
