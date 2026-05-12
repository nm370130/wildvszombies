"""
Wild vs Zombies — Local Mock RGS Server
========================================
Simulates the Stake Engine RGS API locally so the frontend can be tested
against real math output without publishing to any cloud server.

Endpoints implemented (matches CarrotRGS spec):
  POST /wallet/authenticate  — returns balance + config + last round
  POST /wallet/balance       — returns current balance
  POST /wallet/play          — picks a spin from LUT, returns round + events
  POST /wallet/end-round     — credits winnings, returns updated balance
  OPTIONS *                  — CORS pre-flight

Usage:
  python mock_rgs.py
  python mock_rgs.py --port 8080
  python mock_rgs.py --books /path/to/library --port 3000

Then in your frontend, pass:
  rgs_url=http://localhost:8080

Default port: 8080
Default books dir: ~/go/src/math-sdk/games/wild_vs_zombies/library
"""

import json
import os
import random
import time
import uuid
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer


# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_LIBRARY = os.path.expanduser(
    "~/go/src/math-sdk/games/wild_vs_zombies/library"
)
DEFAULT_PORT    = 8080
STARTING_BALANCE = 100_000_000   # $100 in stake-engine units (1 unit = 1e-6)
CURRENCY        = "USD"

# Bet mode cost multipliers (must match game_config.py)
BET_MODE_COSTS = {
    "base":        1.25,
    "bonus_hunt":  6.25,
    "bonus":       100.0,
    "super_bonus": 250.0,
}


# ── Data loader ───────────────────────────────────────────────────────────────

class GameData:
    """Loads LUT + books from the math-sdk library on startup."""

    def __init__(self, library_path: str):
        self.library_path  = library_path
        self.lut           = {}    # mode → list of (weight, book_id)
        self.books         = {}    # mode → {book_id → entry}
        self.total_weights = {}    # mode → sum of weights

        self._load_all()

    def _load_lut(self, mode: str):
        """Load lookUpTable_<mode>_0.csv → list of (cumulative_weight, id)"""
        path = os.path.join(
            self.library_path, "publish_files", f"lookUpTable_{mode}_0.csv"
        )
        if not os.path.exists(path):
            print(f"  [WARN] LUT not found for mode '{mode}': {path}")
            return

        entries = []
        total   = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                book_id = int(parts[0])
                weight  = int(parts[1])
                total  += weight
                entries.append((total, book_id))   # cumulative weight

        self.lut[mode]           = entries
        self.total_weights[mode] = total
        print(f"  Loaded LUT [{mode}]: {len(entries)} entries, total weight={total:,}")

    def _load_books(self, mode: str):
        """Load books_<mode>.json → dict of id → entry"""
        # Try uncompressed json first (local dev), then jsonl
        for fname in [f"books_{mode}.json", f"books_{mode}.jsonl"]:
            path = os.path.join(self.library_path, "books", fname)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    if fname.endswith(".json"):
                        data = json.load(f)
                    else:
                        data = [json.loads(line) for line in f if line.strip()]
                self.books[mode] = {entry["id"]: entry for entry in data}
                print(f"  Loaded books [{mode}]: {len(self.books[mode])} entries")
                return

        # Try zstd compressed
        try:
            import zstandard as zst
            path = os.path.join(
                self.library_path, "publish_files", f"books_{mode}.jsonl.zst"
            )
            if os.path.exists(path):
                with open(path, "rb") as f:
                    decompressor = zst.ZstdDecompressor()
                    with decompressor.stream_reader(f) as reader:
                        content = reader.read().decode("utf-8")
                data = [json.loads(line) for line in content.splitlines() if line.strip()]
                self.books[mode] = {entry["id"]: entry for entry in data}
                print(f"  Loaded books [{mode}] (zst): {len(self.books[mode])} entries")
                return
        except ImportError:
            pass

        print(f"  [WARN] Books not found for mode '{mode}'")

    def _load_all(self):
        print("Loading game data...")
        for mode in BET_MODE_COSTS:
            self._load_lut(mode)
            self._load_books(mode)
        print("Game data ready.\n")

    def pick_round(self, mode: str) -> dict | None:
        """Weighted-random selection from LUT, returns full book entry."""
        if mode not in self.lut or not self.lut[mode]:
            return None

        entries     = self.lut[mode]
        total       = self.total_weights[mode]
        target      = random.randint(1, total)

        # Binary search on cumulative weights
        lo, hi = 0, len(entries) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if entries[mid][0] < target:
                lo = mid + 1
            else:
                hi = mid
        _, book_id = entries[lo]

        return self.books.get(mode, {}).get(book_id)


# ── Session store ─────────────────────────────────────────────────────────────

class SessionStore:
    """Simple in-memory session/balance/round store."""

    def __init__(self, starting_balance: int):
        self.sessions: dict[str, dict] = {}
        self.starting_balance = starting_balance

    def create(self) -> str:
        sid = str(uuid.uuid4())
        self.sessions[sid] = {
            "balance":    self.starting_balance,
            "round":      None,
            "active_bet": 0,
            "mode":       "base",
        }
        return sid

    def get(self, sid: str) -> dict | None:
        return self.sessions.get(sid)

    def ensure(self, sid: str) -> dict:
        """Return session, auto-creating if unknown (dev convenience)."""
        if sid not in self.sessions:
            self.sessions[sid] = {
                "balance":    self.starting_balance,
                "round":      None,
                "active_bet": 0,
                "mode":       "base",
            }
        return self.sessions[sid]


# ── Request handler ───────────────────────────────────────────────────────────

game_data: GameData = None
store:     SessionStore = None


def _make_balance_obj(amount: int) -> dict:
    return {"amount": amount, "currency": CURRENCY}


def _make_config() -> dict:
    return {
        "minBet":          100_000,
        "maxBet":        1_000_000_000,
        "stepBet":         100_000,
        "defaultBetLevel": 1_000_000,
        "betLevels": [
            100_000, 200_000, 500_000, 1_000_000, 2_000_000,
            5_000_000, 10_000_000, 20_000_000, 50_000_000, 100_000_000,
        ],
        "jurisdiction": {
            "socialCasino":       False,
            "disabledFullscreen": False,
            "disabledTurbo":      False,
        },
    }


def _round_response(entry: dict, mode: str, bet_amount: int) -> dict:
    """Wrap a book entry as the 'round' object the frontend expects."""
    cost       = BET_MODE_COSTS.get(mode, 1.0)
    payout_mult = entry.get("payoutMultiplier", 0) / 100   # LUT stores payout*100
    win_amount  = int(bet_amount * payout_mult / cost)

    return {
        "id":               str(entry.get("id", 0)),
        "mode":             mode,
        "betAmount":        bet_amount,
        "payoutMultiplier": entry.get("payoutMultiplier", 0),
        "winAmount":        win_amount,
        "baseGameWins":     entry.get("baseGameWins", 0),
        "freeGameWins":     entry.get("freeGameWins", 0),
        "criteria":         entry.get("criteria", ""),
        "events":           entry.get("events", []),
        "complete":         True,
    }


class RGSHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {self.path}  {fmt % args}")

    def _send(self, status: int, body: dict):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        body = self._read_body()
        path = self.path.split("?")[0].rstrip("/")

        if path == "/wallet/authenticate":
            self._handle_authenticate(body)
        elif path == "/wallet/balance":
            self._handle_balance(body)
        elif path == "/wallet/play":
            self._handle_play(body)
        elif path == "/wallet/end-round":
            self._handle_end_round(body)
        elif path == "/bet/event":
            self._handle_bet_event(body)
        else:
            self._send(404, {"error": f"Unknown path: {path}"})

    # ── Endpoints ──────────────────────────────────────────────────────────────

    def _handle_authenticate(self, body: dict):
        sid = body.get("sessionID", str(uuid.uuid4()))
        session = store.ensure(sid)
        self._send(200, {
            "balance": _make_balance_obj(session["balance"]),
            "config":  _make_config(),
            "round":   session.get("round"),
        })

    def _handle_balance(self, body: dict):
        sid     = body.get("sessionID", "")
        session = store.ensure(sid)
        self._send(200, {"balance": _make_balance_obj(session["balance"])})

    def _handle_play(self, body: dict):
        sid        = body.get("sessionID", "")
        amount     = int(body.get("amount", 1_000_000))      # in 1e-6 units
        mode       = body.get("mode", "base").lower()
        session    = store.ensure(sid)

        # Deduct bet cost
        cost_mult  = BET_MODE_COSTS.get(mode, 1.0)
        bet_debit  = int(amount * cost_mult)

        if session["balance"] < bet_debit:
            self._send(400, {"error": "ERR_IPB", "message": "Insufficient balance"})
            return

        session["balance"]    -= bet_debit
        session["active_bet"]  = bet_debit
        session["mode"]        = mode

        # Pick a random round from math books
        entry = game_data.pick_round(mode)
        if entry is None:
            # Fallback: zero-win round with empty events if books not loaded
            entry = {"id": 0, "payoutMultiplier": 0, "events": [], "criteria": "0"}

        round_obj = _round_response(entry, mode, amount)
        session["round"] = round_obj

        self._send(200, {
            "balance": _make_balance_obj(session["balance"]),
            "round":   round_obj,
        })

    def _handle_end_round(self, body: dict):
        sid     = body.get("sessionID", "")
        session = store.ensure(sid)

        # Credit winnings
        rnd = session.get("round")
        if rnd:
            session["balance"] += rnd.get("winAmount", 0)
            session["round"]    = None

        self._send(200, {"balance": _make_balance_obj(session["balance"])})

    def _handle_bet_event(self, body: dict):
        # Acknowledge in-progress events (no-op for mock)
        self._send(200, {"event": body.get("event", "")})


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Wild vs Zombies Mock RGS")
    parser.add_argument("--port",  type=int, default=DEFAULT_PORT)
    parser.add_argument("--books", type=str, default=DEFAULT_LIBRARY,
                        help="Path to math-sdk library directory")
    args = parser.parse_args()

    global game_data, store
    game_data = GameData(args.books)
    store     = SessionStore(STARTING_BALANCE)

    print(f"Mock RGS running on  http://localhost:{args.port}")
    print(f"Books directory:     {args.books}")
    print(f"Starting balance:    ${STARTING_BALANCE / 1_000_000:.2f}")
    print()
    print("Frontend URL params:")
    print(f"  rgs_url=http://localhost:{args.port}")
    print(f"  sessionID=test-session-001")
    print()
    print("Press Ctrl-C to stop.\n")

    server = HTTPServer(("", args.port), RGSHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
