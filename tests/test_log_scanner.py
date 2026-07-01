"""Tests for log_scanner.py — Arena Player.log parsing.

Focus on the pure-logic parts: DraftState lifecycle, set-code extraction
from log content, JSON payload extraction. Stateful end-to-end log
tailing is exercised by the in-game advisor's tests; we don't duplicate
that here.
"""
from __future__ import annotations

import pytest

from draft_helper.log_scanner import ArenaLogScanner, DraftState


# ---------------------------------------------------------------------------
# DraftState
# ---------------------------------------------------------------------------

def test_draft_state_initializes_to_defaults():
    s = DraftState()
    assert s.set_code == ""
    assert s.draft_format == "QuickDraft"
    assert s.pack_number == 1
    assert s.pick_number == 1
    assert s.current_pack == []
    assert s.picked_cards == []
    assert s.picked_ids == []
    assert s.original_pack_size == 0
    assert s.active is False


def test_draft_state_reset_returns_to_defaults():
    s = DraftState()
    s.set_code = "DSK"
    s.pack_number = 3
    s.pick_number = 14
    s.current_pack = ["Foo", "Bar"]
    s.picked_cards = ["Baz"]
    s.active = True
    s.reset()
    assert s.set_code == ""
    assert s.pack_number == 1
    assert s.pick_number == 1
    assert s.current_pack == []
    assert s.picked_cards == []
    assert s.active is False


# ---------------------------------------------------------------------------
# _extract_set_code — pre-scan helper
# ---------------------------------------------------------------------------

def _scanner_with_no_log() -> ArenaLogScanner:
    """Return a scanner without touching disk — _extract_set_code is pure."""
    s = ArenaLogScanner(log_path="/nonexistent/Player.log")
    return s


def test_extract_set_code_finds_event_join_quickdraft():
    scanner = _scanner_with_no_log()
    content = (
        '[Some prefix] ==> EventJoin '
        '{"EventName":"QuickDraft_DSK_20260101","Foo":"bar"}\n'
    )
    result = scanner._extract_set_code(content)
    assert result == ("DSK", "QuickDraft")


def test_extract_set_code_finds_premier_draft():
    scanner = _scanner_with_no_log()
    content = '==> EventJoin {"EventName":"PremierDraft_BLB_20260101"}\n'
    assert scanner._extract_set_code(content) == ("BLB", "PremierDraft")


def test_extract_set_code_handles_resumed_draft_via_internal_event_name():
    """When MTGA resumes a draft, only InternalEventName is logged (no
    EventJoin). The fallback path should still detect the set."""
    scanner = _scanner_with_no_log()
    content = (
        '[Course state dump] '
        '"InternalEventName":"BotDraft_DSK_20260101"\n'
    )
    result = scanner._extract_set_code(content)
    assert result == ("DSK", "QuickDraft")


def test_extract_set_code_returns_none_for_unrelated_content():
    scanner = _scanner_with_no_log()
    content = "Some unrelated log lines\nNo draft events here\n"
    assert scanner._extract_set_code(content) is None


def test_extract_set_code_handles_resumed_premier_draft_via_internal_name():
    """Regression: a RESUMED Premier Draft logs InternalEventName with
    'PremierDraft_...', not 'BotDraft_...'. The fallback must not be gated
    on the BotDraft string or the set (and thus ratings) never load."""
    scanner = _scanner_with_no_log()
    content = '[Course state dump] "InternalEventName":"PremierDraft_MSH_20260623"\n'
    assert scanner._extract_set_code(content) == ("MSH", "PremierDraft")


def test_extract_set_code_prefers_event_join_over_internal_name():
    """When both signals are present in the same log, EventJoin should
    win (it's more specific and timestamps the actual join)."""
    scanner = _scanner_with_no_log()
    content = (
        '"InternalEventName":"BotDraft_OLD_20260101"\n'
        '==> EventJoin {"EventName":"QuickDraft_NEW_20260101"}\n'
    )
    result = scanner._extract_set_code(content)
    assert result == ("NEW", "QuickDraft")


def test_extract_set_code_uses_last_event_join_if_multiple():
    """Multiple EventJoin lines → use the most recent one."""
    scanner = _scanner_with_no_log()
    content = (
        '==> EventJoin {"EventName":"QuickDraft_OLD_20260101"}\n'
        '==> EventJoin {"EventName":"PremierDraft_NEW_20260102"}\n'
    )
    result = scanner._extract_set_code(content)
    assert result == ("NEW", "PremierDraft")


# ---------------------------------------------------------------------------
# _get_payload — JSON extraction
# ---------------------------------------------------------------------------

def test_get_payload_unwraps_double_encoded_json():
    """The Payload field is a JSON-encoded string of another JSON object;
    decoding both layers should yield the inner dict."""
    scanner = _scanner_with_no_log()
    inner = '{"PackNumber":2,"PickNumber":5}'
    outer = '{"Payload":"' + inner.replace('"', '\\"') + '"}'
    result = scanner._get_payload([outer], 0)
    assert result == {"PackNumber": 2, "PickNumber": 5}


def test_get_payload_returns_outer_dict_when_no_payload_field():
    """Some events have the data directly in the outer object."""
    scanner = _scanner_with_no_log()
    outer = '{"PackNumber":1,"PickNumber":1,"Cards":[1,2,3]}'
    result = scanner._get_payload([outer], 0)
    assert result == {"PackNumber": 1, "PickNumber": 1, "Cards": [1, 2, 3]}


def test_get_payload_returns_none_for_invalid_json():
    scanner = _scanner_with_no_log()
    assert scanner._get_payload(["not valid json"], 0) is None


def test_get_payload_returns_none_for_non_json_line():
    """Line doesn't start with '{' → return None without trying to parse."""
    scanner = _scanner_with_no_log()
    assert scanner._get_payload(["plain text without braces"], 0) is None


def test_get_payload_returns_none_when_index_out_of_bounds():
    scanner = _scanner_with_no_log()
    assert scanner._get_payload(["{}"], 99) is None


def test_get_payload_strips_whitespace():
    """Leading/trailing whitespace shouldn't break JSON detection."""
    scanner = _scanner_with_no_log()
    line = '   {"Payload":"{\\"x\\":1}"}   '
    result = scanner._get_payload([line], 0)
    assert result == {"x": 1}


# ---------------------------------------------------------------------------
# ArenaLogScanner — initialization
# ---------------------------------------------------------------------------

def test_scanner_initializes_with_default_callbacks_none():
    scanner = ArenaLogScanner(log_path="/tmp/fake")
    assert scanner.on_pack_update is None
    assert scanner.on_pick is None
    assert scanner.on_draft_start is None


def test_scanner_initializes_with_fresh_state():
    scanner = ArenaLogScanner(log_path="/tmp/fake")
    assert scanner.state.active is False
    assert scanner.state.set_code == ""


def test_scanner_poll_no_op_when_log_missing():
    """poll() should silently return when the log file doesn't exist."""
    scanner = ArenaLogScanner(log_path="/tmp/definitely-not-a-real-path/Player.log")
    # Should not raise.
    scanner.poll()


# ---------------------------------------------------------------------------
# _handle_draft_notify — current MTGA draft pack format (inline JSON, CSV IDs)
# ---------------------------------------------------------------------------

def _stub_resolve(monkeypatch, mapping):
    """Make card_db.resolve return names from `mapping` (id->name) without HTTP."""
    monkeypatch.setattr(
        "draft_helper.log_scanner.card_db.resolve",
        lambda ids: {str(i): mapping.get(str(i), f"Unknown({i})") for i in ids},
    )


def test_handle_draft_notify_parses_inline_csv_packcards(monkeypatch):
    """Regression: modern MTGA logs the pack as a Draft.Notify line with the
    JSON INLINE (same line) and PackCards a comma-separated STRING of IDs —
    not the next-line double-encoded list the old handler assumed."""
    _stub_resolve(monkeypatch, {"105009": "Stolen Stark Tech",
                                "104989": "Decoy Ploy",
                                "104911": "Kree Commandos"})
    s = ArenaLogScanner(log_path="/tmp/fake")
    packs = []
    s.on_pack_update = packs.append
    line = ('[UnityCrossThreadLogger]Draft.Notify '
            '{"draftId":"abc","SelfPick":6,"SelfPack":2,'
            '"PackCards":"105009,104989,104911"}')
    s._handle_draft_notify(line)
    assert s.state.pack_number == 2
    assert s.state.pick_number == 6
    assert s.state.current_pack == ["Stolen Stark Tech", "Decoy Ploy", "Kree Commandos"]
    assert packs == [["Stolen Stark Tech", "Decoy Ploy", "Kree Commandos"]]


def test_handle_draft_notify_ignores_line_without_packcards(monkeypatch):
    _stub_resolve(monkeypatch, {})
    s = ArenaLogScanner(log_path="/tmp/fake")
    fired = []
    s.on_pack_update = fired.append
    s._handle_draft_notify('Draft.Notify {"draftId":"abc","SelfPick":1,"SelfPack":1}')
    assert fired == []
    assert s.state.current_pack == []


def test_handle_draft_notify_infers_original_pack_size(monkeypatch):
    """Original pack size = cards remaining + picks already made this pack."""
    _stub_resolve(monkeypatch, {str(i): f"C{i}" for i in range(200)})
    s = ArenaLogScanner(log_path="/tmp/fake")
    ids = ",".join(str(100 + n) for n in range(10))  # 10 cards left
    s._handle_draft_notify(
        'Draft.Notify {"SelfPick":5,"SelfPack":1,"PackCards":"' + ids + '"}')
    # pick 5 → 4 already taken this pack → original size 14
    assert s.state.original_pack_size == 14


# ---------------------------------------------------------------------------
# _handle_make_pick — the card the player submitted
# ---------------------------------------------------------------------------

def test_handle_make_pick_extracts_grpid_and_fires_on_pick(monkeypatch):
    _stub_resolve(monkeypatch, {"105119": "Super Suit"})
    s = ArenaLogScanner(log_path="/tmp/fake")
    picks = []
    s.on_pick = picks.append
    line = ('[UnityCrossThreadLogger]==> EventPlayerDraftMakePick '
            r'{"id":"x","request":"{\"DraftId\":\"d\",\"GrpIds\":[105119],'
            r'\"Pack\":1,\"Pick\":11}"}')
    s._handle_make_pick(line)
    assert picks == ["Super Suit"]
    assert s.state.picked_ids == ["105119"]
    assert s.state.picked_cards == ["Super Suit"]


def test_handle_make_pick_deduplicates_repeated_grpid(monkeypatch):
    """The same pick line re-scanned (e.g. resync) must not double-count."""
    _stub_resolve(monkeypatch, {"105119": "Super Suit"})
    s = ArenaLogScanner(log_path="/tmp/fake")
    picks = []
    s.on_pick = picks.append
    line = (r'==> EventPlayerDraftMakePick {"request":"{\"GrpIds\":[105119],'
            r'\"Pack\":1,\"Pick\":11}"}')
    s._handle_make_pick(line)
    s._handle_make_pick(line)
    assert picks == ["Super Suit"]  # fired once, not twice


# ---------------------------------------------------------------------------
# _parse — end-to-end routing (the original bug was in routing, not just the
# handlers, so exercise the full dispatch path)
# ---------------------------------------------------------------------------

def test_parse_routes_draft_notify_to_pack_update(monkeypatch):
    """A Draft.Notify line fed through _parse must reach _handle_draft_notify
    and fire on_pack_update — NOT the old _get_payload/_handle_premier_pack
    path that read the wrong (next) line."""
    _stub_resolve(monkeypatch, {"1": "Alpha", "2": "Beta"})
    s = ArenaLogScanner(log_path="/tmp/fake")
    packs = []
    s.on_pack_update = lambda c: packs.append(list(c))
    content = '[UnityCrossThreadLogger]Draft.Notify {"SelfPick":1,"SelfPack":1,"PackCards":"1,2"}\n'
    s._parse(content)
    assert packs == [["Alpha", "Beta"]]


def test_parse_routes_make_pick_to_on_pick(monkeypatch):
    _stub_resolve(monkeypatch, {"105119": "Super Suit"})
    s = ArenaLogScanner(log_path="/tmp/fake")
    picks = []
    s.on_pick = picks.append
    content = (r'==> EventPlayerDraftMakePick {"request":"{\"GrpIds\":[105119],'
               r'\"Pack\":1,\"Pick\":1}"}' + '\n')
    s._parse(content)
    assert picks == ["Super Suit"]


def test_parse_end_to_end_premier_draft_sequence(monkeypatch):
    """Realistic resumed-Premier-Draft slice: InternalEventName sets the set,
    a Draft.Notify shows the pack, a pick is submitted, then the next
    Draft.Notify shows the reduced pack. State should reflect all of it."""
    _stub_resolve(monkeypatch, {"1": "Alpha", "2": "Beta", "3": "Gamma"})
    s = ArenaLogScanner(log_path="/tmp/fake")
    picks, packs = [], []
    s.on_pick = picks.append
    s.on_pack_update = lambda c: packs.append(list(c))
    content = (
        '"InternalEventName":"PremierDraft_MSH_20260623"\n'
        '[UnityCrossThreadLogger]Draft.Notify {"SelfPick":1,"SelfPack":1,"PackCards":"1,2,3"}\n'
        r'==> EventPlayerDraftMakePick {"request":"{\"GrpIds\":[1],\"Pack\":1,\"Pick\":1}"}'
        + '\n'
        '[UnityCrossThreadLogger]Draft.Notify {"SelfPick":2,"SelfPack":1,"PackCards":"2,3"}\n'
    )
    s._parse(content)
    assert s.state.set_code == "MSH"
    assert s.state.draft_format == "PremierDraft"
    assert picks == ["Alpha"]
    assert s.state.current_pack == ["Beta", "Gamma"]
    assert s.state.pack_number == 1
    assert s.state.pick_number == 2


def test_parse_pack_transition_updates_pack_number(monkeypatch):
    """Moving from pack 1 to pack 2 updates pack_number and re-infers the
    original pack size for the new pack."""
    _stub_resolve(monkeypatch, {str(i): f"C{i}" for i in range(300)})
    s = ArenaLogScanner(log_path="/tmp/fake")
    ids1 = ",".join(str(i) for i in range(10))          # pack1 pick5, 10 left
    ids2 = ",".join(str(i) for i in range(100, 114))     # pack2 pick1, 14 cards
    s._parse('Draft.Notify {"SelfPick":5,"SelfPack":1,"PackCards":"' + ids1 + '"}\n')
    assert s.state.pack_number == 1
    assert s.state.original_pack_size == 14              # 10 + 4 already taken
    s._parse('Draft.Notify {"SelfPick":1,"SelfPack":2,"PackCards":"' + ids2 + '"}\n')
    assert s.state.pack_number == 2
    assert s.state.original_pack_size == 14


def test_parse_make_pick_dedups_across_reparse(monkeypatch):
    """The same pick line seen twice (e.g. overlapping reads) must fire
    on_pick only once — guarded by picked_ids."""
    _stub_resolve(monkeypatch, {"105119": "Super Suit"})
    s = ArenaLogScanner(log_path="/tmp/fake")
    picks = []
    s.on_pick = picks.append
    line = (r'==> EventPlayerDraftMakePick {"request":"{\"GrpIds\":[105119],'
            r'\"Pack\":1,\"Pick\":1}"}' + '\n')
    s._parse(line)
    s._parse(line)
    assert picks == ["Super Suit"]
