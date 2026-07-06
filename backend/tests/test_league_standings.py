"""Integration tests for per-league decoupled standings, AI Referee league rules
posting, scoreboard endpoint removal, and league CRUD (POST/PUT/leaderboard)."""
import os
import uuid
import time
import requests

BASE_URL = (
    os.environ.get("TEST_BASE_URL")
    or os.environ.get("REACT_APP_BACKEND_URL")
    or "http://127.0.0.1:8001"
).rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@rivals.gg")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")

TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAarVyFEAAAAASUVORK5CYII="


def _login_admin():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _register():
    suffix = uuid.uuid4().hex[:6]
    r = requests.post(f"{API}/auth/register", json={
        "email": f"ls_{suffix}@example.com",
        "username": f"ls_{suffix}",
        "password": "Pass@1234",
        "act": f"ACT_{suffix}",
        "accepted_terms": True,
    })
    assert r.status_code == 200, r.text
    return r.json()["user"], r.json()["token"]


def _make_clan(token, prefix):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API}/clans", headers=h, json={
        "name": f"TEST_LS_{prefix}_{uuid.uuid4().hex[:5]}",
        "tag": f"{prefix[:1].upper()}{uuid.uuid4().hex[:3]}",
        "description": "x",
    })
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 1. Scoreboard endpoint fully removed ----------
def test_scoreboard_endpoint_returns_404_or_405():
    r = requests.post(f"{API}/matches/anything/scoreboard", json={"image_b64": "x"})
    assert r.status_code in (404, 405), f"Expected scoreboard endpoint removed, got {r.status_code}"


# ---------- 2. Active leagues endpoint ----------
def test_active_leagues_endpoint():
    r = requests.get(f"{API}/leagues/active")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)


# ---------- 3. Create custom league with rules_image (data URL) ----------
def test_create_custom_league_with_rules_image_data_url():
    token = _login_admin()
    h = {"Authorization": f"Bearer {token}"}
    name = f"League_DataURL_{uuid.uuid4().hex[:5]}"
    r = requests.post(f"{API}/leagues/custom", headers=h, json={
        "name": name,
        "game": "Call of Duty",
        "rules": "BO3 — +3 / -1 / -3",
        "rules_image": TINY_PNG,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == name
    assert body["rules_image"].startswith("data:image"), "rules_image should be persisted as data URL"
    assert body["status"] == "active"


# ---------- 4. Create custom league with http rules_image + PUT edit ----------
def test_put_edit_league():
    token = _login_admin()
    h = {"Authorization": f"Bearer {token}"}
    create = requests.post(f"{API}/leagues/custom", headers=h, json={
        "name": f"League_Edit_{uuid.uuid4().hex[:5]}",
        "game": "Call of Duty",
        "rules": "old rules",
        "rules_image": "https://example.com/rules.png",
    })
    assert create.status_code == 200, create.text
    lid = create.json()["id"]
    # PUT edit
    new_name = f"Edited_{uuid.uuid4().hex[:5]}"
    upd = requests.put(f"{API}/leagues/{lid}", headers=h, json={
        "name": new_name,
        "rules": "new rules text",
    })
    assert upd.status_code == 200, upd.text
    assert upd.json()["name"] == new_name
    assert upd.json()["rules"] == "new rules text"


# ---------- 5. League leaderboard empty for new league + 404 unknown ----------
def test_league_leaderboard_empty_and_unknown():
    token = _login_admin()
    h = {"Authorization": f"Bearer {token}"}
    create = requests.post(f"{API}/leagues/custom", headers=h, json={
        "name": f"League_LB_{uuid.uuid4().hex[:5]}",
        "game": "Call of Duty",
        "rules": "rules",
    })
    assert create.status_code == 200, create.text
    lid = create.json()["id"]
    lb = requests.get(f"{API}/leagues/{lid}/leaderboard")
    assert lb.status_code == 200
    data = lb.json()
    assert data["league"]["id"] == lid
    assert data["standings"] == []
    # unknown
    nf = requests.get(f"{API}/leagues/does-not-exist-xyz/leaderboard")
    assert nf.status_code == 404


# ---------- Helpers for match flow with league_id ----------
def _fill_clan(leader_token, clan_id, count=5):
    h_l = {"Authorization": f"Bearer {leader_token}"}
    for i in range(count):
        u, tm = _register()
        h_m = {"Authorization": f"Bearer {tm}"}
        requests.post(f"{API}/clans/{clan_id}/join-request", headers=h_m)
        reqs = requests.get(f"{API}/clans/{clan_id}/requests", headers=h_l).json()
        for rq in reqs:
            if not rq.get("processed_at") and rq.get("status", "pending") == "pending":
                requests.post(f"{API}/clans/{clan_id}/requests/{rq['id']}", headers=h_l, json={"action": "accept"})
                break


# ---------- 6. League standings on WITHDRAW ----------
def test_league_standings_on_withdraw():
    """When a clan withdraws from a league match, winning_clan +3 win, withdrawing_clan -3 loss
    in that league's standings only."""
    admin_token = _login_admin()
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    # Create league
    lr = requests.post(f"{API}/leagues/custom", headers=h_admin, json={
        "name": f"League_WD_{uuid.uuid4().hex[:5]}",
        "game": "Call of Duty",
        "rules": "BO3 +3/-1/-3",
    })
    assert lr.status_code == 200
    league_id = lr.json()["id"]

    # Create 2 clans
    _, tA = _register()
    _, tB = _register()
    cA = _make_clan(tA, "wda")
    cB = _make_clan(tB, "wdb")
    _fill_clan(tA, cA["id"])
    _fill_clan(tB, cB["id"])

    # Admin creates match WITH league_id
    m = requests.post(f"{API}/matches", headers=h_admin, json={
        "clan_a_id": cA["id"],
        "clan_b_id": cB["id"],
        "league_id": league_id,
    })
    assert m.status_code == 200, m.text
    match_id = m.json()["id"]
    assert m.json().get("league_id") == league_id, "Match must carry league_id"

    # Clan B withdraws (via leader token)
    h_b = {"Authorization": f"Bearer {tB}"}
    w = requests.post(f"{API}/matches/{match_id}/withdraw", headers=h_b)
    assert w.status_code == 200, w.text

    # Verify league standings: cA gets +3 / 1 win, cB gets -3 / 1 loss
    time.sleep(1)
    lb = requests.get(f"{API}/leagues/{league_id}/leaderboard")
    assert lb.status_code == 200, lb.text
    standings = lb.json()["standings"]
    by_clan = {s["clan_id"]: s for s in standings}
    assert cA["id"] in by_clan, f"Winner clan missing from standings: {standings}"
    assert cB["id"] in by_clan, f"Withdrawing clan missing from standings: {standings}"
    win_row = by_clan[cA["id"]]
    lose_row = by_clan[cB["id"]]
    assert win_row["points"] == 3, f"Winner expected +3, got {win_row['points']}"
    assert win_row["wins"] == 1, f"Winner expected wins=1, got {win_row['wins']}"
    assert lose_row["points"] == -3, f"Withdrawing clan expected -3, got {lose_row['points']}"
    assert lose_row["losses"] == 1, f"Withdrawing clan expected losses=1, got {lose_row['losses']}"


# ---------- 7. AI Referee posts league rules text + image after match created with league_id ----------
def test_ai_referee_posts_league_rules_in_chat():
    admin_token = _login_admin()
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    # Create league with both rules text and image
    rules_text = f"UniqueRulesText_{uuid.uuid4().hex[:6]}"
    lr = requests.post(f"{API}/leagues/custom", headers=h_admin, json={
        "name": f"League_AI_{uuid.uuid4().hex[:5]}",
        "game": "Call of Duty",
        "rules": rules_text,
        "rules_image": TINY_PNG,
    })
    assert lr.status_code == 200
    league_id = lr.json()["id"]

    # Create 2 clans
    _, tA = _register()
    _, tB = _register()
    cA = _make_clan(tA, "aia")
    cB = _make_clan(tB, "aib")

    # Match with league
    m = requests.post(f"{API}/matches", headers=h_admin, json={
        "clan_a_id": cA["id"],
        "clan_b_id": cB["id"],
        "league_id": league_id,
    })
    assert m.status_code == 200, m.text
    match_id = m.json()["id"]

    # Wait briefly for AI welcome to post
    time.sleep(2.5)

    # Need a token that can read chat — admin works
    chat = requests.get(f"{API}/matches/{match_id}/chat", headers=h_admin)
    assert chat.status_code == 200, chat.text
    payload = chat.json()
    msgs = payload.get("messages", payload) if isinstance(payload, dict) else payload
    bot_msgs = [m for m in msgs if m.get("user_id") == "ai-bot"]
    assert bot_msgs, f"AI bot welcome message not found in chat. Got: {msgs}"
    # Verify rules text appears in at least one bot message
    combined = " ".join((m.get("text") or "") + " " + (m.get("image") or "") for m in bot_msgs)
    assert rules_text in combined, f"League rules text not found in AI bot messages. Bot msgs: {bot_msgs}"
    # Verify image posted (data URL)
    image_found = any((m.get("image") or "").startswith("data:image") for m in bot_msgs)
    assert image_found, f"League rules image not posted by AI bot. Bot msgs: {bot_msgs}"


# ---------- 8. Regression: global /api/leaderboard/clans still updates ----------
def test_global_clan_leaderboard_still_works():
    r = requests.get(f"{API}/leaderboard/clans")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
