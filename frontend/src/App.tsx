import { useEffect, useRef, useState } from "react";
import "./styles.css";

type Role = "bowler" | "batsman";
type Delivery = "YORKER" | "BOUNCER" | "SPIN";
type Shot = "HELICOPTER" | "SWEEP" | "DUCK";

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
};

type RoundResult = {
  round_number: number;
  delivery: Delivery;
  shot: Shot;
  runs_scored: number;
  wicket: boolean;
  wide: boolean;
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
  delivery?: Delivery;
  shot?: Shot;
  runs_scored?: number;
  wicket?: boolean;
  wide?: boolean;
  target_score?: number | null;
  current_innings?: number;
  winner?: string | null;
  status?: string;
};

const deliveries: { move: Delivery; label: string; emoji: string }[] = [
  { move: "YORKER", label: "Yorker", emoji: "🎯" },
  { move: "BOUNCER", label: "Bouncer", emoji: "🔥" },
  { move: "SPIN", label: "Spin", emoji: "🌀" },
];

const shots: { move: Shot; label: string; emoji: string }[] = [
  { move: "HELICOPTER", label: "Helicopter", emoji: "🚁" },
  { move: "SWEEP", label: "Sweep", emoji: "🏏" },
  { move: "DUCK", label: "Duck", emoji: "🦆" },
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
      setStatus("Second Innings! Choose your move.");
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
          setStatus(
            data.type === "room_created"
              ? "Room created. Share the code with your opponent."
              : "You joined the room successfully."
          );
          break;
        }

        case "player_joined": {
          setPlayersConnected(data.players_connected ?? 2);
          setStatus("Both players are connected. Get ready!");
          break;
        }

        case "move_locked": {
          setMoveLocked(true);
          setStatus(
            data.waiting_for_opponent
              ? "Your move is locked. Waiting for your opponent..."
              : "Move locked. Waiting for the round result..."
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

          setResult({
            round_number: data.round_number ?? 0,
            delivery: data.delivery,
            shot: data.shot,
            runs_scored: data.runs_scored,
            wicket: data.wicket ?? false,
            wide: data.wide ?? false,
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
          setMoveLocked(false);
          setResult(null);
          setIsInningsBreak(true);
          setBreakCountdown(5);
          setStatus(
            `Innings 1 Over! Target to chase: ${
              data.target_score ?? data.scoreboard?.target_score ?? "N/A"
            } runs.`
          );
          break;
        }

        case "match_over": {
          if (data.scoreboard) setScore(data.scoreboard);
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
    connectAndSend({ type: "join_room", room_code: code });
  }

  function submitMove(move: Delivery | Shot) {
    if (!role || moveLocked || isInningsBreak || score.winner) return;
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
    !moveLocked &&
    !isInningsBreak &&
    !score.winner &&
    !(score.current_innings === 2 && score.innings_finished);

  const currentOptions = role === "bowler" ? deliveries : shots;

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
        <p className="eyebrow">REAL-TIME · TWO PLAYERS · ONE OVER</p>
        <h1>
          Every ball.
          <br />
          <span>Changes everything.</span>
        </h1>
        <p className="hero-copy">
          Pick your move in secret. Lock it in. Let the server decide the
          showdown.
        </p>
      </section>

      {!roomCode ? (
        <section className="lobby panel">
          <div>
            <p className="section-kicker">THE PAVILION</p>
            <h2>Ready to play?</h2>
            <p className="muted">No account. No downloads. Just cricket.</p>
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
          ) : (
            <section className="game-panel panel">
              <p className="section-kicker">
                {score.current_innings === 2 && score.innings_finished
                  ? "INNINGS COMPLETE"
                  : `INNINGS ${score.current_innings ?? 1} · NEXT BALL`}
              </p>

              <h2>
                {score.current_innings === 2 && score.innings_finished
                  ? "That's the match!"
                  : role === "bowler"
                    ? "Choose your delivery"
                    : "Choose your shot"}
              </h2>

              <p className="muted">
                {playersConnected !== 2
                  ? "Waiting for the other player to join..."
                  : score.current_innings === 2 && score.innings_finished
                    ? "The match has ended."
                    : moveLocked
                      ? "Your move is hidden. Waiting for the reveal..."
                      : score.target_score
                        ? `Target: ${score.target_score} runs. Pick your choice.`
                        : "Your opponent cannot see your choice."}
              </p>

              {!(score.current_innings === 2 && score.innings_finished) && (
                <div className="move-grid">
                  {currentOptions.map((option) => (
                    <button
                      className="move-card"
                      key={option.move}
                      disabled={!canPlay}
                      onClick={() => submitMove(option.move)}
                    >
                      <span className="move-emoji">{option.emoji}</span>
                      <span className="move-label">{option.label}</span>
                      <span className="move-action">SELECT ↗</span>
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
                  <span>🎯</span>
                  <strong>{result.delivery}</strong>
                  <small>BOWLER</small>
                </div>
                <span className="versus">VS</span>
                <div className="matchup-move">
                  <span>🏏</span>
                  <strong>{result.shot}</strong>
                  <small>BATSMAN</small>
                </div>
              </div>

              <div className={`result-highlight ${result.wicket ? "wicket" : ""}`}>
                {result.wicket
                  ? "WICKET!"
                  : result.wide
                    ? "WIDE — +1 RUN"
                    : result.runs_scored === 0
                      ? "DOT BALL"
                      : `${result.runs_scored} RUN${result.runs_scored === 1 ? "" : "S"}`}
              </div>

              <p className="muted">
                {result.wide
                  ? "The wide adds a run but does not count as a legal ball."
                  : result.wicket
                    ? "The batting side has lost a wicket."
                    : "Score updated on both screens."}
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
        <span>ONE ROOM · TWO PLAYERS · PURE CRICKET</span>
      </footer>
    </main>
  );
}
