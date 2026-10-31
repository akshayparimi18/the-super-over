"""Validated message schemas shared by the HTTP and WebSocket API."""

from pydantic import BaseModel, Field

from .rules import BatsmanIntent, BowlerProfile, DeliveryType

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
