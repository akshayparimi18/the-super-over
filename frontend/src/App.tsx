import { useEffect, useRef, useState } from "react";
import "./styles.css";

type Role = "bowler" | "batsman";
type BowlerProfile = "FAST" | "SPIN";

export type DeliveryType =
  | "YORKER"
  | "BOUNCER"
  | "IN_SWINGER"
  | "OUT_SWINGER"
  | "OFF_BREAK"
  | "LEG_BREAK"
  | "GOOGLY"
  | "TOP_SPIN"
  | "HALF_VOLLEY";

export type BatsmanIntent =
  | "DEFEND_0"
  | "PUSH_1"
  | "PUSH_2"
  | "PUSH_3"
  | "HIT_4"
  | "SLOG_6";

type Scoreboard = {
  runs: number;
  wickets: number;
  legal_balls: number;
  round_number: number;
  balls_per_innings: number;
  wickets_per_innings: number;
  innings_finished: boolean;
  current_innings?: number;
  target_score?: number | null;
  winner?: string | null;
  current_phase?: string;
  bowler_profile?: string | null;
  bowler_inventory?: Record<string, number>;
};

type RoundResult = {
  round_number: number;
  delivery: string;
  shot: string;
  runs_scored: number;
  wicket: boolean;
  wide: boolean;
  bowler_inventory?: Record<string, number>;
  scoreboard: Scoreboard;
  status?: string;
};

type ServerMessage = {
  type: string;
  message?: string;
  room_code?: string;
  role?: Role;
  players_connected?: number;
  waiting_for_opponent?: boolean;
  scoreboard?: Scoreboard;
  your_move_locked?: boolean;
  round_number?: number;
  delivery?: string;
  shot?: string;
  runs_scored?: number;
  wicket?: boolean;
  wide?: boolean;
  target_score?: number | null;
  current_innings?: number;
  winner?: string | null;
  status?: string;
  current_phase?: string;
  bowler_profile?: BowlerProfile;
  bowler_inventory?: Record<string, number>;
};

const deliveryMetadata: Record<string, { label: string; emoji: string }> = {
  YORKER: { label: "Yorker", emoji: "🎯" },
  BOUNCER: { label: "Bouncer", emoji: "🔥" },
  IN_SWINGER: { label: "In-Swinger", emoji: "↩️" },
  OUT_SWINGER: { label: "Out-Swinger", emoji: "↪️" },
  OFF_BREAK: { label: "Off-Break", emoji: "🌀" },
  LEG_BREAK: { label: "Leg-Break", emoji: "💫" },
  GOOGLY: { label: "Googly", emoji: "🔮" },
  TOP_SPIN: { label: "Top-Spin", emoji: "⚡" },
  HALF_VOLLEY: { label: "Half-Volley", emoji: "💥" },
};

const batsmanIntents = [
  { move: "DEFEND_0", label: "Defend", runs: "0 Runs", emoji: "🛡️" },
  { move: "PUSH_1", label: "Push 1", runs: "1 Run", emoji: "⚡" },
  { move: "PUSH_2", label: "Push 2", runs: "2 Runs", emoji: "🏃" },
  { move: "PUSH_3", label: "Push 3", runs: "3 Runs", emoji: "💨" },
  { move: "HIT_4", label: "Hit 4", runs: "4 Runs", emoji: "🏏" },
  { move: "SLOG_6", label: "Slog 6", runs: "6 Runs", emoji: "🚀" },
];

const initialScore: Scoreboard = {
  runs: 0,
  wickets: 0,
  legal_balls: 0,
  round_number: 0,
  balls_per_innings: 6,
  wickets_per_innings: 1,
  innings_finished: false,
  current_innings: 1,
  target_score: null,
  winner: null,
  current_phase: "WAITING_FOR_PLAYERS",
  bowler_profile: null,
  bowler_inventory: {},
};

export default function App() {
  const socketRef = useRef<WebSocket | null>(null);

  const [roomCodeInput, setRoomCodeInput] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [role, setRole] = useState<Role | null>(null);
  const [playersConnected, setPlayersConnected] = useState(0);
  const [score, setScore] = useState<Scoreboard>(initialScore);
  const [connected, setConnected] = useState(false);
  const [moveLocked, setMoveLocked] = useState(false);
  const [result, setResult] = useState<RoundResult | null>(null);
  const [isInningsBreak, setIsInningsBreak] = useState(false);
  const [breakCountdown, setBreakCountdown] = useState(5);
  const [currentPhase, setCurrentPhase] = useState("WAITING_FOR_PLAYERS");
  const [bowlerProfile, setBowlerProfile] = useState<string | null>(null);
  const [bowlerInventory, setBowlerInventory] = useState<Record<string, number>>({});
  const [status, setStatus] = useState("Create a room or join with a code.");
  const [error, setError] = useState("");

  useEffect(() => {
    return () => {
      socketRef.current?.close();
    };
  }, []);

  useEffect(() => {
    if (!isInningsBreak) return;
    if (breakCountdown <= 0) {
      setIsInningsBreak(false);
      setStatus("Second Innings! Bowler, choose your profile.");
      return;
    }
    const timer = setTimeout(() => {
      setBreakCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearTimeout(timer);
  }, [isInningsBreak, breakCountdown]);

  function send(data: object) {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError("Not connected to the game server.");
      return;
    }
    socket.send(JSON.stringify(data));
  }

  function connectAndSend(message: object) {
    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.OPEN ||
        socketRef.current.readyState === WebSocket.CONNECTING)
    ) {
      setError("A connection is already active.");
      return;
    }

    setError("");
    setStatus("Connecting to the game server...");

    const socket = new WebSocket("ws://127.0.0.1:8000/ws");
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      socket.send(JSON.stringify(message));
    };

    socket.onmessage = (event: MessageEvent<string>) => {
      let data: ServerMessage;
      try {
        data = JSON.parse(event.data) as ServerMessage;
      } catch {
        setError("Received an invalid server message.");
        return;
      }

      switch (data.type) {
        case "room_created":
        case "room_joined": {
          setRoomCode(data.room_code ?? "");
          setRole(data.role ?? null);
          setPlayersConnected(data.players_connected ?? 1);
          setScore(data.scoreboard ?? initialScore);
          if (data.current_phase) setCurrentPhase(data.current_phase);
          if (data.scoreboard?.bowler_profile) setBowlerProfile(data.scoreboard.bowler_profile);
          if (data.scoreboard?.bowler_inventory) setBowlerInventory(data.scoreboard.bowler_inventory);

          setStatus(
            data.type === "room_created"
              ? "Room created. Share the code with your opponent."
              : "You joined the room successfully."
          );
          break;
        }

        case "player_joined": {
          setPlayersConnected(data.players_connected ?? 2);
          if (data.current_phase) setCurrentPhase(data.current_phase);
          if (data.scoreboard) setScore(data.scoreboard);
          setStatus(
            role === "bowler"
              ? "Opponent connected! Select your bowling profile."
              : "Both players connected. Waiting for bowler to pick profile."
          );
          break;
        }

        case "phase_change": {
          if (data.current_phase) setCurrentPhase(data.current_phase);
          if (data.scoreboard) setScore(data.scoreboard);
          if (data.message) setStatus(data.message);
          break;
        }

        case "profile_selected": {
          if (data.bowler_profile) setBowlerProfile(data.bowler_profile);
          if (data.bowler_inventory) setBowlerInventory(data.bowler_inventory);
          if (data.current_phase) setCurrentPhase(data.current_phase);
          if (data.scoreboard) setScore(data.scoreboard);
          setStatus(
            `Bowler selected ${data.bowler_profile} profile! Choose your move.`
          );
          break;
        }

        case "move_locked": {
          setMoveLocked(true);
          setStatus(
            data.waiting_for_opponent
              ? "Your move is locked. Waiting for opponent..."
              : "Move locked. Resolving showdown..."
          );
          break;
        }

        case "round_result": {
          if (
            !data.delivery ||
            !data.shot ||
            !data.scoreboard ||
            data.runs_scored === undefined
          ) {
            setError("The server returned an incomplete round result.");
            break;
          }

          if (data.bowler_inventory) setBowlerInventory(data.bowler_inventory);

          setResult({
            round_number: data.round_number ?? 0,
            delivery: data.delivery,
            shot: data.shot,
            runs_scored: data.runs_scored,
            wicket: data.wicket ?? false,
            wide: data.wide ?? false,
            bowler_inventory: data.bowler_inventory,
            scoreboard: data.scoreboard,
            status: data.status,
          });

          setScore(data.scoreboard);
          setMoveLocked(false);
          const winnerText = data.scoreboard.winner;
          setStatus(
            winnerText
              ? winnerText === "Tie"
                ? "Match Over! It's a Tie!"
                : `Match Over! ${winnerText} wins!`
              : data.scoreboard.innings_finished && data.scoreboard.current_innings === 1
                ? "Innings 1 complete!"
                : data.scoreboard.innings_finished
                  ? "Innings finished!"
                  : "Round complete. Choose your next move."
          );
          break;
        }

        case "innings_break": {
          if (data.role) setRole(data.role);
          if (data.scoreboard) setScore(data.scoreboard);
          setCurrentPhase("SELECT_PROFILE");
          setBowlerProfile(null);
          setBowlerInventory({});
          setMoveLocked(false);
          setResult(null);
          setIsInningsBreak(true);
          setBreakCountdown(5);
          setStatus(
            `Innings 1 Over! Target: ${
              data.target_score ?? data.scoreboard?.target_score ?? "N/A"
            } runs.`
          );
          break;
        }

        case "match_over": {
          if (data.scoreboard) setScore(data.scoreboard);
          setCurrentPhase("MATCH_OVER");
          setMoveLocked(false);
          const winnerText = data.winner ?? data.scoreboard?.winner;
          setStatus(
            winnerText === "Tie"
              ? "Match Over! It's a Tie!"
              : `Match Over! ${winnerText ?? "Game concluded"} wins!`
          );
          break;
        }

        case "state": {
          setRoomCode(data.room_code ?? "");
          setRole(data.role ?? null);
          setPlayersConnected(data.players_connected ?? 1);
          setScore(data.scoreboard ?? initialScore);
          setMoveLocked(data.your_move_locked ?? false);
          if (data.current_phase) setCurrentPhase(data.current_phase);
          if (data.bowler_profile) setBowlerProfile(data.bowler_profile);
          if (data.bowler_inventory) setBowlerInventory(data.bowler_inventory);
          break;
        }

        case "error": {
          setError(data.message ?? "Something went wrong.");
          break;
        }

        case "room_closed": {
          setStatus(data.message ?? "The room has closed.");
          setPlayersConnected(0);
          setRoomCode("");
          setRole(null);
          setMoveLocked(false);
          setIsInningsBreak(false);
          setCurrentPhase("WAITING_FOR_PLAYERS");
          setBowlerProfile(null);
          setBowlerInventory({});
          socket.close();
          break;
        }

        default:
          break;
      }
    };

    socket.onerror = () => {
      setError("WebSocket connection failed. Is FastAPI running?");
    };

    socket.onclose = () => {
      setConnected(false);
      setStatus((current) =>
        current === "Room closed." ? current : "Disconnected from the server."
      );
    };
  }

  function createRoom() {
    setRoomCode("");
    setRole(null);
    setScore(initialScore);
    setResult(null);
    setMoveLocked(false);
    setIsInningsBreak(false);
    setBreakCountdown(5);
    setCurrentPhase("WAITING_FOR_PLAYERS");
    setBowlerProfile(null);
    setBowlerInventory({});
    connectAndSend({ type: "create_room" });
  }

  function joinRoom() {
    const code = roomCodeInput.trim().toUpperCase();
    if (!/^[A-Z0-9]{6}$/.test(code)) {
      setError("Enter a valid six-character room code.");
      return;
    }

    setRoomCode("");
    setRole(null);
    setScore(initialScore);
    setResult(null);
    setMoveLocked(false);
    setIsInningsBreak(false);
    setBreakCountdown(5);
    setCurrentPhase("WAITING_FOR_PLAYERS");
    setBowlerProfile(null);
    setBowlerInventory({});
    connectAndSend({ type: "join_room", room_code: code });
  }

  function selectProfile(profile: BowlerProfile) {
    if (role !== "bowler") return;
    setError("");
    send({ type: "select_profile", payload: { profile } });
  }

  function submitMove(move: string) {
    if (!role || moveLocked || isInningsBreak || score.winner) return;
    if (currentPhase === "SELECT_PROFILE") {
      setError("Bowler must select their profile first.");
      return;
    }
    if (score.current_innings === 2 && score.innings_finished) return;
    if (playersConnected !== 2) {
      setError("Wait until both players are connected.");
      return;
    }
    setError("");
    send({ type: "submit_move", payload: { move } });
  }

  function leaveRoom() {
    socketRef.current?.close();
    socketRef.current = null;
    setConnected(false);
    setRoomCode("");
    setRole(null);
    setPlayersConnected(0);
    setScore(initialScore);
    setResult(null);
    setMoveLocked(false);
    setIsInningsBreak(false);
    setBreakCountdown(5);
    setCurrentPhase("WAITING_FOR_PLAYERS");
    setBowlerProfile(null);
    setBowlerInventory({});
    setStatus("You left the room. Create or join another room.");
  }

  async function copyRoomCode() {
    try {
      await navigator.clipboard.writeText(roomCode);
      setStatus("Room code copied!");
    } catch {
      setError(`Copy this room code manually: ${roomCode}`);
    }
  }

  const canPlay =
    connected &&
    Boolean(roomCode) &&
    playersConnected === 2 &&
    currentPhase === "PLAYING" &&
    !moveLocked &&
    !isInningsBreak &&
    !score.winner &&
    !(score.current_innings === 2 && score.innings_finished);

  return (
    <main className="app-shell">
      <div className="stadium-glow" aria-hidden="true" />

      <header className="topbar">
        <div className="brand-mark">🏏 THE SUPER OVER</div>
        <div className={`connection-pill ${connected ? "online" : ""}`}>
          <span className="connection-dot" />
          {connected ? "Connected" : "Offline"}
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">INVENTORY & INTENT · TWO PLAYERS · ONE OVER</p>
        <h1>
          Every ball.
          <br />
          <span>Changes everything.</span>
        </h1>
        <p className="hero-copy">
          Pick your profile. Manage your inventory. Execute your intent.
        </p>
      </section>

      {!roomCode ? (
        <section className="lobby panel">
          <div>
            <p className="section-kicker">THE PAVILION</p>
            <h2>Ready to play?</h2>
            <p className="muted">No account. No downloads. Just pure cricket strategy.</p>
          </div>

          <button className="primary-button" onClick={createRoom}>
            + Create a room
          </button>

          <div className="lobby-divider">
            <span>OR JOIN YOUR FRIEND</span>
          </div>

          <label className="field-label" htmlFor="room-code">
            ROOM CODE
          </label>
          <input
            id="room-code"
            className="room-input"
            placeholder="ENTER 6-CHARACTER CODE"
            value={roomCodeInput}
            maxLength={6}
            autoCapitalize="characters"
            onChange={(event) =>
              setRoomCodeInput(
                event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "")
              )
            }
          />
          <button
            className="secondary-button"
            onClick={joinRoom}
            disabled={roomCodeInput.length !== 6}
          >
            Join with code →
          </button>
        </section>
      ) : (
        <>
          <section className="room-bar panel">
            <div>
              <p className="section-kicker">ROOM CODE</p>
              <div className="room-code">{roomCode}</div>
              <button className="text-button" onClick={copyRoomCode}>
                Copy code
              </button>
            </div>

            <div className="room-meta">
              <span className="players-count">{playersConnected}/2 PLAYERS</span>
              <span className={`role-badge ${role === "bowler" ? "role-bowler" : "role-batsman"}`}>
                {role === "bowler" ? "🎯 BOWLER" : "🏏 BATSMAN"}
              </span>
              <button className="text-button" onClick={leaveRoom}>
                Leave room
              </button>
            </div>
          </section>

          <section className="scoreboard panel">
            <div className="score-main">
              <span className="section-kicker">
                INNINGS {score.current_innings ?? 1} · {role === "bowler" ? "BOWLING" : "BATTING"}
                {bowlerProfile ? ` (${bowlerProfile})` : ""}
              </span>
              <div className="total-score">
                {score.runs}
                <span> / {score.wickets}</span>
              </div>
              <span className="muted">
                RUNS / WICKETS
                {score.target_score ? ` · TARGET: ${score.target_score}` : ""}
              </span>
            </div>

            <div className="score-stat">
              <span className="section-kicker">LEGAL BALLS</span>
              <strong>
                {score.legal_balls}
                <span> / {score.balls_per_innings}</span>
              </strong>
            </div>

            <div className="score-stat">
              <span className="section-kicker">ROUND</span>
              <strong>{score.round_number}</strong>
            </div>
          </section>

          {isInningsBreak ? (
            <section className="panel innings-break-panel">
              <p className="section-kicker">INNINGS BREAK</p>
              <h2>Innings 1 Over!</h2>
              <div className="result-highlight target-highlight">
                🎯 TARGET: {score.target_score} RUNS
              </div>
              <p className="muted innings-role-desc">
                Roles swapped! You are now the{" "}
                <span className={`role-badge inline-badge ${role === "bowler" ? "role-bowler" : "role-batsman"}`}>
                  {role === "bowler" ? "🎯 BOWLER" : "🏏 BATSMAN"}
                </span>
              </p>
              <div className="waiting-banner">
                <span className="pulse-dot" />
                Resuming in {breakCountdown}s — get ready to {role === "bowler" ? "bowl" : "bat"}!
              </div>
            </section>
          ) : score.winner ? (
            <section className="panel match-over-panel">
              <p className="section-kicker">MATCH OVER</p>
              <h2>The Super Over is complete!</h2>
              <div className="result-highlight winner-highlight">
                {score.winner === "Tie" ? "🤝 MATCH TIED!" : `🏆 ${score.winner} WINS!`}
              </div>
              <p className="muted">
                {score.winner === "Tie"
                  ? "Both teams finished level on runs!"
                  : score.winner === "Team 2"
                    ? "The target was chased down successfully!"
                    : "The target score was defended successfully!"}
              </p>
            </section>
          ) : currentPhase === "SELECT_PROFILE" && playersConnected === 2 ? (
            /* Profile Selection Screen */
            <section className="game-panel panel profile-selection-panel">
              <p className="section-kicker">PHASE I · ARSENAL SELECTION</p>
              <h2>
                {role === "bowler"
                  ? "Select Your Bowler Profile"
                  : "Waiting for Bowler..."}
              </h2>
              <p className="muted">
                {role === "bowler"
                  ? "Choose Fast or Spin. Each profile gives you a strategic delivery inventory for the over."
                  : "The bowler is choosing their delivery arsenal (Fast or Spin). Pad up!"}
              </p>

              {role === "bowler" ? (
                <div className="profile-grid">
                  <div className="profile-card">
                    <div className="profile-icon">⚡</div>
                    <h3>Fast Bowler</h3>
                    <p className="profile-desc">Pace, swing & deadly bouncers</p>
                    <ul className="profile-inventory-list">
                      <li>🎯 1 Yorker</li>
                      <li>🔥 1 Bouncer</li>
                      <li>↩️ 1 In-Swinger</li>
                      <li>↪️ 1 Out-Swinger</li>
                      <li>💥 2 Half-Volleys</li>
                    </ul>
                    <button
                      className="primary-button"
                      onClick={() => selectProfile("FAST")}
                    >
                      Select Fast Bowler ➔
                    </button>
                  </div>

                  <div className="profile-card">
                    <div className="profile-icon">🌀</div>
                    <h3>Spin Bowler</h3>
                    <p className="profile-desc">Deception, turn & variation</p>
                    <ul className="profile-inventory-list">
                      <li>🌀 1 Off-Break</li>
                      <li>💫 1 Leg-Break</li>
                      <li>🔮 1 Googly</li>
                      <li>⚡ 1 Top-Spin</li>
                      <li>💥 2 Half-Volleys</li>
                    </ul>
                    <button
                      className="primary-button"
                      onClick={() => selectProfile("SPIN")}
                    >
                      Select Spin Bowler ➔
                    </button>
                  </div>
                </div>
              ) : (
                <div className="waiting-banner">
                  <span className="pulse-dot" />
                  WAITING FOR BOWLER TO SELECT PROFILE...
                </div>
              )}
            </section>
          ) : (
            /* Active Game Play Panel (Moves Grid) */
            <section className="game-panel panel">
              <p className="section-kicker">
                {score.current_innings === 2 && score.innings_finished
                  ? "INNINGS COMPLETE"
                  : `INNINGS ${score.current_innings ?? 1} · BALL ${score.legal_balls + 1} OF 6`}
              </p>

              <h2>
                {score.current_innings === 2 && score.innings_finished
                  ? "That's the match!"
                  : role === "bowler"
                    ? `Choose your delivery (${bowlerProfile || "Arsenal"})`
                    : "Choose your batsman intent"}
              </h2>

              <p className="muted">
                {playersConnected !== 2
                  ? "Waiting for the other player to join..."
                  : moveLocked
                    ? "Your move is hidden. Waiting for the reveal..."
                    : role === "bowler"
                      ? "Manage your delivery stock wisely across the 6 balls."
                      : score.target_score
                        ? `Target: ${score.target_score} runs. Pick your intent.`
                        : "Balance your risk: Defense protects wickets, Slog aims for maximums."}
              </p>

              {!(score.current_innings === 2 && score.innings_finished) && (
                <div className="move-grid">
                  {role === "bowler"
                    ? Object.entries(bowlerInventory).map(([moveKey, count]) => {
                        const meta = deliveryMetadata[moveKey] || {
                          label: moveKey,
                          emoji: "🏏",
                        };
                        const isExhausted = count <= 0;
                        return (
                          <button
                            className={`move-card ${isExhausted ? "exhausted" : ""}`}
                            key={moveKey}
                            disabled={!canPlay || isExhausted}
                            onClick={() => submitMove(moveKey)}
                          >
                            <span className="move-emoji">{meta.emoji}</span>
                            <span className="move-label">{meta.label}</span>
                            <span
                              className={`move-inventory-badge ${
                                isExhausted ? "empty" : ""
                              }`}
                            >
                              {count} left
                            </span>
                          </button>
                        );
                      })
                    : batsmanIntents.map((intent) => (
                        <button
                          className="move-card intent-card"
                          key={intent.move}
                          disabled={!canPlay}
                          onClick={() => submitMove(intent.move)}
                        >
                          <span className="move-emoji">{intent.emoji}</span>
                          <span className="move-label">{intent.label}</span>
                          <span className="move-action">{intent.runs}</span>
                        </button>
                      ))}
                </div>
              )}

              {moveLocked && !(score.current_innings === 2 && score.innings_finished) && (
                <div className="waiting-banner">
                  <span className="pulse-dot" />
                  MOVE LOCKED — WAITING FOR OPPONENT
                </div>
              )}
            </section>
          )}

          {result && (
            <section className={`result-panel panel ${result.wicket ? "wicket-panel" : ""}`}>
              <p className="section-kicker">
                ROUND {result.round_number} · RESULT
              </p>
              <div className="matchup">
                <div className="matchup-move">
                  <span>{deliveryMetadata[result.delivery]?.emoji || "🎯"}</span>
                  <strong>{deliveryMetadata[result.delivery]?.label || result.delivery}</strong>
                  <small>DELIVERY</small>
                </div>
                <span className="versus">VS</span>
                <div className="matchup-move">
                  <span>
                    {batsmanIntents.find((i) => i.move === result.shot)?.emoji || "🏏"}
                  </span>
                  <strong>
                    {batsmanIntents.find((i) => i.move === result.shot)?.label || result.shot}
                  </strong>
                  <small>INTENT</small>
                </div>
              </div>

              <div className={`result-highlight ${result.wicket ? "wicket" : ""}`}>
                {result.wicket
                  ? "WICKET!"
                  : result.wide
                    ? "WIDE — +1 RUN"
                    : result.runs_scored === 0
                      ? "DOT BALL (0 RUNS)"
                      : `${result.runs_scored} RUN${result.runs_scored === 1 ? "" : "S"}`}
              </div>

              <p className="muted">
                {result.wide
                  ? "Wide delivery adds 1 run."
                  : result.wicket
                    ? "A wicket has fallen!"
                    : `${result.runs_scored} run${result.runs_scored === 1 ? "" : "s"} added to the scoreboard.`}
              </p>
            </section>
          )}
        </>
      )}

      <div className="status-area" role="status" aria-live="polite">
        {error && <p className="error-message">{error}</p>}
        <p>{status}</p>
      </div>

      <footer className="footer">
        <span>THE SUPER OVER</span>
        <span>INVENTORY & INTENT · REAL-TIME CRICKET SHOWDOWN</span>
      </footer>
    </main>
  );
}
