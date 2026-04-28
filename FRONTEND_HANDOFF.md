# Wild vs Zombies — Frontend Integration Specification

> **For:** Frontend Developer
> **From:** Math / Backend team
> **Status:** Share after smoke test passes and simulation runs clean

---

## How it works

The frontend never talks to the math code directly. The flow is:

```
Player clicks Spin
  → Frontend calls Stake Engine RGS  POST /play
  → RGS picks a pre-computed simulation from the lookup table
  → RGS returns the simulation's event list
  → Frontend reads events in index order and plays animations
```

Every simulation is a JSON object:

```json
{
  "id": 12345,
  "payoutMultiplier": 3.5,
  "events": [
    { "index": 0, "type": "reveal", ... },
    { "index": 1, "type": "winInfo", ... },
    ...
  ]
}
```

Play `events[]` in `index` order, one by one.

---

## Board layout

**Fixed 5×5 board.** 5 reels, 5 visible rows each. Does not change size.

```
Reel index:   0        1        2        3        4
             left                               right

Row index:    0   ←── top of visible window
              1
              2
              3
              4   ←── bottom of visible window
```

**Padding:** `include_padding = true`. The RGS adds one hidden row above and one below.
All `row` values in events are **already offset by +1** to account for this.

| Row value in events | Meaning |
|---|---|
| 0 | Top padding row (hidden) |
| 1–5 | Visible rows |
| 6 | Bottom padding row (hidden) |

---

## Symbols

| ID | Display name | Type |
|---|---|---|
| `H1` | Cherry Bomb | High pay |
| `H2` | Chomper | High pay |
| `H3` | Wall-nut | High pay |
| `H4` | Peashooter | High pay |
| `H5` | Sunflower | High pay |
| `A` | Ace | Low pay |
| `K` | King | Low pay |
| `Q` | Queen | Low pay |
| `J` | Jack | Low pay |
| `10` | Ten | Low pay |
| `W` | Lawnmower Wild | Substitutes all pays. In bonus: doubles global multiplier, expands to fill full reel. |
| `SC` | Gravestone Scatter | Triggers bonus. 3 → Bonus, 4 → Super Bonus, 5 → Hidden Bonus. |
| `SH` | Shovel | Places 1–5 wilds randomly on board, then transforms into a regular pay symbol. |
| `GSH` | Golden Shovel | Places 1–5 multiplier wilds (2–5× each) randomly, then transforms. |

---

## Win amounts — display convention

**All `amount` / `win` fields in events are integers = actual value × 100.**

| Event field | Example raw value | Divide by 100 | Meaning |
|---|---|---|---|
| `winInfo.wins[].win` | `5000` | `50.0` | 50× bet for that symbol line |
| `winInfo.totalWin` | `5000` | `50.0` | Total win this spin |
| `setWin.amount` | `5000` | `50.0` | Cumulative spin win |
| `setTotalWin.amount` | `5000` | `50.0` | Running total (base + bonus) |
| `freeSpinEnd.amount` | `185000` | `1850.0` | Total bonus session win |
| `finalWin.amount` | `185000` | `1850.0` | Round total (capped at 20,000×) |

Multiply by the player's bet amount to get the currency display value.

---

## Event reference

### `reveal` *(SDK)*
Fired at the start of every spin (base and bonus).

```json
{
  "index": 0,
  "type": "reveal",
  "gameType": "basegame",
  "board": [
    [{"name":"10"}, {"name":"H4"}, {"name":"K"}, {"name":"10"}, {"name":"J"}, {"name":"Q"}],
    ...
  ],
  "paddingPositions": [12, 34, 5, 22, 8],
  "anticipation": [0, 0, 1, 2, 3]
}
```

- `board[reel]` — array of symbols top to bottom (row 0 = top padding, rows 1–5 = visible, row 6 = bottom padding).
- `board[reel][row].name` — symbol ID string.
- `board[reel][row].scatter = true` appears on SC symbols.
- `board[reel][row].wild = true` appears on W symbols.
- `anticipation[reel]` > 0 — show scatter build-up animation on that reel (only fires in base game when 2 SC already visible).
- `gameType` = `"basegame"` or `"freegame"`.

---

### `shovelWilds` *(custom)*
Fired when a `SH` symbol activates — places wilds on the board.

```json
{
  "index": 2,
  "type": "shovelWilds",
  "shovelReel": 1,
  "shovelRow": 3,
  "wildPositions": [
    {"reel": 0, "row": 2},
    {"reel": 3, "row": 4},
    {"reel": 4, "row": 1}
  ]
}
```

- Animate the shovel digging at `(shovelReel, shovelRow)`.
- Place wild symbols at each position in `wildPositions`.
- In bonus, each placed wild also triggers a `globalMultUpdate` (fired separately).
- After all wilds are placed, the SH transforms to a regular symbol (no `symbolTransform` event — the next `reveal` shows the updated board).

---

### `goldenShovelWilds` *(custom)*
Fired when a `GSH` symbol activates — places multiplier wilds.

```json
{
  "index": 3,
  "type": "goldenShovelWilds",
  "shovelReel": 2,
  "shovelRow": 1,
  "wildPositions": [
    {"reel": 0, "row": 2, "mult": 3},
    {"reel": 3, "row": 4, "mult": 2}
  ]
}
```

- Same as `shovelWilds`, but each wild has a `mult` value (2–5).
- Display the `mult` badge on each placed wild symbol.
- In bonus, each wild triggers a `globalMultUpdate`.

---

### `wildExpand` *(custom)*
Fired in the bonus when a reel containing at least one `W` expands to fill all 5 rows.

```json
{
  "index": 5,
  "type": "wildExpand",
  "reel": 2,
  "height": 5,
  "expanded": true
}
```

- `expanded: true` — animate the wild revving up and expanding to fill the full reel (all 5 rows become W).
- `expanded: false` — reserved for future stall animation; not emitted in current build.
- Fired once per reel per bonus spin. Multiple reels can expand in one spin.

---

### `globalMultUpdate` *(custom)*
Fired each time the global multiplier changes. Only fires in bonus.

```json
{
  "index": 6,
  "type": "globalMultUpdate",
  "prevMult": 4,
  "globalMult": 8,
  "reason": "wild"
}
```

- Update the multiplier banner to show `globalMult`.
- `reason` values:
  - `"wild"` — a W from the reel strip doubled the multiplier (×2).
  - `"shovel"` — a wild placed by SH doubled the multiplier (×2).
  - `"golden_shovel"` — a wild placed by GSH (×2 × its own mult value).
- `prevMult` → `globalMult` shows the transition (use for number roll animation).
- The global multiplier **accumulates across all bonus spins** — it never resets within a session.

---

### `zombieNudge` *(custom)*
Fired in the base game when the zombie hand animation plays.

```json
{
  "index": 1,
  "type": "zombieNudge",
  "reel": 3,
  "nudgedSymbol": "SC",
  "success": true
}
```

- `success: true` — the zombie hand pushed a SC (or W) from just above the visible window into row 1. The board has already been updated — play the nudge animation then show the new board state.
- `success: false` — the zombie hand appeared but found nothing useful. Play the tease animation only; board is unchanged.
- Only fires when exactly 2 SC are visible in that base-game spin (15% probability).

---

### `preBonusSequence` *(custom)*
Fired once before the first bonus spin in Super Bonus and Hidden Bonus.

```json
{
  "index": 10,
  "type": "preBonusSequence",
  "bonusTier": "super_bonus",
  "wildPositions": [
    {"reel": 1, "row": 2},
    {"reel": 3, "row": 4},
    {"reel": 0, "row": 3}
  ]
}
```

- Play the pre-bonus cinematic: wilds activate one by one at each position in `wildPositions`.
- `bonusTier` = `"super_bonus"` or `"hidden_bonus"` — use for theme colour / intro screen.
- Not fired for standard Bonus (3 SC).

---

### `bonusTierEntry` *(custom)*
Fired once on bonus entry, after `preBonusSequence` (if applicable).

```json
{
  "index": 11,
  "type": "bonusTierEntry",
  "bonusTier": "bonus",
  "spinsAwarded": 10,
  "reelStrip": "FR0"
}
```

- Show the tier splash screen.
- `bonusTier`: `"bonus"` | `"super_bonus"` | `"hidden_bonus"`.
- `spinsAwarded`: initial spin count (10 / 12 / 15).
- `reelStrip`: informational only, frontend does not need to use it.

---

### `freeSpinTrigger` *(SDK)*
Fired in the base game when 3+ scatters land.

```json
{
  "index": 9,
  "type": "freeSpinTrigger",
  "totalFs": 10,
  "positions": [
    {"reel": 0, "row": 2},
    {"reel": 2, "row": 3},
    {"reel": 4, "row": 1}
  ]
}
```

- Flash scatter positions, then transition to bonus intro.

---

### `updateFreeSpin` *(SDK)*
Fired before each bonus spin.

```json
{
  "index": 12,
  "type": "updateFreeSpin",
  "amount": 1,
  "total": 10
}
```

- `amount` = current spin number (1-based).
- `total` = total spins in session (increases if retrigger fires).

---

### `retrigger` *(custom)*
Fired when 3+ SC land during a bonus spin. Awards +5 extra spins. Fires at most once per session.

```json
{
  "index": 20,
  "type": "retrigger",
  "spinsAdded": 5,
  "totalFs": 15
}
```

- Play retrigger celebration.
- Update spin counter to `totalFs`.

---

### `winInfo` *(SDK)*
Fired when the board has wins.

```json
{
  "index": 25,
  "type": "winInfo",
  "totalWin": 50000,
  "wins": [
    {
      "symbol": "H1",
      "kind": 5,
      "win": 50000,
      "positions": [
        {"reel": 0, "row": 2},
        {"reel": 1, "row": 3},
        {"reel": 2, "row": 1},
        {"reel": 3, "row": 2},
        {"reel": 4, "row": 3}
      ],
      "meta": {
        "ways": 1,
        "globalMult": 4,
        "winWithoutMult": 12500
      }
    }
  ]
}
```

- Highlight all `positions` for each win entry.
- `kind` = number of reels spanned.
- `win` = final win (already multiplied by `globalMult`) × 100.
- `meta.winWithoutMult` = base win before multiplier × 100 (use for "WIN × 4" display).
- `meta.globalMult` = the multiplier that was applied.

---

### `setWin` *(SDK)*
```json
{ "type": "setWin", "amount": 50000, "winLevel": 2 }
```
Update the win ticker. `winLevel` 0 = normal, higher = bigger celebration (Big Win / Mega Win).

---

### `setTotalWin` *(SDK)*
```json
{ "type": "setTotalWin", "amount": 50000 }
```
Running total win for the round (base + bonus combined so far).

---

### `wincap` *(SDK)*
```json
{ "type": "wincap", "amount": 2000000 }
```
Fired when the 20,000× win cap is hit. Show the win-cap celebration. `amount` = 20000 × 100.

---

### `freeSpinEnd` *(SDK)*
```json
{ "type": "freeSpinEnd", "amount": 185000, "winLevel": 3 }
```
End of the bonus session. Show total bonus win summary screen.

---

### `finalWin` *(SDK)*
```json
{ "type": "finalWin", "amount": 185000 }
```
Last event in every simulation. `amount` = total round win × 100, capped at 20,000× (= 2,000,000 raw).

---

## Typical event sequences

### Base game — no win
```
reveal → setTotalWin → finalWin
```

### Base game — win, no bonus
```
reveal → winInfo → setWin → setTotalWin → finalWin
```

### Base game — GSH activates (base, no bonus)
```
reveal → goldenShovelWilds → winInfo → setWin → setTotalWin → finalWin
```

### Base game — zombie nudge fires
```
reveal → zombieNudge → [win events] → finalWin
```

### Base game — 3 SC trigger standard bonus
```
reveal → freeSpinTrigger → bonusTierEntry
  → [for each bonus spin:]
      updateFreeSpin → reveal
      → [if SH on board:] shovelWilds → globalMultUpdate (×N)
      → [if GSH on board:] goldenShovelWilds → globalMultUpdate (×N)
      → [per reel with W:] wildExpand → globalMultUpdate (strip W count)
      → [if retrigger:] retrigger
      → winInfo → setWin → setTotalWin
freeSpinEnd → setTotalWin → finalWin
```

### 4 SC trigger super bonus (has pre-bonus)
```
reveal → freeSpinTrigger
→ preBonusSequence → globalMultUpdate (×N for pre-placed wilds)
→ bonusTierEntry
→ [bonus spins as above]
→ freeSpinEnd → setTotalWin → finalWin
```

---

## Bonus tier summary

| SC count | Tier | Spins | Strip | Pre-bonus wilds |
|---|---|---|---|---|
| 3 | `bonus` | 10 | FR0 | None |
| 4 | `super_bonus` | 12 | FR_SUPER | 3–4 wilds |
| 5 | `hidden_bonus` | 15 | FR_HIDDEN | 5–6 wilds |

Retrigger: +5 spins, once per session.
Global multiplier: accumulates across all spins in a session. Starts at 1× on entry.

---

## Buy-bonus mode

Player pays 100× bet. Always enters standard **Bonus** (10 spins, FR0 strip). No pre-bonus sequence. Event sequence starts directly at `bonusTierEntry`.

---

## Open questions to confirm before integration

1. **Asset names** — confirm art asset filenames match symbol IDs: `H1`, `H2`, `H3`, `H4`, `H5`, `A`, `K`, `Q`, `J`, `10`, `W`, `SC`, `SH`, `GSH`.
2. **Win level thresholds** — `setWin.winLevel` and `freeSpinEnd.winLevel` use SDK defaults. Share your Big Win / Mega Win breakpoints and we will configure them.
3. **Multiplier badge on W** — for GSH-placed wilds, the `mult` value (2–5) appears in `goldenShovelWilds.wildPositions[].mult`. Confirm how to display this badge (number overlay, separate sprite, etc.).
4. **Nudge after reveal** — `zombieNudge` fires after the `reveal` for that spin. The `reveal` shows the initial board (2 SC visible). On `zombieNudge` with `success: true`, play the nudge animation and update row 1 of the indicated reel to the nudged symbol.
5. **Multiplier display** — the `globalMult` banner should be persistent across all bonus spins (it never resets mid-session). Confirm the UI has a persistent multiplier display in the bonus.
