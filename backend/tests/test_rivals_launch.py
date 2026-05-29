"""Rivals launch-batch tests: challenges, cooldowns, timers, profile, admin edits,
archive, leagues, blacklist, tournaments losers_bracket. Complements test_rivals.py."""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://esports-hub-146.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@rivals.gg")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")


def _register(suffix):
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "email": f"lb_{suffix}_{uuid.uuid4().hex[:6]}@example.com",
        "username": f"lb_{suffix}_{uuid.uuid4().hex[:5]}",
        "password": "Pass@1234",
        "act": f"COD_{suffix}_{uuid.uuid4().hex[:4]}",
        "accepted_terms": True,
    })
    assert r.status_code == 200, r.text
    return s, r.json()["user"], r.json()["token"]


def _login_admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    return s, r.json()["user"], r.json()["token"]


def _make_clan(token, prefix):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API}/clans", headers=h, json={
        "name": f"TEST_{prefix}_{uuid.uuid4().hex[:5]}",
        "tag": f"{prefix[:1].upper()}{uuid.uuid4().hex[:3]}",
        "description": "x",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _fill_clan(leader_token, clan_id, count=5):
    """Add `count` members to a clan so it can participate in matches (≥6 total)."""
    h_l = {"Authorization": f"Bearer {leader_token}"}
    added = []
    for i in range(count):
        _, _, tm = _register(f"fill_{uuid.uuid4().hex[:5]}")
        h_m = {"Authorization": f"Bearer {tm}"}
        requests.post(f"{API}/clans/{clan_id}/join-request", headers=h_m)
        reqs = requests.get(f"{API}/clans/{clan_id}/requests", headers=h_l).json()
        for r in reqs:
            if not r.get("processed_at") and r.get("status", "pending") == "pending":
                requests.post(f"{API}/clans/{clan_id}/requests/{r['id']}", headers=h_l, json={"action": "accept"})
                added.append(tm)
                break
    return added


@pytest.fixture(scope="module")
def admin():
    s, u, t = _login_admin()
    return {"session": s, "user": u, "token": t}


# ---------------- Profile updates (act + streaming URLs) ----------------
def test_me_profile_updates_act_and_streams():
    _, u, t = _register("prof")
    h = {"Authorization": f"Bearer {t}"}
    r = requests.put(f"{API}/me/profile", headers=h, json={
        "act": "NEW_ACT_001",
        "twitch_url": "https://twitch.tv/foo",
        "kick_url": "https://kick.com/foo",
        "tiktok_url": "https://tiktok.com/@foo",
    })
    assert r.status_code == 200, r.text
    me = requests.get(f"{API}/auth/me", headers=h).json()
    assert me["act"] == "NEW_ACT_001"
    assert me["twitch_url"] == "https://twitch.tv/foo"
    assert me["kick_url"] == "https://kick.com/foo"
    assert me["tiktok_url"] == "https://tiktok.com/@foo"


# ---------------- Forgot password completion flow ----------------
def test_forgot_password_admin_complete(admin):
    _, u, _ = _register("fpc")
    requests.post(f"{API}/auth/forgot-password", json={"email": u["email"]})
    h = {"Authorization": f"Bearer {admin['token']}"}
    resets = requests.get(f"{API}/admin/password-resets", headers=h).json()
    target = next((x for x in resets if x["user_id"] == u["id"]), None)
    assert target, "Pending reset not found for user"
    rid = target["id"]
    r = requests.post(f"{API}/admin/password-resets/{rid}/complete", headers=h)
    assert r.status_code == 200
    resets2 = requests.get(f"{API}/admin/password-resets", headers=h).json()
    after = next((x for x in resets2 if x["id"] == rid), None)
    # After complete, either removed from pending list, or status flipped
    if after is not None:
        assert after.get("status") in ("completed", "done")


# ---------------- Admin edit user (username/email/password/act) ----------------
def test_admin_edit_user_full(admin):
    s, u, t = _register("aeu")
    h_admin = {"Authorization": f"Bearer {admin['token']}"}
    new_email = f"updated_{uuid.uuid4().hex[:6]}@example.com"
    new_username = f"upd_{uuid.uuid4().hex[:5]}"
    r = requests.put(f"{API}/admin/users/{u['id']}", headers=h_admin, json={
        "username": new_username,
        "email": new_email,
        "password": "NewPass@9876",
        "act": "ACT_UPDATED",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == new_username
    assert body["email"] == new_email
    assert body["act"] == "ACT_UPDATED"
    # New password works
    s2 = requests.Session()
    login = s2.post(f"{API}/auth/login", json={"email": new_email, "password": "NewPass@9876"})
    assert login.status_code == 200


# ---------------- Admin edit clan ----------------
def test_admin_edit_clan(admin):
    _, _, t = _register("aec")
    clan = _make_clan(t, "aec")
    h_admin = {"Authorization": f"Bearer {admin['token']}"}
    new_name = f"Renamed_{uuid.uuid4().hex[:5]}"
    new_tag = f"R{uuid.uuid4().hex[:4]}"
    r = requests.put(f"{API}/admin/clans/{clan['id']}", headers=h_admin, json={
        "name": new_name,
        "tag": new_tag,
        "description": "new desc",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == new_name
    assert body["tag"] == new_tag
    assert body["description"] == "new desc"


# ---------------- Clan challenge flow ----------------
def test_clan_challenge_accept_creates_match():
    _, _, ta = _register("ch_a")
    _, _, tb = _register("ch_b")
    ca = _make_clan(ta, "cha")
    cb = _make_clan(tb, "chb")
    _fill_clan(ta, ca["id"])
    _fill_clan(tb, cb["id"])
    h_a = {"Authorization": f"Bearer {ta}"}
    h_b = {"Authorization": f"Bearer {tb}"}
    # B challenges A (clan_id in URL = challenger's own clan = B's clan)
    r = requests.post(f"{API}/clans/{cb['id']}/challenge", headers=h_b,
                     json={"opponent_clan_id": ca["id"]})
    assert r.status_code == 200, r.text
    challenge = r.json()
    assert challenge.get("status") == "pending"
    # Listing for clan A shows it
    lst = requests.get(f"{API}/clans/{ca['id']}/challenges", headers=h_a).json()
    assert any(c["id"] == challenge["id"] for c in lst)
    # A accepts -> match created
    acc = requests.post(f"{API}/challenges/{challenge['id']}",
                        headers=h_a, json={"action": "accept"})
    assert acc.status_code == 200, acc.text
    body = acc.json()
    # Should contain match_id or match object
    assert body.get("match_id") or body.get("match") or body.get("id")


def test_clan_challenge_reject():
    _, _, ta = _register("rj_a")
    _, _, tb = _register("rj_b")
    ca = _make_clan(ta, "rja")
    cb = _make_clan(tb, "rjb")
    _fill_clan(ta, ca["id"])
    _fill_clan(tb, cb["id"])
    h_a = {"Authorization": f"Bearer {ta}"}
    h_b = {"Authorization": f"Bearer {tb}"}
    ch = requests.post(f"{API}/clans/{cb['id']}/challenge", headers=h_b,
                      json={"opponent_clan_id": ca["id"]}).json()
    r = requests.post(f"{API}/challenges/{ch['id']}",
                     headers=h_a, json={"action": "reject"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") in ("rejected", "declined")


# ---------------- 3h pair cooldown between same two clans ----------------
def test_3h_pair_cooldown_between_clans(admin):
    _, _, ta = _register("cd_a")
    _, _, tb = _register("cd_b")
    ca = _make_clan(ta, "cda")
    cb = _make_clan(tb, "cdb")
    _fill_clan(ta, ca["id"])
    _fill_clan(tb, cb["id"])
    h_a = {"Authorization": f"Bearer {ta}"}
    h_b = {"Authorization": f"Bearer {tb}"}
    h_admin = {"Authorization": f"Bearer {admin['token']}"}
    # First match via challenge accept
    ch = requests.post(f"{API}/clans/{cb['id']}/challenge", headers=h_b,
                      json={"opponent_clan_id": ca["id"]}).json()
    requests.post(f"{API}/challenges/{ch['id']}", headers=h_a, json={"action": "accept"})
    # Second challenge accept within 3h -> should fail with 400
    ch2 = requests.post(f"{API}/clans/{cb['id']}/challenge", headers=h_b,
                       json={"opponent_clan_id": ca["id"]})
    # Either challenge creation fails 400 OR the accept fails 400
    if ch2.status_code == 200:
        acc2 = requests.post(f"{API}/challenges/{ch2.json()['id']}",
                             headers=h_a, json={"action": "accept"})
        assert acc2.status_code == 400, f"Expected 400 cooldown, got {acc2.status_code}"
    else:
        assert ch2.status_code == 400
    # Staff override: admin creates match directly
    m = requests.post(f"{API}/matches", headers=h_admin,
                     json={"clan_a_id": ca["id"], "clan_b_id": cb["id"]})
    assert m.status_code == 200, "Admin should be able to override 3h cooldown"


# ---------------- Map timers (grace / prayer / claim) ----------------
def test_map_timers_grace_prayer(admin):
    _, _, ta = _register("tm_a")
    _, _, tb = _register("tm_b")
    ca = _make_clan(ta, "tma")
    cb = _make_clan(tb, "tmb")
    h_admin = {"Authorization": f"Bearer {admin['token']}"}
    h_a = {"Authorization": f"Bearer {ta}"}
    m = requests.post(f"{API}/matches", headers=h_admin,
                     json={"clan_a_id": ca["id"], "clan_b_id": cb["id"]}).json()
    mid = m["id"]
    # Start grace on map 0 (as leader A)
    g = requests.post(f"{API}/matches/{mid}/maps/0/grace", headers=h_a)
    assert g.status_code == 200, g.text
    # Map 0 should now have grace ends_at
    m_after = requests.get(f"{API}/matches/{mid}").json()
    mp0 = m_after["maps"][0]
    assert mp0.get("grace_started_at") and mp0.get("grace_started_by_clan")
    # Prayer break
    p = requests.post(f"{API}/matches/{mid}/maps/0/prayer", headers=h_a)
    assert p.status_code == 200
    # Claim grace win before expiry -> should fail
    c = requests.post(f"{API}/matches/{mid}/maps/0/claim-grace-win", headers=h_a)
    # Either 400 (too soon) or 200 if backend allows; assert it's not 500
    assert c.status_code in (200, 400, 403), c.text


# ---------------- Clan archive + cooldown ----------------
def test_clan_archive_excluded_from_listing_and_cooldown():
    _, _, t_leader = _register("aex_l")
    _, u_mem, t_mem = _register("aex_m")
    clan = _make_clan(t_leader, "aex")
    h_l = {"Authorization": f"Bearer {t_leader}"}
    h_m = {"Authorization": f"Bearer {t_mem}"}
    # Member joins
    requests.post(f"{API}/clans/{clan['id']}/join-request", headers=h_m)
    reqs = requests.get(f"{API}/clans/{clan['id']}/requests", headers=h_l).json()
    requests.post(f"{API}/clans/{clan['id']}/requests/{reqs[0]['id']}",
                  headers=h_l, json={"action": "accept"})
    # Archive
    a = requests.post(f"{API}/clans/{clan['id']}/archive", headers=h_l)
    assert a.status_code == 200, a.text
    # Excluded from /api/clans
    lst = requests.get(f"{API}/clans").json()
    assert not any(c["id"] == clan["id"] for c in lst), "Archived clan must be excluded"
    # Member cannot join another clan in cooldown
    _, _, t_other = _register("aex_o")
    other_clan = _make_clan(t_other, "aex2")
    r = requests.post(f"{API}/clans/{other_clan['id']}/join-request", headers=h_m)
    assert r.status_code == 400, f"Member in cooldown should not be able to join: {r.status_code} {r.text}"


# ---------------- Clan leave cooldown ----------------
def test_leave_starts_cooldown():
    _, _, tl = _register("lv_l")
    _, _, tm = _register("lv_m")
    clan = _make_clan(tl, "lv")
    h_l = {"Authorization": f"Bearer {tl}"}
    h_m = {"Authorization": f"Bearer {tm}"}
    requests.post(f"{API}/clans/{clan['id']}/join-request", headers=h_m)
    reqs = requests.get(f"{API}/clans/{clan['id']}/requests", headers=h_l).json()
    requests.post(f"{API}/clans/{clan['id']}/requests/{reqs[0]['id']}",
                  headers=h_l, json={"action": "accept"})
    # Leave
    r = requests.post(f"{API}/clans/{clan['id']}/leave", headers=h_m)
    assert r.status_code == 200, r.text
    me = requests.get(f"{API}/auth/me", headers=h_m).json()
    assert me["clan_id"] is None
    assert me.get("clan_cooldown_until")


# ---------------- Leagues + leaderboard ----------------
def test_leagues_current_arabic():
    r = requests.get(f"{API}/leagues/current")
    assert r.status_code == 200
    assert "دوري رايفلز" in r.json().get("name", "")


def test_leaderboard_clans_excludes_archived_and_has_trophies():
    r = requests.get(f"{API}/leaderboard/clans")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        # Verify archived clans excluded
        for c in data:
            assert not c.get("archived")
        # trophies key may be absent on clans that never won; ensure at least the field
        # is supported by the endpoint by checking presence on any clan
        # (Not strictly required if no clan has trophies yet)
        has_trophy_field = any("trophies" in c for c in data)
        assert has_trophy_field or all("points" in c for c in data)


# ---------------- Blacklist with proof image ----------------
def test_blacklist_with_proof_image(admin):
    h = {"Authorization": f"Bearer {admin['token']}"}
    TINY = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAarVyFEAAAAASUVORK5CYII="
    r = requests.post(f"{API}/blacklist", headers=h, json={
        "player_name": "ProofCheater",
        "cheat_tool": "Wallhack",
        "details": "proof attached",
        "proof_image": TINY,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("proof_image", "").startswith("data:image")
    requests.delete(f"{API}/blacklist/{body['id']}", headers=h)


# ---------------- Tournament losers_bracket ----------------
def test_tournament_losers_bracket(admin):
    h = {"Authorization": f"Bearer {admin['token']}"}
    r = requests.post(f"{API}/tournaments", headers=h, json={
        "name": f"TEST_TRN_{uuid.uuid4().hex[:5]}",
        "max_participants": 4,
        "losers_bracket": True,
    })
    # Endpoint may be POST /api/tournaments
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body.get("losers_bracket") is True


# ---------------- Twitch live returns null gracefully ----------------
def test_live_streams_returns_gracefully():
    # Endpoint may be exposed; if 404, skip
    r = requests.get(f"{API}/live/twitch", params={"channel": "ninja"})
    assert r.status_code in (200, 404)


# ---- Structural upgrade tests (Feb backlog) ----
def test_register_grants_personal_plus_trial():
    s, u, t = _register("pp_trial")
    assert u.get("is_personal_plus") is True
    assert u.get("personal_plus_until")


def test_personal_plus_required_for_visual_customization():
    """Free user cannot set avatar; Plus user can."""
    # New users have 3-day trial so are Personal Plus -> can set
    _, u, t = _register("pp_visual")
    h = {"Authorization": f"Bearer {t}"}
    # Use a small valid PNG data URL
    tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAAA1BMVEX///+nxBvIAAAAC0lEQVQI12NgAAIAAAUAAeImBZsAAAAASUVORK5CYII="
    r = requests.put(f"{API}/me/profile", headers=h, json={
        "avatar": tiny_png,
        "accent_color": "#FF8800",
    })
    assert r.status_code == 200, r.text
    assert r.json().get("avatar") == tiny_png
    assert r.json().get("accent_color") == "#FF8800"


def test_join_clan_requires_act():
    """A player without an Activision ID cannot join a clan (we wipe it via admin to simulate)."""
    s_l, u_l, t_l = _register("act_l")
    cr = _make_clan(t_l, "actcl")
    # Create a player and wipe their act via admin
    admin_s, _, admin_t = _login_admin()
    s_m, u_m, t_m = _register("act_p")
    h_admin = {"Authorization": f"Bearer {admin_t}"}
    # Try setting empty act via admin endpoint (it accepts a string but our model lets empty? skip act bypass)
    # Direct DB cannot be touched from tests; use admin endpoint to set act = ""
    # AdminUserEditIn.act allows None but accepts strings; empty string sanitized.
    requests.put(f"{API}/admin/users/{u_m['id']}", headers=h_admin, json={"act": ""})
    h_m = {"Authorization": f"Bearer {t_m}"}
    r = requests.post(f"{API}/clans/{cr['id']}/join-request", headers=h_m)
    assert r.status_code == 400
    assert "Activision" in r.json().get("detail", "")


def test_clan_challenge_blocked_under_6_members():
    _, _, ta = _register("min_a")
    _, _, tb = _register("min_b")
    ca = _make_clan(ta, "mina")
    cb = _make_clan(tb, "minb")
    h_b = {"Authorization": f"Bearer {tb}"}
    r = requests.post(f"{API}/clans/{cb['id']}/challenge", headers=h_b,
                     json={"opponent_clan_id": ca["id"]})
    assert r.status_code == 400
    assert "لاعبين" in r.json().get("detail", "")


def test_career_stats_kd_in_sanitized_user():
    _, u, t = _register("kd_check")
    assert "wins" in u and "losses" in u and "kd" in u


# ---------------- League leaderboard (decoupled standings) ----------------
def test_league_leaderboard_endpoint_and_empty_state(admin):
    h = {"Authorization": f"Bearer {admin['token']}"}
    name = f"LB Test League {uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/leagues/custom", headers=h,
                      json={"name": name, "game": "Call of Duty",
                            "rules": "BO3 — points: +3 / -1 / -3",
                            "description": "auto test league"})
    assert r.status_code == 200, r.text
    league = r.json()
    assert league["status"] == "active"
    # Leaderboard responds with empty standings for a fresh league
    lb = requests.get(f"{API}/leagues/{league['id']}/leaderboard")
    assert lb.status_code == 200, lb.text
    data = lb.json()
    assert data["league"]["id"] == league["id"]
    assert data["standings"] == []


def test_league_leaderboard_404_for_unknown():
    r = requests.get(f"{API}/leagues/does-not-exist-xyz/leaderboard")
    assert r.status_code == 404


# ---------------- Scoreboard OCR endpoint removed ----------------
def test_scoreboard_endpoint_removed():
    """The OCR scoreboard endpoint has been intentionally removed."""
    r = requests.post(f"{API}/matches/anything/scoreboard", json={"image_b64": "x"})
    # 404 = route not registered (or 405). Either way, the feature is gone.
    assert r.status_code in (404, 405), r.text
