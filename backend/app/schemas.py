"""Validated message schemas shared by the HTTP and WebSocket API."""

from typing import Literal

from pydantic import BaseModel, Field

Delivery = Literal["YORKER", "BOUNCER", "SPIN"]
Shot = Literal["HELICOPTER", "SWEEP", "DUCK"]


class ClientMessage(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    room_code: str | None = Field(default=None, min_length=4, max_length=8)
    payload: dict = Field(default_factory=dict)


class MovePayload(BaseModel):
    move: Delivery | Shot


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


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "The Super Over API"
