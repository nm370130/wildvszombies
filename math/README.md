# Wild vs Zombies — Math Module

Python simulation backend for the Wild vs Zombies slot game, built on the
Stake Engine Math SDK.

---

## What this module does

The Math SDK runs locally to generate static output files that get uploaded
to Stake Engine once. The RGS then serves all player sessions without any
custom server.

| Output | Description |
|---|---|
| **Books** (`.jsonl.zst`) | Pre-computed simulation results. Each entry is a JSON object `{id, payoutMultiplier, events[]}` describing one complete spin outcome. |
| **Lookup tables** (`.csv`) | `simulation_id, weight, payout_multiplier` rows. The RGS reads these at runtime to randomly select an outcome for each player bet. |

---

## Prerequisites

The Math SDK must be cloned and its venv set up **once**:

```bash
git clone <math-sdk-repo-url> ~/go/src/math-sdk
cd ~/go/src/math-sdk
python3.13 -m venv .venv          # must be Python 3.12+; use python3.13 explicitly
.venv/bin/pip install -r requirements.txt
```

> If you already have `~/go/src/math-sdk` with a `.venv` inside it, you're done — no further setup needed.

---

## Running simulations

Always use the helper script from the `math/` directory:

```bash
cd /path/to/wildvszombies/math
bash run.sh          # smoke test  (10 K sims per mode, ~30 s)
```

`run.sh` sets `PYTHONPATH` to the SDK automatically. Do not run `python run.py` directly.

### Production run

Edit `run.py` and change `num_sim_args`:

```python
num_sim_args = {
    "base":  int(1_000_000),   # 1 M base-game sims
    "bonus": int(500_000),     # 500 K bonus-buy sims
}
```

Then `bash run.sh` again. This will:
1. Generate books and lookup tables (10 threads).
2. Run the Rust paytable optimiser to converge on 96% RTP.
3. Produce a PAR stat sheet (hit rate, volatility, RTP split).
4. Run Stake Engine format compliance checks.

Output goes to `math/library/`.

---

## Project structure

```
math/
├── game_config.py       # All static parameters: paytable, symbols, bet modes, reel strips
├── game_override.py     # SDK hook overrides (reset_book, assign_special_sym_function)
├── game_events.py       # Custom event emitters
├── game_executables.py  # Game mechanics: shovel, golden shovel, expanding wilds, nudge
├── game_calculations.py # Ways-pay evaluation with global multiplier
├── game_optimization.py # Stub for the Rust optimiser setup class
├── gamestate.py         # run_spin() and run_freespin() — top-level game loop
├── run.py               # Entry point: generate books, optimise, analyse
├── run.sh               # Helper script (sets PYTHONPATH, calls run.py)
└── reels/
    ├── BR0.csv          # Base-game reel strip
    ├── FR0.csv          # Standard bonus strip  (3 SC → 10 spins)
    ├── FR_SUPER.csv     # Super bonus strip     (4 SC → 12 spins)
    ├── FR_HIDDEN.csv    # Hidden bonus strip    (5 SC → 15 spins, ≥1500× guaranteed)
    └── FRWCAP.csv       # Win-cap scenario strip
```

---

## Game parameters

| Parameter | Value |
|---|---|
| RTP | 96% |
| Win cap | 20,000× bet |
| Board | 5×5 fixed (5 reels × 5 rows) |
| Win type | Ways-pay (min 3 adjacent reels) |
| Base bet cost | 1.25× |
| Bonus buy cost | 100× |

### Symbols

| ID | Name | Role |
|---|---|---|
| H1 | Cherry Bomb | High pay |
| H2 | Chomper | High pay |
| H3 | Wall-nut | High pay |
| H4 | Peashooter | High pay |
| H5 | Sunflower | High pay |
| A K Q J 10 | Low pays | Low pay |
| W | Lawnmower Wild | Substitutes all; doubles global mult per wild in bonus; expands to full reel in bonus |
| SC | Gravestone Scatter | 3/4/5 → Bonus / Super Bonus / Hidden Bonus |
| SH | Shovel | Places 1–5 wilds randomly; each wild doubles global mult in bonus |
| GSH | Golden Shovel | Places 1–5 multiplier wilds (2–5×); each doubles global mult × own value in bonus |

### Bonus tiers

| Scatters | Tier | Spins | Reel strip | Notes |
|---|---|---|---|---|
| 3 | Bonus | 10 | FR0 | — |
| 4 | Super Bonus | 12 | FR_SUPER | Pre-bonus 3–4 wild activations |
| 5 | Hidden Bonus | 15 | FR_HIDDEN | Pre-bonus 5–6 activations; guaranteed ≥1500×; cannot be purchased |

Retrigger: 3 SC during any bonus spin → +5 spins (once per session).

Nudge: when exactly 2 SC visible in base game, 15% chance the zombie hand pushes a SC into view.

---

## Class hierarchy (MRO)

```
GameState
└── GameStateOverride       (game_override.py)   SDK hook overrides
    └── GameExecutables     (game_executables.py) shovel, expanding wilds, nudge, retrigger
        └── GameCalculations (game_calculations.py) Ways evaluation + global multiplier
            └── Executables                        SDK core
```

---

## Tuning RTP

After a production run the optimiser adjusts simulation weights automatically.
If manual tuning is needed:

- **Increase RTP**: raise paytable pay values, or increase W/GSH density on bonus strips.
- **Decrease RTP**: lower paytable pay values, or reduce SC density on BR0 (fewer bonus entries).
- **Win-cap frequency**: adjust `quota` on the `wincap` distribution in `game_config.py`.

Re-run `bash run.sh` after any changes.
