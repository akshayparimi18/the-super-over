"""Authoritative cricket matchup rules and inventory engine for The Super Over."""

from dataclasses import dataclass
from enum import StrEnum
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
    runs: int
    wicket: bool = False
    wide: bool = False
    status: str | None = None


# Comprehensive 9 Delivery x 6 BatsmanIntent Matchup Matrix
MATCHUP_RULES: dict[tuple[DeliveryType, BatsmanIntent], Outcome] = {
    # HALF_VOLLEY (Overpitched boundary ball: highly rewarding if attacked)
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.PUSH_2): Outcome(runs=2),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.PUSH_3): Outcome(runs=3),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.HIT_4): Outcome(runs=4),
    (DeliveryType.HALF_VOLLEY, BatsmanIntent.SLOG_6): Outcome(runs=6),

    # YORKER (Pace & pin-point yorker: lethal against reckless slogs)
    (DeliveryType.YORKER, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.YORKER, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.YORKER, BatsmanIntent.PUSH_2): Outcome(runs=0, wicket=True),
    (DeliveryType.YORKER, BatsmanIntent.PUSH_3): Outcome(runs=0, wicket=True),
    (DeliveryType.YORKER, BatsmanIntent.HIT_4): Outcome(runs=1),
    (DeliveryType.YORKER, BatsmanIntent.SLOG_6): Outcome(runs=0, wicket=True),

    # BOUNCER (Short, rising delivery)
    (DeliveryType.BOUNCER, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.BOUNCER, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.BOUNCER, BatsmanIntent.PUSH_2): Outcome(runs=2),
    (DeliveryType.BOUNCER, BatsmanIntent.PUSH_3): Outcome(runs=1),
    (DeliveryType.BOUNCER, BatsmanIntent.HIT_4): Outcome(runs=4),
    (DeliveryType.BOUNCER, BatsmanIntent.SLOG_6): Outcome(runs=0, wicket=True),

    # IN_SWINGER (Late swing into the stumps/pads)
    (DeliveryType.IN_SWINGER, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.IN_SWINGER, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.IN_SWINGER, BatsmanIntent.PUSH_2): Outcome(runs=2),
    (DeliveryType.IN_SWINGER, BatsmanIntent.PUSH_3): Outcome(runs=0, wicket=True),
    (DeliveryType.IN_SWINGER, BatsmanIntent.HIT_4): Outcome(runs=4),
    (DeliveryType.IN_SWINGER, BatsmanIntent.SLOG_6): Outcome(runs=0, wicket=True),

    # OUT_SWINGER (Shaping away towards the cordon)
    (DeliveryType.OUT_SWINGER, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.PUSH_2): Outcome(runs=2),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.PUSH_3): Outcome(runs=0),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.HIT_4): Outcome(runs=0, wicket=True),
    (DeliveryType.OUT_SWINGER, BatsmanIntent.SLOG_6): Outcome(runs=0, wicket=True),

    # OFF_BREAK (Spinning into right-hander)
    (DeliveryType.OFF_BREAK, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.OFF_BREAK, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.OFF_BREAK, BatsmanIntent.PUSH_2): Outcome(runs=2),
    (DeliveryType.OFF_BREAK, BatsmanIntent.PUSH_3): Outcome(runs=1),
    (DeliveryType.OFF_BREAK, BatsmanIntent.HIT_4): Outcome(runs=4),
    (DeliveryType.OFF_BREAK, BatsmanIntent.SLOG_6): Outcome(runs=0, wicket=True),

    # LEG_BREAK (Drifting and spinning away sharply)
    (DeliveryType.LEG_BREAK, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.LEG_BREAK, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.LEG_BREAK, BatsmanIntent.PUSH_2): Outcome(runs=2),
    (DeliveryType.LEG_BREAK, BatsmanIntent.PUSH_3): Outcome(runs=0),
    (DeliveryType.LEG_BREAK, BatsmanIntent.HIT_4): Outcome(runs=0, wicket=True),
    (DeliveryType.LEG_BREAK, BatsmanIntent.SLOG_6): Outcome(runs=6),

    # GOOGLY (Disguised wrong-un turning in)
    (DeliveryType.GOOGLY, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.GOOGLY, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.GOOGLY, BatsmanIntent.PUSH_2): Outcome(runs=0, wicket=True),
    (DeliveryType.GOOGLY, BatsmanIntent.PUSH_3): Outcome(runs=0, wicket=True),
    (DeliveryType.GOOGLY, BatsmanIntent.HIT_4): Outcome(runs=0),
    (DeliveryType.GOOGLY, BatsmanIntent.SLOG_6): Outcome(runs=0, wicket=True),

    # TOP_SPIN (Extra bounce and rapid trajectory)
    (DeliveryType.TOP_SPIN, BatsmanIntent.DEFEND_0): Outcome(runs=0),
    (DeliveryType.TOP_SPIN, BatsmanIntent.PUSH_1): Outcome(runs=1),
    (DeliveryType.TOP_SPIN, BatsmanIntent.PUSH_2): Outcome(runs=2),
    (DeliveryType.TOP_SPIN, BatsmanIntent.PUSH_3): Outcome(runs=3),
    (DeliveryType.TOP_SPIN, BatsmanIntent.HIT_4): Outcome(runs=4),
    (DeliveryType.TOP_SPIN, BatsmanIntent.SLOG_6): Outcome(runs=0, wicket=True),
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
    """Return the outcome for a delivery and batsman intent pair, optionally consuming inventory."""
    d = DeliveryType(delivery) if not isinstance(delivery, DeliveryType) else delivery
    s = BatsmanIntent(shot) if not isinstance(shot, BatsmanIntent) else shot

    if bowler_inventory is not None:
        consume_delivery(bowler_inventory, d)
    elif room is not None and hasattr(room, "bowler_inventory") and room.bowler_inventory:
        consume_delivery(room.bowler_inventory, d)

    base = MATCHUP_RULES[(d, s)]
    status = None
    if room is not None:
        status = check_innings_state(room)
    return Outcome(
        runs=base.runs,
        wicket=base.wicket,
        wide=base.wide,
        status=status,
    )
