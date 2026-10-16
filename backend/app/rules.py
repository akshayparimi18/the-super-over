"""Authoritative cricket matchup rules for The Super Over."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Delivery(StrEnum):
    YORKER = "YORKER"
    BOUNCER = "BOUNCER"
    SPIN = "SPIN"


class Shot(StrEnum):
    HELICOPTER = "HELICOPTER"
    SWEEP = "SWEEP"
    DUCK = "DUCK"


@dataclass(frozen=True)
class Outcome:
    runs: int
    wicket: bool = False
    wide: bool = False
    status: str | None = None


# Exact matchup table approved for the MVP.
MATCHUP_RULES: dict[tuple[Delivery, Shot], Outcome] = {
    (Delivery.YORKER, Shot.HELICOPTER): Outcome(runs=6),
    (Delivery.YORKER, Shot.SWEEP): Outcome(runs=1),
    (Delivery.YORKER, Shot.DUCK): Outcome(runs=0, wicket=True),
    (Delivery.BOUNCER, Shot.DUCK): Outcome(runs=1, wide=True),
    (Delivery.BOUNCER, Shot.SWEEP): Outcome(runs=2),
    (Delivery.BOUNCER, Shot.HELICOPTER): Outcome(runs=0, wicket=True),
    (Delivery.SPIN, Shot.SWEEP): Outcome(runs=4),
    (Delivery.SPIN, Shot.DUCK): Outcome(runs=0),
    (Delivery.SPIN, Shot.HELICOPTER): Outcome(runs=0, wicket=True),
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
            # swap the host/guest roles
            for player in room.players.values():
                player.role = "batsman" if player.role == "bowler" else "bowler"
            return "INNINGS_BREAK"
    elif room.current_innings == 2:
        if room.target_score is not None and room.runs >= room.target_score:
            room.winner = "Team 2"
            return "MATCH_OVER"
        elif (
            room.wickets >= DEFAULT_WICKETS_TO_END_INNINGS
            or room.legal_balls >= LEGAL_BALLS_PER_INNINGS
        ):
            if room.target_score is not None and room.runs == room.target_score - 1:
                room.winner = "Tie"
            else:
                room.winner = "Team 1"
            return "MATCH_OVER"
    return None


def resolve_matchup(delivery: Delivery, shot: Shot, room: Any = None) -> Outcome:
    """Return the outcome for a validated delivery/shot pair and check innings state if room is provided."""
    base = MATCHUP_RULES[(delivery, shot)]
    status = None
    if room is not None:
        status = check_innings_state(room)
    return Outcome(
        runs=base.runs,
        wicket=base.wicket,
        wide=base.wide,
        status=status,
    )
