"""Validated message schemas shared by the HTTP and WebSocket API."""

from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field


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


# Type aliases for backward compatibility
Delivery = DeliveryType
Shot = BatsmanIntent


class ClientMessage(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    room_code: str | None = Field(default=None, min_length=4, max_length=8)
    payload: dict = Field(default_factory=dict)


class ProfilePayload(BaseModel):
    profile: BowlerProfile


class MovePayload(BaseModel):
    move: str = Field(min_length=1, max_length=30)


class GameState(BaseModel):
    runs: int = 0
    wickets: int = 0
    legal_balls: int = 0
    round_number: int = 0
    balls_per_innings: int = 6
    wickets_per_innings: int = 1
    innings_finished: bool = False
    current_innings: int = 1
    target_score: int | None = None
    winner: str | None = None
    current_phase: str = "WAITING_FOR_PLAYERS"
    bowler_profile: str | None = None
    bowler_inventory: dict[str, int] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "The Super Over API"
