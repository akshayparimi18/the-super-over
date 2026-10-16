"""Authoritative cricket matchup rules and weighted probability engine for The Super Over."""

from dataclasses import dataclass
from enum import StrEnum
import random
from typing import Any


class BowlerProfile(StrEnum):
    FAST = "FAST"
    SPIN = "SPIN"


class DeliveryType(StrEnum):
    YORKER = "YORKER"
    BOUNCER = "BOUNCER"
    IN_SWINGER = "IN_SWINGER"
    OUT_SWINGER = "OUT_SWINGER"
    OFF_BREAK = "OFF_BREAK"
    LEG_BREAK = "LEG_BREAK"
    GOOGLY = "GOOGLY"
    TOP_SPIN = "TOP_SPIN"
    HALF_VOLLEY = "HALF_VOLLEY"


class BatsmanIntent(StrEnum):
    DEFEND_0 = "DEFEND_0"
    PUSH_1 = "PUSH_1"
    PUSH_2 = "PUSH_2"
    PUSH_3 = "PUSH_3"
    HIT_4 = "HIT_4"
    SLOG_6 = "SLOG_6"


# Aliases for backward compatibility
Delivery = DeliveryType
Shot = BatsmanIntent


# Standard Bowler Inventories
FAST_INVENTORY: dict[str, int] = {
    DeliveryType.YORKER.value: 1,
    DeliveryType.BOUNCER.value: 1,
    DeliveryType.IN_SWINGER.value: 1,
    DeliveryType.OUT_SWINGER.value: 1,
    DeliveryType.HALF_VOLLEY.value: 2,
}

SPIN_INVENTORY: dict[str, int] = {
    DeliveryType.OFF_BREAK.value: 1,
    DeliveryType.LEG_BREAK.value: 1,
    DeliveryType.GOOGLY.value: 1,
    DeliveryType.TOP_SPIN.value: 1,
    DeliveryType.HALF_VOLLEY.value: 2,
}


def get_initial_inventory(profile: BowlerProfile | str) -> dict[str, int]:
    """Return a fresh delivery inventory for the selected bowler profile."""
    val = profile.value if isinstance(profile, BowlerProfile) else str(profile).upper()
    if val == BowlerProfile.FAST.value:
        return dict(FAST_INVENTORY)
    elif val == BowlerProfile.SPIN.value:
        return dict(SPIN_INVENTORY)
    raise ValueError(f"Unknown bowler profile: {profile}")


def consume_delivery(inventory: dict[str, int], delivery: DeliveryType | str) -> None:
    """Decrement the selected delivery from bowler inventory; raise ValueError if exhausted."""
    key = delivery.value if isinstance(delivery, DeliveryType) else str(delivery).upper()
    count = inventory.get(key, 0)
    if count <= 0:
        raise ValueError(f"Illegal move: Delivery '{key}' has 0 remaining stock in inventory.")
    inventory[key] = count - 1


@dataclass(frozen=True)
class Outcome:
    runs: int = 0
    wicket: bool = False
    wide: bool = False
    status: str | None = None


# Comprehensive 9 DeliveryType x 6 BatsmanIntent Weighted Risk/Reward Matrix
# Structure: (DeliveryType, BatsmanIntent) -> (list[Outcome], list[int]) where sum(weights) == 100
MATCHUP_RULES: dict[tuple[DeliveryType, BatsmanIntent], tuple[list[Outcome], list[int]]] = {
    # ---------------- HALF_VOLLEY (Overpitched: high reward for boundaries, minimal wicket risk) ----------------
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=1)],
        [95, 5],
    ),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=2), Outcome(runs=0)],
        [85, 10, 5],
    ),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.PUSH_2): (
        [Outcome(runs=2), Outcome(runs=1), Outcome(runs=3)],
        [80, 15, 5],
    ),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.PUSH_3): (
        [Outcome(runs=3), Outcome(runs=2), Outcome(runs=4)],
        [75, 15, 10],
    ),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.HIT_4): (
        [Outcome(runs=4), Outcome(runs=6), Outcome(runs=2), Outcome(runs=0, wicket=True)],
        [80, 10, 5, 5],
    ),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.SLOG_6): (
        [Outcome(runs=6), Outcome(runs=4), Outcome(runs=0, wicket=True)],
        [80, 15, 5],
    ),

    # ---------------- YORKER (Pin-point toe-crusher: lethal against reckless slogs) ----------------
    (DeliveryType.YORKER, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [90, 10],
    ),
    (DeliveryType.YORKER, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [70, 20, 10],
    ),
    (DeliveryType.YORKER, BatsmanIntent.PUSH_2): (
        [Outcome(runs=0, wicket=True), Outcome(runs=1), Outcome(runs=2)],
        [65, 25, 10],
    ),
    (DeliveryType.YORKER, BatsmanIntent.PUSH_3): (
        [Outcome(runs=0, wicket=True), Outcome(runs=1), Outcome(runs=2)],
        [75, 20, 5],
    ),
    (DeliveryType.YORKER, BatsmanIntent.HIT_4): (
        [Outcome(runs=1), Outcome(runs=0, wicket=True), Outcome(runs=4)],
        [60, 30, 10],
    ),
    (DeliveryType.YORKER, BatsmanIntent.SLOG_6): (
        [Outcome(runs=0, wicket=True), Outcome(runs=1), Outcome(runs=6)],
        [85, 10, 5],
    ),

    # ---------------- BOUNCER (Short, aggressive delivery) ----------------
    (DeliveryType.BOUNCER, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=1, wide=True), Outcome(runs=0, wicket=True)],
        [85, 10, 5],
    ),
    (DeliveryType.BOUNCER, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [75, 15, 10],
    ),
    (DeliveryType.BOUNCER, BatsmanIntent.PUSH_2): (
        [Outcome(runs=2), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [70, 20, 10],
    ),
    (DeliveryType.BOUNCER, BatsmanIntent.PUSH_3): (
        [Outcome(runs=1), Outcome(runs=2), Outcome(runs=0, wicket=True)],
        [60, 25, 15],
    ),
    (DeliveryType.BOUNCER, BatsmanIntent.HIT_4): (
        [Outcome(runs=4), Outcome(runs=0, wicket=True), Outcome(runs=1)],
        [65, 25, 10],
    ),
    (DeliveryType.BOUNCER, BatsmanIntent.SLOG_6): (
        [Outcome(runs=0, wicket=True), Outcome(runs=6), Outcome(runs=1)],
        [75, 15, 10],
    ),

    # ---------------- IN_SWINGER (Late inswing towards pads/stumps) ----------------
    (DeliveryType.IN_SWINGER, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [90, 10],
    ),
    (DeliveryType.IN_SWINGER, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [80, 10, 10],
    ),
    (DeliveryType.IN_SWINGER, BatsmanIntent.PUSH_2): (
        [Outcome(runs=2), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [70, 20, 10],
    ),
    (DeliveryType.IN_SWINGER, BatsmanIntent.PUSH_3): (
        [Outcome(runs=0, wicket=True), Outcome(runs=2), Outcome(runs=1)],
        [60, 25, 15],
    ),
    (DeliveryType.IN_SWINGER, BatsmanIntent.HIT_4): (
        [Outcome(runs=4), Outcome(runs=0, wicket=True), Outcome(runs=2)],
        [65, 25, 10],
    ),
    (DeliveryType.IN_SWINGER, BatsmanIntent.SLOG_6): (
        [Outcome(runs=0, wicket=True), Outcome(runs=6), Outcome(runs=4)],
        [80, 10, 10],
    ),

    # ---------------- OUT_SWINGER (Moving away toward slip cordon) ----------------
    (DeliveryType.OUT_SWINGER, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [95, 5],
    ),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [80, 15, 5],
    ),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.PUSH_2): (
        [Outcome(runs=2), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [75, 15, 10],
    ),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.PUSH_3): (
        [Outcome(runs=0), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [55, 30, 15],
    ),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.HIT_4): (
        [Outcome(runs=0, wicket=True), Outcome(runs=4), Outcome(runs=1)],
        [65, 25, 10],
    ),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.SLOG_6): (
        [Outcome(runs=0, wicket=True), Outcome(runs=6), Outcome(runs=1)],
        [80, 10, 10],
    ),

    # ---------------- OFF_BREAK (Off-spinner turning into right-hander) ----------------
    (DeliveryType.OFF_BREAK, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [90, 10],
    ),
    (DeliveryType.OFF_BREAK, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=2)],
        [80, 15, 5],
    ),
    (DeliveryType.OFF_BREAK, BatsmanIntent.PUSH_2): (
        [Outcome(runs=2), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [75, 15, 10],
    ),
    (DeliveryType.OFF_BREAK, BatsmanIntent.PUSH_3): (
        [Outcome(runs=1), Outcome(runs=2), Outcome(runs=0, wicket=True)],
        [60, 25, 15],
    ),
    (DeliveryType.OFF_BREAK, BatsmanIntent.HIT_4): (
        [Outcome(runs=4), Outcome(runs=0, wicket=True), Outcome(runs=1)],
        [65, 25, 10],
    ),
    (DeliveryType.OFF_BREAK, BatsmanIntent.SLOG_6): (
        [Outcome(runs=0, wicket=True), Outcome(runs=6), Outcome(runs=4)],
        [75, 15, 10],
    ),

    # ---------------- LEG_BREAK (Sharply turning away) ----------------
    (DeliveryType.LEG_BREAK, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [90, 10],
    ),
    (DeliveryType.LEG_BREAK, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=2)],
        [80, 15, 5],
    ),
    (DeliveryType.LEG_BREAK, BatsmanIntent.PUSH_2): (
        [Outcome(runs=2), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [70, 20, 10],
    ),
    (DeliveryType.LEG_BREAK, BatsmanIntent.PUSH_3): (
        [Outcome(runs=0), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [60, 25, 15],
    ),
    (DeliveryType.LEG_BREAK, BatsmanIntent.HIT_4): (
        [Outcome(runs=0, wicket=True), Outcome(runs=4), Outcome(runs=1)],
        [65, 25, 10],
    ),
    (DeliveryType.LEG_BREAK, BatsmanIntent.SLOG_6): (
        [Outcome(runs=6), Outcome(runs=0, wicket=True), Outcome(runs=1)],
        [60, 30, 10],
    ),

    # ---------------- GOOGLY (Deceptive wrong-un turning back in) ----------------
    (DeliveryType.GOOGLY, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [90, 10],
    ),
    (DeliveryType.GOOGLY, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [75, 15, 10],
    ),
    (DeliveryType.GOOGLY, BatsmanIntent.PUSH_2): (
        [Outcome(runs=0, wicket=True), Outcome(runs=1), Outcome(runs=2)],
        [65, 25, 10],
    ),
    (DeliveryType.GOOGLY, BatsmanIntent.PUSH_3): (
        [Outcome(runs=0, wicket=True), Outcome(runs=1), Outcome(runs=2)],
        [70, 20, 10],
    ),
    (DeliveryType.GOOGLY, BatsmanIntent.HIT_4): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True), Outcome(runs=4)],
        [55, 35, 10],
    ),
    (DeliveryType.GOOGLY, BatsmanIntent.SLOG_6): (
        [Outcome(runs=0, wicket=True), Outcome(runs=6), Outcome(runs=1)],
        [80, 10, 10],
    ),

    # ---------------- TOP_SPIN (Extra bounce and direct flight) ----------------
    (DeliveryType.TOP_SPIN, BatsmanIntent.DEFEND_0): (
        [Outcome(runs=0), Outcome(runs=0, wicket=True)],
        [90, 10],
    ),
    (DeliveryType.TOP_SPIN, BatsmanIntent.PUSH_1): (
        [Outcome(runs=1), Outcome(runs=0), Outcome(runs=2)],
        [80, 10, 10],
    ),
    (DeliveryType.TOP_SPIN, BatsmanIntent.PUSH_2): (
        [Outcome(runs=2), Outcome(runs=1), Outcome(runs=0, wicket=True)],
        [75, 15, 10],
    ),
    (DeliveryType.TOP_SPIN, BatsmanIntent.PUSH_3): (
        [Outcome(runs=3), Outcome(runs=2), Outcome(runs=0, wicket=True)],
        [65, 20, 15],
    ),
    (DeliveryType.TOP_SPIN, BatsmanIntent.HIT_4): (
        [Outcome(runs=4), Outcome(runs=0, wicket=True), Outcome(runs=2)],
        [65, 25, 10],
    ),
    (DeliveryType.TOP_SPIN, BatsmanIntent.SLOG_6): (
        [Outcome(runs=0, wicket=True), Outcome(runs=6), Outcome(runs=4)],
        [75, 15, 10],
    ),
}

LEGAL_BALLS_PER_INNINGS = 6
DEFAULT_WICKETS_TO_END_INNINGS = 1


def check_innings_state(room: Any) -> str | None:
    """Implement the innings state check for match progression and win conditions."""
    if room.current_innings == 1:
        if (
            room.wickets >= DEFAULT_WICKETS_TO_END_INNINGS
            or room.legal_balls >= LEGAL_BALLS_PER_INNINGS
        ):
            room.target_score = room.runs + 1
            room.current_innings = 2
            room.runs = 0
            room.wickets = 0
            room.legal_balls = 0
            room.bowler_profile = None
            room.bowler_inventory = {}
            room.current_phase = "SELECT_PROFILE"
            # swap the host/guest roles
            for player in room.players.values():
                player.role = "batsman" if player.role == "bowler" else "bowler"
            return "INNINGS_BREAK"
    elif room.current_innings == 2:
        if room.target_score is not None and room.runs >= room.target_score:
            room.winner = "Team 2"
            room.current_phase = "MATCH_OVER"
            return "MATCH_OVER"
        elif (
            room.wickets >= DEFAULT_WICKETS_TO_END_INNINGS
            or room.legal_balls >= LEGAL_BALLS_PER_INNINGS
        ):
            if room.target_score is not None and room.runs == room.target_score - 1:
                room.winner = "Tie"
            else:
                room.winner = "Team 1"
            room.current_phase = "MATCH_OVER"
            return "MATCH_OVER"
    return None


def resolve_matchup(
    delivery: DeliveryType | str,
    shot: BatsmanIntent | str,
    room: Any = None,
    bowler_inventory: dict[str, int] | None = None,
) -> Outcome:
    """Return the outcome for a delivery and batsman intent pair using weighted probabilities."""
    d = DeliveryType(delivery) if not isinstance(delivery, DeliveryType) else delivery
    s = BatsmanIntent(shot) if not isinstance(shot, BatsmanIntent) else shot

    if bowler_inventory is not None:
        consume_delivery(bowler_inventory, d)
    elif room is not None and hasattr(room, "bowler_inventory") and room.bowler_inventory:
        consume_delivery(room.bowler_inventory, d)

    outcomes, weights = MATCHUP_RULES[(d, s)]
    selected = random.choices(outcomes, weights=weights, k=1)[0]

    status = None
    if room is not None:
        status = check_innings_state(room)
    return Outcome(
        runs=selected.runs,
        wicket=selected.wicket,
        wide=selected.wide,
        status=status,
    )
