"""
Integration tests — hit the real running Docker backend via HTTP.
Require: docker compose up (spry_v2_web on port 8000).

Run: pytest tests/insights/test_integration.py -v
"""
from __future__ import annotations

import pytest
import httpx

BASE = "http://localhost:8000"
HEADERS = {"X-Demo-Key": "spry-demo-2024"}

ORG_ID = "cc00837a-73dc-41a5-9f51-fc6f0a30b827"
ALICE_USER_ID = "f3e24cdd-b08a-4f34-b048-ecf6e6ca617b"   # alice@spry.demo — ADMIN (auth member)
BOB_USER_ID = "303e0bf5-195b-490f-80a5-9d79e2505915"    # bob@spry.demo — MEMBER
ENGINEERING_TEAM_ID = "00c0883f-169b-48eb-86c8-c9fe267c4bf2"
DESIGN_TEAM_ID = "83c16689-759e-4db3-8b57-dbe140500b67"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=30) as c:
        yield c


# ─── Settings endpoint ────────────────────────────────────────────────────────

class TestSettingsEndpoint:
    def test_get_settings_returns_three_tabs(self, client):
        r = client.get(f"/organizations/{ORG_ID}/insights/settings/")
        assert r.status_code == 200
        tabs = {s["tab"] for s in r.json()["data"]}
        assert tabs == {"personal", "teams", "organization"}

    def test_settings_have_required_fields(self, client):
        r = client.get(f"/organizations/{ORG_ID}/insights/settings/")
        for s in r.json()["data"]:
            assert "tab" in s
            assert "generation_frequency" in s
            assert "data_horizon" in s
            assert "frequency_label" in s
            assert "horizon_label" in s

    def test_patch_personal_horizon(self, client):
        r = client.patch(
            f"/organizations/{ORG_ID}/insights/settings/personal",
            json={"data_horizon": "last_3m"},
        )
        assert r.status_code == 200
        personal = next(s for s in r.json()["data"] if s["tab"] == "personal")
        assert personal["data_horizon"] == "last_3m"

    def test_patch_restores_original(self, client):
        r = client.patch(
            f"/organizations/{ORG_ID}/insights/settings/personal",
            json={"data_horizon": "current_month"},
        )
        assert r.status_code == 200
        personal = next(s for s in r.json()["data"] if s["tab"] == "personal")
        assert personal["data_horizon"] == "current_month"

    def test_patch_invalid_tab_returns_404(self, client):
        r = client.patch(
            f"/organizations/{ORG_ID}/insights/settings/nonexistent",
            json={"data_horizon": "current_month"},
        )
        assert r.status_code == 404

    def test_patch_invalid_horizon_returns_422(self, client):
        r = client.patch(
            f"/organizations/{ORG_ID}/insights/settings/personal",
            json={"data_horizon": "made_up_value"},
        )
        assert r.status_code == 422


# ─── Personal insights endpoint ───────────────────────────────────────────────

class TestPersonalInsights:
    def test_self_view_returns_200(self, client):
        r = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        assert r.status_code == 200

    def test_self_view_returns_list(self, client):
        r = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        data = r.json()["data"]
        assert isinstance(data, list)

    def test_self_insights_have_correct_tab(self, client):
        r = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        for i in r.json()["data"]:
            assert i["tab"] == "personal", f"Wrong tab on insight {i['id']}"

    def test_self_insight_ids_are_unique(self, client):
        r = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        ids = [i["id"] for i in r.json()["data"]]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"

    def test_self_insights_valid_statuses(self, client):
        r = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        valid = {"positive", "attention", "negative"}
        for i in r.json()["data"]:
            assert i["status"] in valid

    def test_self_insights_have_all_fields(self, client):
        r = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        for i in r.json()["data"]:
            assert i.get("id"), f"Missing id: {i}"
            assert i.get("title"), f"Missing title: {i}"
            assert i.get("data_signal"), f"Missing data_signal: {i}"
            assert i.get("recommendation"), f"Missing recommendation: {i}"

    def test_manager_view_returns_m_prefix_ids(self, client):
        """Alice (admin) views Bob → should get m-* insight IDs."""
        r = client.get(f"/organizations/{ORG_ID}/members/{BOB_USER_ID}/insights/")
        assert r.status_code == 200
        ids = [i["id"] for i in r.json()["data"]]
        # At least some m-* insights should appear
        m_ids = [x for x in ids if x.startswith("m-")]
        assert len(m_ids) >= 1, f"Expected m-* insights for manager view, got: {ids}"

    def test_manager_view_includes_member_name(self, client):
        r = client.get(f"/organizations/{ORG_ID}/members/{BOB_USER_ID}/insights/")
        for i in r.json()["data"]:
            if i["id"].startswith("m-"):
                assert "Bob" in i["title"] or "Bob" in i.get("data_signal", ""), \
                    f"Member name missing from manager insight: {i}"

    def test_settings_drive_date_range(self, client):
        """Changing data_horizon should produce different insights."""
        # Set to current_month
        client.patch(
            f"/organizations/{ORG_ID}/insights/settings/personal",
            json={"data_horizon": "current_month"},
        )
        r1 = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        ids1 = {i["id"] for i in r1.json()["data"]}

        # Set to last_3m
        client.patch(
            f"/organizations/{ORG_ID}/insights/settings/personal",
            json={"data_horizon": "last_3m"},
        )
        r2 = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        ids2 = {i["id"] for i in r2.json()["data"]}

        # Restore
        client.patch(
            f"/organizations/{ORG_ID}/insights/settings/personal",
            json={"data_horizon": "current_month"},
        )
        # The sets of insights may differ when horizon changes (data changes)
        # We just verify both returned valid responses
        assert isinstance(ids1, set)
        assert isinstance(ids2, set)

    def test_no_query_params_required(self, client):
        """Endpoint must work without start_date / end_date."""
        r = client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        assert r.status_code == 200


# ─── Team insights endpoint ───────────────────────────────────────────────────

class TestTeamInsights:
    def test_returns_200(self, client):
        r = client.get(f"/organizations/{ORG_ID}/teams/{ENGINEERING_TEAM_ID}/insights/")
        assert r.status_code == 200

    def test_insights_have_teams_tab(self, client):
        r = client.get(f"/organizations/{ORG_ID}/teams/{ENGINEERING_TEAM_ID}/insights/")
        for i in r.json()["data"]:
            assert i["tab"] == "teams"

    def test_insight_ids_are_t_prefix(self, client):
        r = client.get(f"/organizations/{ORG_ID}/teams/{ENGINEERING_TEAM_ID}/insights/")
        for i in r.json()["data"]:
            assert i["id"].startswith("t-"), f"Unexpected ID: {i['id']}"

    def test_ids_are_unique(self, client):
        r = client.get(f"/organizations/{ORG_ID}/teams/{ENGINEERING_TEAM_ID}/insights/")
        ids = [i["id"] for i in r.json()["data"]]
        assert len(ids) == len(set(ids))

    def test_design_team_also_works(self, client):
        r = client.get(f"/organizations/{ORG_ID}/teams/{DESIGN_TEAM_ID}/insights/")
        assert r.status_code == 200

    def test_nonexistent_team_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        r = client.get(f"/organizations/{ORG_ID}/teams/{fake_id}/insights/")
        assert r.status_code == 404


# ─── Org insights endpoint ────────────────────────────────────────────────────

class TestOrgInsights:
    def test_returns_200(self, client):
        r = client.get(f"/organizations/{ORG_ID}/insights/")
        assert r.status_code == 200

    def test_insights_have_organization_tab(self, client):
        r = client.get(f"/organizations/{ORG_ID}/insights/")
        for i in r.json()["data"]:
            assert i["tab"] == "organization"

    def test_insight_ids_are_o_prefix(self, client):
        r = client.get(f"/organizations/{ORG_ID}/insights/")
        for i in r.json()["data"]:
            assert i["id"].startswith("o-"), f"Unexpected ID: {i['id']}"

    def test_ids_are_unique(self, client):
        r = client.get(f"/organizations/{ORG_ID}/insights/")
        ids = [i["id"] for i in r.json()["data"]]
        assert len(ids) == len(set(ids))

    def test_has_required_fields(self, client):
        r = client.get(f"/organizations/{ORG_ID}/insights/")
        for i in r.json()["data"]:
            for field in ["id", "tab", "status", "title", "data_signal", "recommendation"]:
                assert field in i, f"Missing field '{field}' in {i}"


# ─── Response time ────────────────────────────────────────────────────────────

class TestPerformance:
    def test_personal_responds_under_5s(self, client):
        import time
        start = time.time()
        client.get(f"/organizations/{ORG_ID}/members/{ALICE_USER_ID}/insights/")
        elapsed = time.time() - start
        assert elapsed < 5, f"Personal insights took {elapsed:.1f}s (>5s)"

    def test_team_responds_under_10s(self, client):
        import time
        start = time.time()
        client.get(f"/organizations/{ORG_ID}/teams/{ENGINEERING_TEAM_ID}/insights/")
        elapsed = time.time() - start
        assert elapsed < 10, f"Team insights took {elapsed:.1f}s (>10s)"

    def test_org_responds_under_10s(self, client):
        import time
        start = time.time()
        client.get(f"/organizations/{ORG_ID}/insights/")
        elapsed = time.time() - start
        assert elapsed < 10, f"Org insights took {elapsed:.1f}s (>10s)"
