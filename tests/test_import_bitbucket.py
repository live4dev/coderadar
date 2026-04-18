"""
Unit tests for the pure / mockable helper functions in scripts/import_bitbucket.py.

Covered:
- _make_session         — header construction (Bearer token, Basic auth, anonymous)
- _http_clone_url       — extracts HTTP clone URL from a Bitbucket repo dict
- _paginate             — pagination logic (isLastPage / nextPageStart) with mocked HTTP
- _get_default_branch   — default-branch lookup with mocked HTTP (ok / error / exception)
"""
import base64
from unittest.mock import MagicMock

import pytest
import requests

from scripts.import_bitbucket import (
    _make_session,
    _http_clone_url,
    _paginate,
    _get_default_branch,
)


# ---------------------------------------------------------------------------
# _make_session
# ---------------------------------------------------------------------------

class TestMakeSession:
    def test_bearer_token(self):
        session = _make_session(token="mytoken", username=None, password=None)
        assert session.headers["Authorization"] == "Bearer mytoken"

    def test_basic_auth(self):
        session = _make_session(token=None, username="alice", password="s3cr3t")
        expected = "Basic " + base64.b64encode(b"alice:s3cr3t").decode()
        assert session.headers["Authorization"] == expected

    def test_token_takes_precedence_over_basic(self):
        # When both are supplied, token wins
        session = _make_session(token="tok", username="alice", password="pass")
        assert session.headers["Authorization"] == "Bearer tok"

    def test_no_credentials_no_auth_header(self):
        session = _make_session(token=None, username=None, password=None)
        assert "Authorization" not in session.headers

    def test_accept_header_is_json(self):
        session = _make_session(token="t", username=None, password=None)
        assert session.headers["Accept"] == "application/json"

    def test_returns_requests_session(self):
        assert isinstance(_make_session(None, None, None), requests.Session)


# ---------------------------------------------------------------------------
# _http_clone_url
# ---------------------------------------------------------------------------

class TestHttpCloneUrl:
    def _repo(self, clone_links):
        return {"links": {"clone": clone_links}}

    def test_returns_http_href(self):
        repo = self._repo([
            {"name": "ssh", "href": "ssh://git@bitbucket.example.com/proj/repo.git"},
            {"name": "http", "href": "https://bitbucket.example.com/scm/proj/repo.git"},
        ])
        assert _http_clone_url(repo) == "https://bitbucket.example.com/scm/proj/repo.git"

    def test_returns_none_when_no_http_link(self):
        repo = self._repo([{"name": "ssh", "href": "ssh://git@bb/proj/repo.git"}])
        assert _http_clone_url(repo) is None

    def test_returns_none_for_empty_clone_list(self):
        assert _http_clone_url(self._repo([])) is None

    def test_returns_none_when_links_key_missing(self):
        assert _http_clone_url({}) is None

    def test_returns_first_http_link_when_multiple(self):
        repo = self._repo([
            {"name": "http", "href": "https://first.example.com/repo.git"},
            {"name": "http", "href": "https://second.example.com/repo.git"},
        ])
        assert _http_clone_url(repo) == "https://first.example.com/repo.git"


# ---------------------------------------------------------------------------
# _paginate
# ---------------------------------------------------------------------------

def _mock_response(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestPaginate:
    def test_single_page(self):
        session = MagicMock()
        session.get.return_value = _mock_response({
            "values": [{"slug": "repo1"}, {"slug": "repo2"}],
            "isLastPage": True,
        })

        items = list(_paginate(session, "https://bb.example.com/rest/api/1.0/projects"))
        assert [i["slug"] for i in items] == ["repo1", "repo2"]
        assert session.get.call_count == 1

    def test_two_pages(self):
        session = MagicMock()
        session.get.side_effect = [
            _mock_response({"values": [{"slug": "a"}], "isLastPage": False, "nextPageStart": 1}),
            _mock_response({"values": [{"slug": "b"}], "isLastPage": True}),
        ]

        items = list(_paginate(session, "https://bb.example.com/rest/api/1.0/projects"))
        assert [i["slug"] for i in items] == ["a", "b"]
        assert session.get.call_count == 2

    def test_second_request_uses_next_page_start(self):
        session = MagicMock()
        session.get.side_effect = [
            _mock_response({"values": [{"slug": "a"}], "isLastPage": False, "nextPageStart": 100}),
            _mock_response({"values": [{"slug": "b"}], "isLastPage": True}),
        ]

        list(_paginate(session, "https://bb.example.com/rest/api/1.0/projects"))

        _, second_kwargs = session.get.call_args_list[1]
        assert second_kwargs["params"]["start"] == 100

    def test_empty_values(self):
        session = MagicMock()
        session.get.return_value = _mock_response({"values": [], "isLastPage": True})

        items = list(_paginate(session, "https://bb.example.com/rest/api/1.0/projects"))
        assert items == []

    def test_http_error_propagates(self):
        resp = _mock_response(None, status=401)
        resp.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")

        session = MagicMock()
        session.get.return_value = resp

        with pytest.raises(requests.HTTPError):
            list(_paginate(session, "https://bb.example.com/rest/api/1.0/projects"))


# ---------------------------------------------------------------------------
# _get_default_branch
# ---------------------------------------------------------------------------

class TestGetDefaultBranch:
    def test_returns_display_id_on_success(self):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"displayId": "develop", "id": "refs/heads/develop"}

        session = MagicMock()
        session.get.return_value = resp

        result = _get_default_branch(session, "https://bb.example.com", "PROJ", "myrepo")
        assert result == "develop"

    def test_returns_none_on_non_ok_response(self):
        resp = MagicMock()
        resp.ok = False

        session = MagicMock()
        session.get.return_value = resp

        result = _get_default_branch(session, "https://bb.example.com", "PROJ", "myrepo")
        assert result is None

    def test_returns_none_on_network_exception(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("timeout")

        result = _get_default_branch(session, "https://bb.example.com", "PROJ", "myrepo")
        assert result is None

    def test_calls_correct_url(self):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"displayId": "main"}

        session = MagicMock()
        session.get.return_value = resp

        _get_default_branch(session, "https://bb.example.com", "MYPROJ", "myrepo")

        called_url = session.get.call_args[0][0]
        assert "MYPROJ" in called_url
        assert "myrepo" in called_url
        assert "default-branch" in called_url
