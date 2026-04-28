# Wild vs Zombies — Stake Engine Math Deployment Guide

Two ways to run a production simulation:

- **Option A — GitHub Actions (recommended):** runs on GitHub's servers, no powerful machine needed.
- **Option B — Local machine:** run directly if you have 16 GB+ RAM.

---

## Option A — GitHub Actions (recommended)

### One-time setup

**Step 1 — Push this repo to GitHub** (if not already):

```bash
cd /path/to/wildvszombies
git init
git remote add origin https://github.com/nm370130/wildvszombies.git
git push -u origin main
```

**Step 2 — Add the math-sdk secret:**

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `MATH_SDK_REPO_URL`
4. Value: the full git clone URL of the math-sdk repo (e.g. `https://github.com/org/math-sdk.git` or SSH URL)
5. Save

### Running a production simulation

1. Go to your GitHub repo → **Actions** tab
2. Click **Production Math Run** in the left sidebar
3. Click **Run workflow** (top right)
4. Fill in the inputs:

| Input | Recommended value | Description |
|---|---|---|
| Base game simulations | `500000` | 500K fits GitHub's 7 GB runner |
| Bonus buy simulations | `250000` | 250K bonus |
| Run RTP optimizer | `true` | |

5. Click **Run workflow** (green button)

### Downloading the output

1. Wait for the run to complete (~60–90 minutes) — green tick = success
2. Click the completed run
3. Scroll to **Artifacts** at the bottom
4. Download `publish_files-<run-number>.zip`
5. Unzip it — you get the 5 files ready to upload to Stake Engine

### Cost

Free. GitHub gives 2,000 free minutes/month. Each production run uses ~90 minutes → about **22 free runs per month**.

---

## Option B — Local machine (16 GB RAM required)

---

## Prerequisites (one-time setup)

These only need to be done once on the machine you are running from.

### 1. Clone and set up the Math SDK

```bash
git clone <math-sdk-repo-url> ~/go/src/math-sdk
cd ~/go/src/math-sdk
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Install Rust (required for the RTP optimizer)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
echo 'source ~/.cargo/env' >> ~/.zshrc
```

Verify:

```bash
cargo --version   # must print a version number
```

### 3. Verify QA passes

```bash
cd /path/to/wildvszombies/math
bash run_qa.sh
# Expected: 55 PASSED | 0 FAILED
```

---

## Step 1 — Configure for production run

Open `math/run.py` and update two sections:

**Sim counts** (lines 54–57):

```python
num_sim_args = {
    "base":  1_000_000,   # 1 million base-game sims
    "bonus": 500_000,     # 500 K bonus-buy sims
}
```

**Run conditions** (lines 59–64):

```python
run_conditions = {
    "run_sims":          True,
    "run_optimization":  True,    # Rust optimizer — needs ≥ 200 K sims
    "run_analysis":      True,    # PAR stat sheet
    "run_format_checks": True,    # Stake Engine compliance checks
}
```

**Optimizer parameters** — restore production values in `math/game_optimization.py`.

For **base** mode `ConstructParameters` (around line 126):

```python
num_show=5000,
num_per_fence=10000,
sim_trials=5000,
test_spins=[50, 100, 200, 500],
test_weights=[0.25, 0.35, 0.25, 0.15],
```

For **bonus** mode `ConstructParameters` (around line 186):

```python
num_show=5000,
num_per_fence=10000,
sim_trials=5000,
test_spins=[10, 20, 50],
test_weights=[0.5, 0.3, 0.2],
```

---

## Step 2 — Run the production simulation

```bash
cd /path/to/wildvszombies/math
bash run.sh
```

Expected runtime: **60–120 minutes** (1 M sims + optimizer + analysis).

The terminal will print progress per batch and then optimizer convergence lines. A clean run ends with no Python tracebacks.

### What a successful run looks like

```
Creating books...

Creating books for wild_vs_zombies in base
Batch 1 of X  ...
Thread N finished with ... RTP.
...
Finished creating books in ... seconds.

Creating books for wild_vs_zombies in bonus
...
Finished creating books in ... seconds.

Running optimization for mode: base
Running optimization for mode: bonus

[Analysis output if run_analysis=True]
[Format check output if run_format_checks=True]
```

No errors = success.

---

## Step 3 — Verify the output files

The files that will be uploaded are at:

```
~/go/src/math-sdk/games/wild_vs_zombies/library/publish_files/
```

Check that all 5 files exist and have non-zero size:

```bash
ls -lh ~/go/src/math-sdk/games/wild_vs_zombies/library/publish_files/
```

Expected output:

```
books_base.jsonl.zst        ~200–500 MB
books_bonus.jsonl.zst       ~100–300 MB
index.json                  ~1 KB
lookUpTable_base_0.csv      ~15–30 MB
lookUpTable_bonus_0.csv     ~8–15 MB
```

Also check the verification file to confirm RTP converged:

```bash
cat ~/go/src/math-sdk/games/wild_vs_zombies/library/configs/books_base.verification.json
```

The `rtp` value should be close to **0.96** (within ±0.005).

---

## Step 4 — Upload to Stake Engine

1. Log in to the Stake Engine dashboard.
2. Navigate to **Math** → **Upload**.
3. Select the game `wild_vs_zombies`.
4. Upload all 5 files from `publish_files/`:
   - `books_base.jsonl.zst`
   - `books_bonus.jsonl.zst`
   - `index.json`
   - `lookUpTable_base_0.csv`
   - `lookUpTable_bonus_0.csv`
5. Confirm the upload. Stake Engine will validate the file formats automatically.

> The Python source code (`wildvszombies/` repo) is **never uploaded**. Only these 5 output files go to Stake Engine.

---

## Step 5 — Post-upload checklist

- [ ] All 5 files uploaded without error
- [ ] Stake Engine format validation passes (no rejection message)
- [ ] Test a spin in the Stake Engine sandbox/staging environment
- [ ] Confirm `payoutMultiplier` and `events[]` appear in the RGS response
- [ ] Share `FRONTEND_HANDOFF.md` with the frontend developer

---

## Re-deploying after a change

Any time you change game logic (paytable, reel strips, mechanics, config), repeat from **Step 1**:

```
Edit code → bash run.sh (production) → re-upload publish_files/
```

The new upload replaces the previous files. All subsequent player sessions use the new outcomes.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `cargo not found` | Run `source ~/.cargo/env` or restart terminal |
| Optimizer hangs >30 min | Sims too low for `num_per_fence`. Ensure base ≥ 1 M, bonus ≥ 500 K |
| Optimizer panic `index out of bounds` | Check `search_conditions` in `game_optimization.py` — each scatter fence needs a distinct `kind` filter |
| `verification.json` RTP far from 0.96 | Re-tune reel strips or paytable values (see `math/README.md` Tuning section), then re-run |
| Format checks fail | Review error message — usually a missing field or wrong type in the config |
| `ModuleNotFoundError` during run | Run via `bash run.sh`, not `python run.py` directly |

---

## File reference

| File | Purpose |
|---|---|
| `math/run.py` | Main entry point — edit sim counts and run conditions here |
| `math/run.sh` | Shell wrapper — always use this to run |
| `math/run_qa.sh` | QA test suite — run before every production deploy |
| `math/game_config.py` | Paytable, symbols, bet modes, reel strips |
| `math/game_optimization.py` | Optimizer targets and parameters |
| `math/reels/*.csv` | Reel strip symbol sequences |
| `FRONTEND_HANDOFF.md` | Event specification for the frontend developer |
