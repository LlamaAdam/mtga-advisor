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
