from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BoardCard:
    name: str
    arena_id: str
    instance_id: int
    power: int
    toughness: int
    keywords: list[str]
    tapped: bool = False
    attacking: bool = False


@dataclass
class HandCard:
    name: str
    arena_id: str
    instance_id: int
    mana_cost: str     # e.g. "{1}{R}"
    cmc: int
    colors: list[str]  # e.g. ["R"]
    castable: bool = False


@dataclass
class Player:
    seat_id: int
    life: int
    board: list[BoardCard] = field(default_factory=list)
    hand: list[HandCard] = field(default_factory=list)
    mana_available: int = 0
    mana_colors: list[str] = field(default_factory=list)


@dataclass
class RuleAlert:
    severity: str   # "DANGER", "WARNING", "INFO"
    message: str


@dataclass
class GameState:
    turn: int
    phase: str
    active_seat: int
    you: Player
    opponent: Player
    recent_events: list[str] = field(default_factory=list)
    game_id: str = ""
