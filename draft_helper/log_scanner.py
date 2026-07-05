"""
Arena Player.log scanner — corrected for actual MTGA log format.

Actual log structure (confirmed from live log):

  Draft join:
    [UnityCrossThreadLogger]==> EventJoin {"id":"...","request":"{\"EventName\":\"QuickDraft_FDN_20260323\",...}"}

  Pack shown / pick response (bot/quick draft):
    <== BotDraftDraftStatus(GUID)
    {"CurrentModule":"BotDraft","Payload":"{\\"DraftPack\\":[\\"93913\\",...],\\"PickedCards\\":[...],\\"PackNumber\\":0,\\"PickNumber\\":0,...}"}

    <== BotDraftDraftPick(GUID)
    {"CurrentModule":"BotDraft","Payload":"{\\"DraftPack\\":[\\"93856\\",...],\\"PickedCards\\":[\\"93913\\"],\\"PackNumber\\":0,\\"PickNumber\\":1,...}"}

  Cards are Arena numeric IDs — resolved to names via card_db.py (Scryfall).
  PickedCards grows by one after each pick, so we diff to detect what was picked.
"""

import json
import os
import re
from typing import Optional

from . import config
from . import card_db


class DraftState:
    def __init__(self):
        self.set_code: str = ""
        self.draft_format: str = "QuickDraft"
        self.pack_number: int = 1      # 1-indexed for display
        self.pick_number: int = 1      # 1-indexed for display
        self.current_pack: list[str] = []    # card names in current pack
        self.picked_cards: list[str] = []    # card names picked so far (entire draft, cumulative)
        self.picked_ids: list[str] = []      # raw Arena IDs picked (for diffing)
        self.original_pack_size: int = 0     # inferred full size of this pack
        self.active: bool = False

    def reset(self):
        self.__init__()


class ArenaLogScanner:
    """
    Tails Arena's Player.log and fires callbacks on draft events.

    Callbacks (assign before calling recover_current_draft / poll):
      on_draft_start(set_code, draft_format)
      on_pack_update(card_names)
      on_pick(card_name)
    """

    def __init__(self, log_path: str = config.ARENA_LOG_PATH):
        self.log_path = log_path
        self.state = DraftState()
        self._file_pos: int = 0
        self._last_mtime: float = 0

        self.on_pack_update = None
        self.on_pick        = None
        self.on_draft_start = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def poll(self):
        """Check for new log content. Call in a loop."""
        if not os.path.exists(self.log_path):
            return
        try:
            mtime = os.path.getmtime(self.log_path)
        except OSError:
            return
        if mtime == self._last_mtime:
            return
        self._last_mtime = mtime
        self._read_new_content()

    def recover_current_draft(self):
        """
        Read the entire existing log to recover any in-progress draft.
        Sets _file_pos to end-of-file so poll() continues tailing.
        """
        self._full_scan(fire_start_callback=True)

    def resync(self):
        """
        Re-read the full log and rebuild picked cards + current pack from
        the most recent pack state — without re-triggering the ratings fetch.

        Use this when you suspect picks were missed (e.g. press R in the overlay).
        Returns True if an active draft was found.
        """
        return self._full_scan(fire_start_callback=False)

    def _full_scan(self, fire_start_callback: bool = True) -> bool:
        """
        Core full-log scan used by both recover_current_draft() and resync().
        If fire_start_callback is False, on_draft_start is suppressed so
        ratings are not re-fetched unnecessarily.
        """
        if not os.path.exists(self.log_path):
            print(f"[scanner] Log not found: {self.log_path}")
            return False

        label = "Scanning" if fire_start_callback else "Resyncing"
        print(f"[scanner] {label} log for current draft state...")

        # Temporarily suppress on_draft_start if we don't want to re-fetch
        saved_cb = self.on_draft_start
        if not fire_start_callback:
            self.on_draft_start = None

        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                self._file_pos = f.tell()
            self._last_mtime = os.path.getmtime(self.log_path)

            # Pre-scan for set code so we can preload card names BEFORE
            # processing pack events — fixes Unknown(XXXXX) during recovery.
            set_info = self._extract_set_code(content)
            if set_info:
                set_code, _ = set_info
                card_db.preload_set(set_code)   # blocking, ensures names ready

            # Reset state so we rebuild cleanly from scratch
            prev_set_code = self.state.set_code
            prev_format   = self.state.draft_format
            self.state.reset()
            # Preserve set/format so pack updates still work if draft_start isn't re-fired
            if not fire_start_callback:
                self.state.set_code     = prev_set_code or (set_info[0] if set_info else "")
                self.state.draft_format = prev_format   or (set_info[1] if set_info else "")
                self.state.active       = True

            self._parse(content)

            # If we processed picks/packs but active was cleared by some edge-case
            # event, re-infer from data rather than declare no draft found.
            if not self.state.active and self.state.set_code and (
                self.state.current_pack or self.state.picked_cards
            ):
                self.state.active = True

            if self.state.active:
                print(f"[scanner] {'Recovered' if fire_start_callback else 'Resynced'}: "
                      f"{self.state.set_code} {self.state.draft_format} | "
                      f"Pack {self.state.pack_number} Pick {self.state.pick_number} | "
                      f"{len(self.state.picked_cards)} cards picked")
            else:
                print("[scanner] No active draft found in log.")
        except OSError as e:
            print(f"[scanner] Error reading log: {e}")
        finally:
            self.on_draft_start = saved_cb

        return self.state.active

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_new_content(self):
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._file_pos)
                content = f.read()
                self._file_pos = f.tell()
        except OSError:
            return
        if content:
            self._parse(content)

    def _extract_set_code(self, content: str) -> Optional[tuple[str, str]]:
        """
        Quick pre-scan: find the most recent draft event name and return
        (set_code, draft_format). Returns None if not found.

        Checks two sources (in priority order):
          1. EventJoin lines — present when a draft is joined in this session
          2. InternalEventName in the Courses state dump — present when MTGA
             resumes a draft from a previous session (no EventJoin re-logged)
        """
        _fmt_map = {"QuickDraft": "QuickDraft", "BotDraft": "QuickDraft",
                    "PremierDraft": "PremierDraft", "TradDraft": "TradDraft"}
        _pattern = re.compile(
            r'"(?:EventName|InternalEventName)"\s*:\s*"'
            r'((?:QuickDraft|PremierDraft|TradDraft|BotDraft)_([A-Z0-9]{2,5})_\d+)"'
        )

        result = None
        for line in content.splitlines():
            # Primary: explicit EventJoin
            if "==> EventJoin" in line and "EventName" in line:
                m = _pattern.search(line)
                if m:
                    result = (m.group(2), _fmt_map.get(m.group(1).split("_")[0], "PremierDraft"))

            # Fallback: InternalEventName in Courses/state dump (resumed draft).
            # Any draft format (PremierDraft/QuickDraft/BotDraft/TradDraft) —
            # the regex validates the actual value; don't pre-filter on one
            # format string (resumed Premier drafts carry PremierDraft here,
            # not BotDraft).
            elif "InternalEventName" in line and "Draft" in line:
                m = _pattern.search(line)
                if m:
                    candidate = (m.group(2), _fmt_map.get(m.group(1).split("_")[0], "PremierDraft"))
                    if result is None:   # only use as fallback
                        result = candidate

        return result   # returns the LAST EventJoin match, or first InternalEventName match

    def _parse(self, content: str):
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

            # Draft join — detect set code and format
            if "==> EventJoin" in line and "EventName" in line:
                self._handle_event_join(line)

            # InternalEventName in a Courses/state dump (resumed drafts).
            # Fallback signal only: a state dump can list OLD completed
            # courses, so it must never override an already-active draft.
            elif "InternalEventName" in line and "Draft" in line:
                self._handle_event_join(line, fallback=True)

            # Bot/Quick Draft: pack shown at start of draft
            elif line.startswith("<== BotDraftDraftStatus("):
                payload = self._get_payload(lines, i + 1)
                if payload:
                    self._handle_bot_pack(payload)

            # Bot/Quick Draft: response after making a pick (new pack state)
            elif line.startswith("<== BotDraftDraftPick("):
                payload = self._get_payload(lines, i + 1)
                if payload:
                    self._handle_bot_pack(payload)

            # Premier / Quick Draft: current pack via Draft.Notify.
            # The JSON is INLINE on this same line (not the next), and its
            # PackCards field is a comma-separated string of Arena IDs — so
            # it needs a dedicated handler, not _get_payload/_handle_premier_pack.
            elif "Draft.Notify" in line:
                self._handle_draft_notify(line)

            # Premier / Quick Draft: the card the player just submitted.
            elif "==> EventPlayerDraftMakePick" in line and "GrpIds" in line:
                self._handle_make_pick(line)

            # Legacy Premier Draft pack (older MTGA log format)
            elif line.startswith("<== Draft_CompleteDraft(") or \
                 line.startswith("<== Draft_MakeHumanDraftPick("):
                payload = self._get_payload(lines, i + 1)
                if payload:
                    self._handle_premier_pack(payload)

            i += 1

    def _get_payload(self, lines: list[str], idx: int) -> dict | None:
        """
        Read the JSON line immediately after a <== event line.
        The Payload field is a double-encoded JSON string — decode both layers.
        """
        if idx >= len(lines):
            return None
        raw_line = lines[idx].strip()
        if not raw_line.startswith("{"):
            return None
        try:
            outer = json.loads(raw_line)
            payload_str = outer.get("Payload", "")
            if isinstance(payload_str, dict):
                # Already-decoded object — some log variants skip the
                # double encoding.
                return payload_str
            if isinstance(payload_str, str) and payload_str:
                return json.loads(payload_str)
            if payload_str:
                # Present but neither string nor object (number, list…) —
                # malformed; skip rather than crash the poll loop.
                return None
            # Some events have the data directly in the outer object
            return outer
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_event_join(self, line: str, fallback: bool = False):
        """Detect draft start from EventJoin or InternalEventName (resumed draft).

        fallback=True marks the InternalEventName path: it exists to recover
        a resumed draft when nothing is active, but a Courses/state dump can
        also list old, completed courses — so it must never displace a draft
        that is already active.
        """
        if fallback and self.state.active:
            return
        match = re.search(
            r'"(?:EventName|InternalEventName)"\s*:\s*"'
            r'((?:QuickDraft|PremierDraft|TradDraft|BotDraft)_([A-Z0-9]{2,5})_\d+)"',
            line,
        )
        if not match:
            return

        event_name = match.group(1)
        set_code   = match.group(2)
        fmt_raw    = event_name.split("_")[0]
        fmt_map    = {
            "QuickDraft":  "QuickDraft",
            "BotDraft":    "QuickDraft",
            "PremierDraft":"PremierDraft",
            "TradDraft":   "TradDraft",
        }
        draft_format = fmt_map.get(fmt_raw, "PremierDraft")

        # Only reset if this is a new draft (different set or format)
        if (self.state.set_code != set_code or
                self.state.draft_format != draft_format or
                not self.state.active):
            self.state.reset()
            self.state.set_code = set_code
            self.state.draft_format = draft_format
            self.state.active = True
            print(f"[scanner] Draft started: {set_code} {draft_format}")
            if self.on_draft_start:
                self.on_draft_start(set_code, draft_format)

    def _handle_bot_pack(self, payload: dict):
        """Handle BotDraftDraftStatus / BotDraftDraftPick payload."""
        # Only hard-stop on explicit "Complete" — ignore unknown status values
        if payload.get("DraftStatus") == "Complete":
            self.state.active = False
            return

        # Skip if no pack data at all
        if not payload.get("DraftPack"):
            return

        pack_number = int(payload.get("PackNumber", 0)) + 1   # 0-indexed → 1-indexed
        pick_number = int(payload.get("PickNumber", 0)) + 1

        raw_pack    = payload.get("DraftPack", [])
        raw_picked  = payload.get("PickedCards", [])

        # Resolve Arena IDs → card names
        all_ids = list(set(raw_pack + raw_picked))
        if all_ids:
            id_map = card_db.resolve(all_ids)
        else:
            id_map = {}

        pack_names   = [id_map.get(str(i), f"Unknown({i})") for i in raw_pack]
        picked_names = [id_map.get(str(i), f"Unknown({i})") for i in raw_picked]

        # Detect newly picked card (PickedCards grew by 1)
        new_picked_ids = [str(i) for i in raw_picked]
        prev_ids       = set(self.state.picked_ids)
        new_ids        = [i for i in new_picked_ids if i not in prev_ids]

        # Infer original pack size: current cards + picks made THIS pack.
        # PickedCards is cumulative across the whole draft, so we use
        # pick_number-1 (0-based picks in current pack) instead of len(raw_picked).
        inferred_size = len(raw_pack) + (pick_number - 1)
        if pack_number != self.state.pack_number:
            # New pack — reset original size
            self.state.original_pack_size = inferred_size
        elif inferred_size > self.state.original_pack_size:
            self.state.original_pack_size = inferred_size

        self.state.pack_number  = pack_number
        self.state.pick_number  = pick_number
        self.state.current_pack = pack_names
        self.state.picked_cards = picked_names
        self.state.picked_ids   = new_picked_ids

        # Fire pick callback for each newly picked card
        for nid in new_ids:
            picked_name = id_map.get(nid, f"Unknown({nid})")
            if self.on_pick:
                self.on_pick(picked_name)

        # Fire pack update
        if pack_names and self.on_pack_update:
            self.on_pack_update(pack_names)

    def _handle_premier_pack(self, payload: dict):
        """Handle Premier Draft pack/pick events (structure TBD from live log)."""
        # Premier draft may use card names or IDs depending on MTGA version.
        # We handle both cases here.
        pack_cards = (
            payload.get("SelfPack") or
            payload.get("PackCards") or
            payload.get("DraftPack") or
            []
        )
        picked = payload.get("PickedCards") or payload.get("takenCards") or []

        if not pack_cards:
            return

        # Determine if these are IDs or names
        if pack_cards and str(pack_cards[0]).isdigit():
            all_ids = list(set([str(c) for c in pack_cards + picked]))
            id_map  = card_db.resolve(all_ids)
            pack_names   = [id_map.get(str(c), str(c)) for c in pack_cards]
            picked_names = [id_map.get(str(c), str(c)) for c in picked]
        else:
            pack_names   = [str(c) for c in pack_cards]
            picked_names = [str(c) for c in picked]

        # Detect new picks
        prev_set = set(self.state.picked_cards)
        for name in picked_names:
            if name not in prev_set and self.on_pick:
                self.on_pick(name)

        self.state.current_pack = pack_names
        self.state.picked_cards = picked_names
        self.state.pack_number  = int(payload.get("PackNumber", 0)) + 1
        self.state.pick_number  = int(payload.get("PickNumber", 0)) + 1

        if pack_names and self.on_pack_update:
            self.on_pack_update(pack_names)

    def _handle_draft_notify(self, line: str):
        """Handle the current MTGA draft pack event: ``Draft.Notify``.

        Unlike the older ``<== Draft_...`` events, the JSON here is INLINE on
        the same line (after the ``Draft.Notify`` marker), and its
        ``PackCards`` field is a comma-separated STRING of Arena IDs — not a
        JSON list. ``SelfPack`` / ``SelfPick`` are the 1-indexed pack/pick.
        Example:
          [UnityCrossThreadLogger]Draft.Notify {"draftId":"...","SelfPick":6,
              "SelfPack":1,"PackCards":"105009,104989,104911,..."}
        """
        # Extract the payload by brace balance (raw_decode), not a greedy
        # regex to the LAST '}' — trailing diagnostics containing braces
        # would otherwise corrupt the capture and drop every pack.
        marker = line.find("Draft.Notify")
        if marker == -1:
            return
        brace = line.find("{", marker)
        if brace == -1:
            return
        try:
            payload, _ = json.JSONDecoder().raw_decode(line[brace:])
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return

        raw = payload.get("PackCards")
        if not raw:
            return
        # CSV string is the normal shape; tolerate a JSON list too. Only
        # numeric tokens are real Arena ids — drop garbage instead of
        # feeding it to card_db.resolve.
        tokens = ([str(x) for x in raw] if isinstance(raw, list)
                  else str(raw).split(","))
        pack_ids = [t.strip() for t in tokens if t.strip().isdigit()]
        if not pack_ids:
            return

        pack_number = int(payload.get("SelfPack", 1))
        pick_number = int(payload.get("SelfPick", 1))

        id_map = card_db.resolve(pack_ids)
        pack_names = [id_map.get(str(i), f"Unknown({i})") for i in pack_ids]

        # Infer original pack size: current cards + picks already made this pack.
        inferred_size = len(pack_ids) + (pick_number - 1)
        if pack_number != self.state.pack_number:
            self.state.original_pack_size = inferred_size
        elif inferred_size > self.state.original_pack_size:
            self.state.original_pack_size = inferred_size

        self.state.pack_number  = pack_number
        self.state.pick_number  = pick_number
        self.state.current_pack = pack_names

        if pack_names and self.on_pack_update:
            self.on_pack_update(pack_names)

    def _handle_make_pick(self, line: str):
        """Track the card the player submitted via ``EventPlayerDraftMakePick``.

        The raw log line embeds the pick as an escaped JSON string, e.g.
          ==> EventPlayerDraftMakePick {"id":"...","request":"{\\"DraftId\\":
              \\"...\\",\\"GrpIds\\":[105119],\\"Pack\\":1,\\"Pick\\":2}"}
        Parse both JSON layers properly (a raw-line regex can be fooled by a
        'GrpIds' lookalike inside another string field, and misses multi-card
        picks); fall back to a regex only if the JSON doesn't decode.
        Feeds the deck-color tracker (drives the best-pick highlight).
        """
        gids = self._extract_grpids(line)
        new_gids = [g for g in gids if g not in self.state.picked_ids]
        if not new_gids:
            return
        id_map = card_db.resolve(new_gids)
        for gid in new_gids:
            self.state.picked_ids.append(gid)
            name = id_map.get(gid, f"Unknown({gid})")
            self.state.picked_cards.append(name)
            if self.on_pick:
                self.on_pick(name)

    @staticmethod
    def _extract_grpids(line: str) -> list[str]:
        """Pull the GrpIds list from an EventPlayerDraftMakePick line."""
        brace = line.find("{")
        if brace != -1:
            try:
                outer, _ = json.JSONDecoder().raw_decode(line[brace:])
                request = outer.get("request") if isinstance(outer, dict) else None
                if isinstance(request, str) and request:
                    request = json.loads(request)
                if isinstance(request, dict):
                    raw = request.get("GrpIds")
                    if isinstance(raw, list):
                        gids = [str(g) for g in raw if str(g).isdigit()]
                        if gids:
                            return gids
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        # Fallback for lines whose JSON doesn't decode (truncated writes,
        # unforeseen format drift). Accepts multi-id arrays.
        m = re.search(r'GrpIds\\?":\[([\d,\s]+)\]', line)
        if not m:
            return []
        return [t.strip() for t in m.group(1).split(",") if t.strip().isdigit()]
