"""Rivals esports backend tests - iteration 2."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://esports-hub-146.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@rivals.gg"
ADMIN_PASSWORD = "Admin@12345"


def _register(suffix):
    email = f"test_{suffix}_{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "email": email,
        "username": f"tu_{suffix}_{uuid.uuid4().hex[:5]}",
        "password": "Pass@1234",
    })
    assert r.status_code == 200, r.text
    return s, r.json()["user"], r.json()["token"], email


def _login_admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s, r.json()["user"], r.json()["token"]


@pytest.fixture(scope="module")
def admin():
    s, u, t = _login_admin()
    return {"session": s, "user": u, "token": t}


# ---- Meta ----
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200


def test_games():
    r = requests.get(f"{API}/games")
    assert r.status_code == 200
    assert r.json() == ["Call of Duty"]


def test_limits():
    r = requests.get(f"{API}/limits")
    assert r.status_code == 200
    d = r.json()
    assert d["clan_default"] == 7
    assert d["clan_plus"] == 12
    assert d["vice_default"] == 1
    assert d["vice_plus"] == 2
    assert d["bo_total"] == 3
    assert d["maps_to_win"] == 2


# ---- Auth ----
def test_admin_login(admin):
    assert admin["user"]["role"] == "admin"
    assert admin["user"]["email"] == ADMIN_EMAIL


def test_me_endpoint(admin):
    r = admin["session"].get(f"{API}/auth/me",
                             headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN_EMAIL


def test_register_and_me():
    s, u, t, _ = _register("reg")
    r = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json()["id"] == u["id"]
    assert r.json()["is_plus"] is False


# ---- Plus toggle ----
def test_toggle_plus():
    s, u, t, _ = _register("plus")
    h = {"Authorization": f"Bearer {t}"}
    r = s.post(f"{API}/me/plus", headers=h)
    assert r.status_code == 200
    assert r.json()["is_plus"] is True
    # Toggle back
    r = s.post(f"{API}/me/plus", headers=h)
    assert r.json()["is_plus"] is False


# ---- Rules ----
def test_rules_seeded():
    r = requests.get(f"{API}/rules")
    assert r.status_code == 200
    rules = r.json()
    assert isinstance(rules, list)
    assert len(rules) >= 5


def test_rules_crud_admin(admin):
    h = {"Authorization": f"Bearer {admin['token']}"}
    # CREATE
    r = requests.post(f"{API}/rules", headers=h,
                      json={"title": "TEST_RULE", "body": "tbody", "order": 99})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert r.json()["title"] == "TEST_RULE"

    # GET shows it
    r2 = requests.get(f"{API}/rules")
    assert any(x["id"] == rid for x in r2.json())

    # UPDATE
    r = requests.put(f"{API}/rules/{rid}", headers=h,
                     json={"title": "TEST_RULE_UPD", "body": "tbody", "order": 99})
    assert r.status_code == 200
    assert r.json()["title"] == "TEST_RULE_UPD"

    # DELETE
    r = requests.delete(f"{API}/rules/{rid}", headers=h)
    assert r.status_code == 200


def test_rules_non_admin_blocked():
    s, _, t, _ = _register("rul")
    h = {"Authorization": f"Bearer {t}"}
    r = requests.post(f"{API}/rules", headers=h, json={"title": "x", "body": "y"})
    assert r.status_code == 403


# ---- Clan create / fields ----
@pytest.fixture(scope="module")
def leader_a():
    s, u, t, _ = _register("leaderA")
    h = {"Authorization": f"Bearer {t}"}
    name = f"TEST_clanA_{uuid.uuid4().hex[:5]}"
    tag = f"A{uuid.uuid4().hex[:4]}"
    r = requests.post(f"{API}/clans", headers=h,
                      json={"name": name, "tag": tag, "description": "a"})
    assert r.status_code == 200, r.text
    return {"session": s, "user": u, "token": t, "clan": r.json()}


@pytest.fixture(scope="module")
def leader_b():
    s, u, t, _ = _register("leaderB")
    h = {"Authorization": f"Bearer {t}"}
    name = f"TEST_clanB_{uuid.uuid4().hex[:5]}"
    tag = f"B{uuid.uuid4().hex[:4]}"
    r = requests.post(f"{API}/clans", headers=h,
                      json={"name": name, "tag": tag, "description": "b"})
    assert r.status_code == 200, r.text
    return {"session": s, "user": u, "token": t, "clan": r.json()}


def test_clan_create_no_id_leak(leader_a):
    assert "_id" not in leader_a["clan"]
    assert leader_a["clan"]["leader_id"] == leader_a["user"]["id"]


def test_clan_detail_has_limit_fields(leader_a):
    r = requests.get(f"{API}/clans/{leader_a['clan']['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["max_members"] == 7
    assert d["max_vices"] == 1
    assert "members" in d


def test_clan_detail_plus_limits():
    # leader becomes plus -> limits jump
    s, u, t, _ = _register("plusldr")
    h = {"Authorization": f"Bearer {t}"}
    name = f"TEST_clanPlus_{uuid.uuid4().hex[:5]}"
    tag = f"P{uuid.uuid4().hex[:4]}"
    r = requests.post(f"{API}/clans", headers=h, json={"name": name, "tag": tag})
    cid = r.json()["id"]
    requests.post(f"{API}/me/plus", headers=h)
    d = requests.get(f"{API}/clans/{cid}").json()
    assert d["max_members"] == 12
    assert d["max_vices"] == 2


def test_vice_cap_enforced(leader_a):
    # add a member then attempt 2 vice promotions (limit 1)
    h_a = {"Authorization": f"Bearer {leader_a['token']}"}
    members = []
    for i in range(2):
        s, u, t, _ = _register(f"mem{i}")
        # invite & accept
        inv = requests.post(f"{API}/clans/{leader_a['clan']['id']}/invite",
                            headers=h_a, json={"user_id": u["id"]})
        assert inv.status_code == 200, inv.text
        inv_id = inv.json()["id"]
        h_m = {"Authorization": f"Bearer {t}"}
        ar = requests.post(f"{API}/invites/{inv_id}", headers=h_m, json={"action": "accept"})
        assert ar.status_code == 200
        members.append(u["id"])

    # promote first vice OK
    r = requests.post(f"{API}/clans/{leader_a['clan']['id']}/promote/{members[0]}", headers=h_a)
    assert r.status_code == 200
    # promote second vice should fail (cap=1)
    r = requests.post(f"{API}/clans/{leader_a['clan']['id']}/promote/{members[1]}", headers=h_a)
    assert r.status_code == 400


# ---- Matches with BO3 maps voting ----
@pytest.fixture(scope="module")
def match(admin, leader_a, leader_b):
    h = {"Authorization": f"Bearer {admin['token']}"}
    r = requests.post(f"{API}/matches", headers=h, json={
        "clan_a_id": leader_a["clan"]["id"],
        "clan_b_id": leader_b["clan"]["id"],
        "notes": "TEST_MATCH",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["game"] == "Call of Duty"
    assert d["status"] == "live"
    assert len(d["maps"]) == 3
    for mp in d["maps"]:
        assert mp["vote_a"] is None
        assert mp["vote_b"] is None
        assert mp["winner"] is None
        assert mp["disputed"] is False
        assert mp["admin_resolved"] is False
    return d


def test_match_created(match):
    assert match["id"]


def test_vote_map_agreement_and_finish(match, leader_a, leader_b):
    h_a = {"Authorization": f"Bearer {leader_a['token']}"}
    h_b = {"Authorization": f"Bearer {leader_b['token']}"}
    mid = match["id"]
    ca = leader_a["clan"]["id"]

    # Map 0: both vote A -> A wins map 0
    r = requests.post(f"{API}/matches/{mid}/vote-map", headers=h_a,
                      json={"map_index": 0, "winner_clan_id": ca})
    assert r.status_code == 200
    r = requests.post(f"{API}/matches/{mid}/vote-map", headers=h_b,
                      json={"map_index": 0, "winner_clan_id": ca})
    assert r.status_code == 200
    assert r.json()["maps"][0]["winner"] == "A"

    # Map 1: disagree -> disputed
    cb = leader_b["clan"]["id"]
    r = requests.post(f"{API}/matches/{mid}/vote-map", headers=h_a,
                      json={"map_index": 1, "winner_clan_id": ca})
    r = requests.post(f"{API}/matches/{mid}/vote-map", headers=h_b,
                      json={"map_index": 1, "winner_clan_id": cb})
    assert r.json()["maps"][1]["disputed"] is True
    assert r.json()["maps"][1]["winner"] is None

    # Map 2: both vote A -> A wins -> match should auto-finish (2 wins for A)
    r = requests.post(f"{API}/matches/{mid}/vote-map", headers=h_a,
                      json={"map_index": 2, "winner_clan_id": ca})
    r = requests.post(f"{API}/matches/{mid}/vote-map", headers=h_b,
                      json={"map_index": 2, "winner_clan_id": ca})
    assert r.status_code == 200
    # NOTE: vote-map response may be stale (does not reflect _maybe_finish writes).
    # Refetch match to assert auto-finish.
    final = requests.get(f"{API}/matches/{mid}").json()
    assert final["status"] == "finished"
    assert final["winner_clan_id"] == ca
    assert final["score_a"] == 2
    assert final["score_b"] == 0

    # Verify points awarded (+25 / -10)
    cdetail_a = requests.get(f"{API}/clans/{ca}").json()
    cdetail_b = requests.get(f"{API}/clans/{cb}").json()
    assert cdetail_a["points"] == 25
    assert cdetail_b["points"] == -10
    assert cdetail_a["wins"] == 1
    assert cdetail_b["losses"] == 1


def test_admin_resolve_map(admin, leader_a, leader_b):
    """Create new match, dispute a map, admin resolves it."""
    h_admin = {"Authorization": f"Bearer {admin['token']}"}
    h_a = {"Authorization": f"Bearer {leader_a['token']}"}
    h_b = {"Authorization": f"Bearer {leader_b['token']}"}
    r = requests.post(f"{API}/matches", headers=h_admin, json={
        "clan_a_id": leader_a["clan"]["id"],
        "clan_b_id": leader_b["clan"]["id"],
    })
    assert r.status_code == 200
    mid = r.json()["id"]
    ca = leader_a["clan"]["id"]
    cb = leader_b["clan"]["id"]

    # Disagree on map 0
    requests.post(f"{API}/matches/{mid}/vote-map", headers=h_a,
                  json={"map_index": 0, "winner_clan_id": ca})
    requests.post(f"{API}/matches/{mid}/vote-map", headers=h_b,
                  json={"map_index": 0, "winner_clan_id": cb})

    # Non-admin cannot resolve
    r = requests.post(f"{API}/matches/{mid}/admin-resolve-map", headers=h_a,
                      json={"map_index": 0, "winner_clan_id": ca})
    assert r.status_code == 403

    # Admin resolves -> A
    r = requests.post(f"{API}/matches/{mid}/admin-resolve-map", headers=h_admin,
                      json={"map_index": 0, "winner_clan_id": ca})
    assert r.status_code == 200
    mp = r.json()["maps"][0]
    assert mp["winner"] == "A"
    assert mp["admin_resolved"] is True
    assert mp["disputed"] is False


def test_dispute_endpoint(admin, leader_a, leader_b):
    h_admin = {"Authorization": f"Bearer {admin['token']}"}
    h_a = {"Authorization": f"Bearer {leader_a['token']}"}
    r = requests.post(f"{API}/matches", headers=h_admin, json={
        "clan_a_id": leader_a["clan"]["id"],
        "clan_b_id": leader_b["clan"]["id"],
    })
    mid = r.json()["id"]
    r = requests.post(f"{API}/matches/{mid}/dispute", headers=h_a)
    assert r.status_code == 200
    m = requests.get(f"{API}/matches/{mid}").json()
    assert any(mp.get("disputed") for mp in m["maps"])


# ---- Chat with media ----
TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAarVyFEAAAAASUVORK5CYII="
TINY_VID = "data:video/mp4;base64,AAAA"


@pytest.fixture(scope="module")
def chat_match(admin, leader_a, leader_b):
    h = {"Authorization": f"Bearer {admin['token']}"}
    r = requests.post(f"{API}/matches", headers=h, json={
        "clan_a_id": leader_a["clan"]["id"],
        "clan_b_id": leader_b["clan"]["id"],
    })
    return r.json()


def test_chat_post_and_permissions(chat_match, leader_a, leader_b):
    mid = chat_match["id"]
    h_a = {"Authorization": f"Bearer {leader_a['token']}"}
    h_b = {"Authorization": f"Bearer {leader_b['token']}"}

    # Leader A posts text
    r = requests.post(f"{API}/matches/{mid}/chat", headers=h_a, json={"text": "hello A"})
    assert r.status_code == 200
    assert r.json()["type"] == "text"

    # Leader A posts image
    r = requests.post(f"{API}/matches/{mid}/chat", headers=h_a,
                      json={"image": TINY_PNG, "text": "result"})
    assert r.status_code == 200
    img_msg_id = r.json()["id"]
    assert r.json()["type"] == "image"

    # Leader A posts video
    r = requests.post(f"{API}/matches/{mid}/chat", headers=h_a, json={"video": TINY_VID})
    assert r.status_code == 200
    vid_msg_id = r.json()["id"]
    assert r.json()["type"] == "video"

    # Outsider (new random user) gets media-only without text
    s, u, t, _ = _register("outsider")
    h_o = {"Authorization": f"Bearer {t}"}
    r = requests.get(f"{API}/matches/{mid}/chat", headers=h_o)
    assert r.status_code == 200
    data = r.json()
    assert data["can_write"] is False
    for m in data["messages"]:
        assert m.get("image") or m.get("video"), "Outsider should only see media"
        assert m.get("text") == "", "text must be stripped"

    # Player-in-match sees full content
    r = requests.get(f"{API}/matches/{mid}/chat", headers=h_a)
    assert r.json()["can_write"] is True
    full = r.json()["messages"]
    # text message present
    assert any(m["type"] == "text" and m["text"] == "hello A" for m in full)

    # Opponent decision: leader B accepts image
    r = requests.post(f"{API}/chat/{img_msg_id}/opponent-decision", headers=h_b,
                      json={"decision": "accept"})
    assert r.status_code == 200

    # Leader A cannot decide on their own image
    r = requests.post(f"{API}/chat/{img_msg_id}/opponent-decision", headers=h_a,
                      json={"decision": "reject"})
    assert r.status_code == 403

    # Admin decision on video
    admin_s, _, admin_t = _login_admin()
    h_admin = {"Authorization": f"Bearer {admin_t}"}
    r = requests.post(f"{API}/chat/{vid_msg_id}/admin-decision", headers=h_admin,
                      json={"decision": "approve", "note": "ok"})
    assert r.status_code == 200

    # Non-admin cannot admin-decision
    r = requests.post(f"{API}/chat/{vid_msg_id}/admin-decision", headers=h_a,
                      json={"decision": "reject"})
    assert r.status_code == 403


def test_chat_write_blocked_for_outsiders(chat_match):
    mid = chat_match["id"]
    s, u, t, _ = _register("outwrite")
    h = {"Authorization": f"Bearer {t}"}
    r = requests.post(f"{API}/matches/{mid}/chat", headers=h, json={"text": "hi"})
    assert r.status_code == 403
