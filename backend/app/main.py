import asyncio
import secrets
import string
from dataclasses import dataclass, field
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from app.rules import Delivery, Shot, check_innings_state, resolve_matchup
from app.schemas import ClientMessage, GameState, MovePayload

app = FastAPI(title="The Super Over API")

ROOM_CODE_LENGTH = 6
LEGAL_BALLS_PER_INNINGS = 6
WICKETS_PER_INNINGS = 1
ALPHABET = string.ascii_uppercase + string.digits
BOWLER_MOVES = {delivery.value for delivery in Delivery}
BATSMAN_MOVES = {shot.value for shot in Shot}


@dataclass
class Player:
    player_id: str
    role: str
    websocket: WebSocket


@dataclass
class Room:
    code: str
    players: dict[str, Player] = field(default_factory=dict)
    moves: dict[str, str] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = False
    runs: int = 0
    wickets: int = 0
    legal_balls: int = 0
    round_number: int = 0
    current_innings: int = 1
    target_score: int | None = None
    winner: str | None = None


rooms: dict[str, Room] = {}
rooms_lock = asyncio.Lock()


def make_room_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(ROOM_CODE_LENGTH))


async def create_unique_room() -> Room:
    async with rooms_lock:
        while True:
            code = make_room_code()
            if code not in rooms:
                room = Room(code=code)
                rooms[code] = room
                return room


def public_score(room: Room) -> dict:
    """Only publish state that is safe for both players to see."""
    is_innings_finished = (
        room.legal_balls >= LEGAL_BALLS_PER_INNINGS
        or room.wickets >= WICKETS_PER_INNINGS
        or room.winner is not None
        or (
            room.current_innings == 2
            and room.target_score is not None
            and room.runs >= room.target_score
        )
    )
    return {
        "runs": room.runs,
        "wickets": room.wickets,
        "legal_balls": room.legal_balls,
        "round_number": room.round_number,
        "balls_per_innings": LEGAL_BALLS_PER_INNINGS,
        "wickets_per_innings": WICKETS_PER_INNINGS,
        "innings_finished": is_innings_finished,
        "current_innings": room.current_innings,
        "target_score": room.target_score,
        "winner": room.winner,
    }


async def send_json(websocket: WebSocket, data: dict) -> None:
    await websocket.send_json(data)


async def send_error(
    websocket: WebSocket,
    code: str,
    message: str,
    **extra: object,
) -> None:
    payload = {"type": "error", "code": code, "message": message}
    payload.update(extra)
    await send_json(websocket, payload)


async def broadcast(room: Room, data: dict) -> None:
    """Send a public event to connected room members."""
    for player in list(room.players.values()):
        try:
            await send_json(player.websocket, data)
        except (RuntimeError, WebSocketDisconnect):
            # A failed send must not undo an already resolved round.
            pass


async def remove_player(room: Room, player_id: str) -> None:
    remaining: list[Player] = []
    should_delete = False

    async with room.lock:
        player = room.players.get(player_id)
        if player is None:
            return
        del room.players[player_id]
        room.moves.pop(player_id, None)

        if not room.players:
            should_delete = True
        else:
            # This MVP closes a room when either player leaves.
            remaining = list(room.players.values())
            room.players.clear()
            room.moves.clear()
            should_delete = True
        if should_delete:
            room.closed = True

    if should_delete:
        async with rooms_lock:
            if rooms.get(room.code) is room:
                rooms.pop(room.code, None)

    for remaining_player in remaining:
        try:
            await send_json(
                remaining_player.websocket,
                {
                    "type": "room_closed",
                    "message": "The other player disconnected.",
                },
            )
            await remaining_player.websocket.close()
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    player_id = secrets.token_hex(8)
    current_room_code: str | None = None

    try:
        while True:
            data = await websocket.receive_json()
            try:
                msg = ClientMessage(**data)
            except ValidationError:
                await send_error(websocket, "invalid_message", "Invalid message format.")
                continue

            if msg.type == "create_room":
                if current_room_code:
                    await send_error(websocket, "already_in_room", "Already in a room.")
                    continue

                room = await create_unique_room()
                current_room_code = room.code
                player = Player(
                    player_id=player_id, role="bowler", websocket=websocket
                )
                async with room.lock:
                    room.players[player_id] = player

                await send_json(
                    websocket,
                    {
                        "type": "room_created",
                        "room_code": room.code,
                        "role": "bowler",
                        "players_connected": 1,
                        "scoreboard": public_score(room),
                    },
                )

            elif msg.type == "join_room":
                if current_room_code:
                    await send_error(websocket, "already_in_room", "Already in a room.")
                    continue

                code = (msg.room_code or "").upper()
                async with rooms_lock:
                    room = rooms.get(code)

                if not room:
                    await send_error(
                        websocket,
                        "room_not_found",
                        "Room not found.",
                        room_code=code,
                    )
                    continue

                async with room.lock:
                    if room.closed:
                        await send_error(
                            websocket,
                            "room_not_found",
                            "Room not found.",
                            room_code=code,
                        )
                        continue

                    if len(room.players) >= 2:
                        await send_error(websocket, "room_full", "Room is full.")
                        continue

                    player = Player(
                        player_id=player_id, role="batsman", websocket=websocket
                    )
                    room.players[player_id] = player
                    current_room_code = room.code
                    players_connected = len(room.players)

                await send_json(
                    websocket,
                    {
                        "type": "room_joined",
                        "room_code": room.code,
                        "role": "batsman",
                        "players_connected": players_connected,
                        "scoreboard": public_score(room),
                    },
                )

                # Notify only the existing player (Fix B)
                for existing_player in list(room.players.values()):
                    if existing_player.player_id == player_id:
                        continue
                    try:
                        await send_json(
                            existing_player.websocket,
                            {
                                "type": "player_joined",
                                "players_connected": players_connected,
                            },
                        )
                    except (RuntimeError, WebSocketDisconnect):
                        pass

            elif msg.type == "submit_move":
                if not current_room_code:
                    continue

                async with rooms_lock:
                    room = rooms.get(current_room_code)
                if not room:
                    continue

                try:
                    payload = MovePayload(**msg.payload)
                except ValidationError:
                    await send_error(websocket, "invalid_move", "Invalid move.")
                    continue

                result_data = None
                innings_status = None
                async with room.lock:
                    player = room.players.get(player_id)
                    if not player or len(room.players) != 2:
                        continue

                    if room.winner is not None:
                        await send_error(websocket, "match_over", "Match is finished.")
                        continue

                    if public_score(room)["innings_finished"] and (
                        room.current_innings == 2 or room.target_score is not None
                    ):
                        await send_error(websocket, "innings_finished", "Innings finished.")
                        continue

                    if player.role == "bowler" and payload.move not in BOWLER_MOVES:
                        await send_error(
                            websocket,
                            "invalid_move",
                            "Invalid move for bowler",
                        )
                        continue
                    if player.role == "batsman" and payload.move not in BATSMAN_MOVES:
                        await send_error(
                            websocket,
                            "invalid_move",
                            "Invalid move for batsman",
                        )
                        continue

                    if player_id in room.moves:
                        await send_error(
                            websocket,
                            "move_already_submitted",
                            "Move already submitted.",
                        )
                        continue

                    room.moves[player_id] = payload.move

                    await send_json(
                        websocket,
                        {
                            "type": "move_locked",
                            "waiting_for_opponent": len(room.moves) < 2,
                        },
                    )

                    if len(room.moves) == 2:
                        bowler_id = next(
                            pid
                            for pid, p in room.players.items()
                            if p.role == "bowler"
                        )
                        batsman_id = next(
                            pid
                            for pid, p in room.players.items()
                            if p.role == "batsman"
                        )

                        delivery = room.moves[bowler_id]
                        shot = room.moves[batsman_id]
                        room.moves.clear()

                        try:
                            outcome = resolve_matchup(Delivery(delivery), Shot(shot))
                        except ValueError:
                            outcome = resolve_matchup(Delivery.YORKER, Shot.DUCK)

                        room.round_number += 1
                        room.runs += outcome.runs
                        if outcome.wicket:
                            room.wickets += 1
                        if not outcome.wide:
                            room.legal_balls += 1

                        result_data = {
                            "type": "round_result",
                            "round_number": room.round_number,
                            "delivery": delivery,
                            "shot": shot,
                            "runs_scored": outcome.runs,
                            "wicket": outcome.wicket,
                            "wide": outcome.wide,
                            "scoreboard": public_score(room),
                        }

                        innings_status = check_innings_state(room)
                        if innings_status:
                            result_data["status"] = innings_status
                            if innings_status == "MATCH_OVER":
                                result_data["scoreboard"]["winner"] = room.winner

                if result_data:
                    await broadcast(room, result_data)

                if innings_status == "INNINGS_BREAK":
                    async with room.lock:
                        room.moves.clear()
                    for p in list(room.players.values()):
                        try:
                            await send_json(
                                p.websocket,
                                {
                                    "type": "innings_break",
                                    "target_score": room.target_score,
                                    "current_innings": room.current_innings,
                                    "role": p.role,
                                    "scoreboard": public_score(room),
                                },
                            )
                        except (RuntimeError, WebSocketDisconnect):
                            pass
                elif innings_status == "MATCH_OVER":
                    async with room.lock:
                        room.moves.clear()
                    await broadcast(
                        room,
                        {
                            "type": "match_over",
                            "winner": room.winner,
                            "scoreboard": public_score(room),
                        },
                    )

            else:
                await send_error(
                    websocket,
                    "unknown_action",
                    f"Unknown action: {msg.type}",
                )

    except WebSocketDisconnect:
        pass
    finally:
        if current_room_code:
            async with rooms_lock:
                room = rooms.get(current_room_code)
            if room:
                await remove_player(room, player_id)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "app": "The Super Over API"}
