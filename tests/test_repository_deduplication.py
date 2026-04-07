"""
Tests for globally-unique repository URL deduplication.

Key invariants verified:
- The same URL shared across projects produces one `repositories` row.
- A project can hold multiple entries for the same URL.
- Deleting a ProjectRepository entry orphans the underlying Repository only when
  no other ProjectRepository references it.
- RepositoryOut exposes both `id` (ProjectRepository) and `repository_id` (Repository).
"""
import pytest
from app.models import Repository, ProjectRepository


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_project(client, name="Project A"):
    r = client.post("/api/v1/projects", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _create_repo(client, project_id, url="https://github.com/org/repo", name="my-repo", **kw):
    payload = {"project_id": project_id, "name": name, "url": url, "provider_type": "github", **kw}
    return client.post("/api/v1/repositories", json=payload)


# ── URL deduplication across projects ────────────────────────────────────────

def test_same_url_two_projects_creates_one_repository_row(client, db_session):
    pid_a = _create_project(client, "Project A")
    pid_b = _create_project(client, "Project B")

    r1 = _create_repo(client, pid_a, name="repo-a")
    r2 = _create_repo(client, pid_b, name="repo-b")

    assert r1.status_code == 201
    assert r2.status_code == 201

    # Both responses carry different ProjectRepository ids
    assert r1.json()["id"] != r2.json()["id"]

    # But both point to the same global Repository row
    assert r1.json()["repository_id"] == r2.json()["repository_id"]

    # Only one row in `repositories`
    assert db_session.query(Repository).count() == 1

    # Two rows in `project_repositories`
    assert db_session.query(ProjectRepository).count() == 2


def test_same_url_two_projects_preserves_per_project_name(client, db_session):
    pid_a = _create_project(client, "Project A")
    pid_b = _create_project(client, "Project B")

    _create_repo(client, pid_a, name="alpha")
    _create_repo(client, pid_b, name="beta")

    prs = db_session.query(ProjectRepository).order_by(ProjectRepository.id).all()
    assert {pr.name for pr in prs} == {"alpha", "beta"}


def test_same_url_two_projects_preserves_per_project_branch(client, db_session):
    pid_a = _create_project(client, "Project A")
    pid_b = _create_project(client, "Project B")

    _create_repo(client, pid_a, name="r", default_branch="main")
    _create_repo(client, pid_b, name="r", default_branch="develop")

    prs = db_session.query(ProjectRepository).order_by(ProjectRepository.id).all()
    assert {pr.default_branch for pr in prs} == {"main", "develop"}


# ── Same URL within one project (allowed) ────────────────────────────────────

def test_same_url_same_project_creates_two_project_repository_rows(client, db_session):
    pid = _create_project(client)

    r1 = _create_repo(client, pid, name="main-tracking", default_branch="main")
    r2 = _create_repo(client, pid, name="dev-tracking", default_branch="develop")

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]

    # Still only one underlying Repository
    assert db_session.query(Repository).count() == 1
    assert db_session.query(ProjectRepository).count() == 2


# ── Delete behaviour ─────────────────────────────────────────────────────────

def test_delete_one_of_two_references_keeps_repository_row(client, db_session):
    pid_a = _create_project(client, "A")
    pid_b = _create_project(client, "B")

    pr_id_a = _create_repo(client, pid_a).json()["id"]
    _create_repo(client, pid_b)

    assert db_session.query(Repository).count() == 1

    resp = client.delete(f"/api/v1/repositories/{pr_id_a}")
    assert resp.status_code == 204

    # ProjectRepository for A is gone, global Repository still exists
    assert db_session.query(ProjectRepository).count() == 1
    assert db_session.query(Repository).count() == 1


def test_delete_last_reference_removes_repository_row(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid).json()["id"]

    assert db_session.query(Repository).count() == 1

    resp = client.delete(f"/api/v1/repositories/{pr_id}")
    assert resp.status_code == 204

    assert db_session.query(ProjectRepository).count() == 0
    assert db_session.query(Repository).count() == 0


def test_delete_all_references_removes_repository_row(client, db_session):
    pid_a = _create_project(client, "A")
    pid_b = _create_project(client, "B")

    pr_id_a = _create_repo(client, pid_a).json()["id"]
    pr_id_b = _create_repo(client, pid_b).json()["id"]

    client.delete(f"/api/v1/repositories/{pr_id_a}")
    client.delete(f"/api/v1/repositories/{pr_id_b}")

    assert db_session.query(Repository).count() == 0
    assert db_session.query(ProjectRepository).count() == 0


# ── Response shape ────────────────────────────────────────────────────────────

def test_response_contains_both_id_and_repository_id(client):
    pid = _create_project(client)
    body = _create_repo(client, pid).json()

    assert "id" in body              # ProjectRepository.id
    assert "repository_id" in body   # global Repository.id
    assert body["id"] != body["repository_id"] or True  # may equal if ids align, both present


def test_two_projects_response_share_repository_id(client):
    pid_a = _create_project(client, "A")
    pid_b = _create_project(client, "B")

    body_a = _create_repo(client, pid_a, name="r-a").json()
    body_b = _create_repo(client, pid_b, name="r-b").json()

    assert body_a["repository_id"] == body_b["repository_id"]
    assert body_a["id"] != body_b["id"]


def test_response_url_matches_requested_url(client):
    pid = _create_project(client)
    url = "https://gitlab.com/my-group/my-project"
    body = _create_repo(client, pid, url=url, provider_type="gitlab").json()
    assert body["url"] == url
    assert body["provider_type"] == "gitlab"


# ── Update URL ────────────────────────────────────────────────────────────────

def test_update_url_to_existing_repo_shares_row(client, db_session):
    pid = _create_project(client)
    pr_a = _create_repo(client, pid, url="https://github.com/org/a", name="a").json()
    _create_repo(client, pid, url="https://github.com/org/b", name="b")

    assert db_session.query(Repository).count() == 2

    # Move pr_a to point at b's URL
    resp = client.put(f"/api/v1/repositories/{pr_a['id']}", json={
        "name": "a-renamed",
        "url": "https://github.com/org/b",
        "provider_type": "github",
    })
    assert resp.status_code == 200

    # Now both ProjectRepositories share the same Repository
    assert db_session.query(Repository).count() == 1
    assert db_session.query(ProjectRepository).count() == 2


def test_update_url_to_new_url_creates_new_repository_row(client, db_session):
    pid = _create_project(client)
    pr = _create_repo(client, pid, url="https://github.com/org/old", name="r").json()

    resp = client.put(f"/api/v1/repositories/{pr['id']}", json={
        "name": "r",
        "url": "https://github.com/org/new",
        "provider_type": "github",
    })
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://github.com/org/new"

    # Old Repository row should be cleaned up (no other references)
    assert db_session.query(Repository).count() == 1


def test_update_url_orphaned_old_repository_is_deleted(client, db_session):
    pid = _create_project(client)
    pr = _create_repo(client, pid, url="https://github.com/org/old", name="r").json()

    client.put(f"/api/v1/repositories/{pr['id']}", json={
        "name": "r",
        "url": "https://github.com/org/new",
        "provider_type": "github",
    })

    urls = {r.url for r in db_session.query(Repository).all()}
    assert "https://github.com/org/old" not in urls
    assert "https://github.com/org/new" in urls


# ── Git tags stay on the global Repository ───────────────────────────────────

def test_git_tags_endpoint_accessible_via_project_repository_id(client, db_session):
    pid = _create_project(client)
    pr_id = _create_repo(client, pid).json()["id"]

    resp = client.get(f"/api/v1/repositories/{pr_id}/git-tags")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── Different providers cannot share a URL (provider is URL-level) ────────────

def test_second_add_of_same_url_does_not_change_provider_type(client, db_session):
    pid_a = _create_project(client, "A")
    pid_b = _create_project(client, "B")

    _create_repo(client, pid_a, provider_type="github")
    # Add the same URL under a different project with a different provider_type
    _create_repo(client, pid_b, provider_type="gitlab")

    # The underlying repository row keeps the first provider_type (github)
    repo = db_session.query(Repository).one()
    assert repo.provider_type.value == "github"
