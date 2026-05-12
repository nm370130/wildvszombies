"""
Wild vs Zombies — Game Executables (v3)
=========================================
Mechanic rules (from client GDD v3):

  BASE GAME:
    - W  : simple wild — substitutes only, no expansion, no multiplier
    - No VS, SH, or GSH in base game

  BONUS GAME:
    - W  : simple wild — substitutes only (no longer doubles global mult)
    - VS : bonus-only. Expands to cover full reel. Triggers Duel Sequence.
           Per-reel multiplier = cumulative sum of Peashooter shot values.
           Multiple VS reels in same win: multipliers summed.
    - SH : places 1-3 simple wilds at random positions, transforms to paying sym
    - GSH: places 1-2 VS symbols at random positions, those expand + duel,
           GSH transforms to paying sym

  DUEL SEQUENCE (per VS reel):
    - First shot guaranteed: value from {2,3,5,8,10}
    - Each subsequent shot: duel_continue_prob chance to fire, else zombie wins
    - Shots accumulate additively. Max 5 shots.
    - Hidden Bonus: minimum shot value raised to 3

  WAVE BAR (across entire bonus session):
    - Points = Peashooter shots that hit
    - Stage 2 (5 pts) : +1 DuelSpin  (1 guaranteed VS expansion)
    - Stage 3 (12 pts): +1 DuelSpin  (2 guaranteed VS expansions) + GSH guarantee
    - Stage 4 (20 pts): +1 MegaDuelSpin (3 guaranteed VS, boosted odds) + +3 spins

  RETRIGGER: 3 SC in bonus → +5 spins (once per session)
  NUDGE    : 2 SC in base → 15% chance zombie hand pushes symbol into view
  PRE-BONUS: Super/Hidden bonus — place mix of W and VS before first spin
"""

import random

from game_calculations import GameCalculations
from game_events import (
    shovel_wilds_event,
    golden_shovel_vs_event,
    vs_expand_event,
    duel_sequence_event,
    wave_bar_update_event,
    wave_bar_stage_event,
    duel_spin_event,
    nudge_event,
    pre_bonus_sequence_event,
    bonus_tier_entry_event,
    retrigger_event,
)
from src.calculations.statistics import get_random_outcome


class GameExecutables(GameCalculations):
    """Wild vs Zombies mechanics layer."""

    # ── Duel Sequence ─────────────────────────────────────────────────────────

    def run_duel_sequence(self, reel: int, boosted: bool = False) -> int:
        """
        Run one Duel Sequence on a reel. Returns the cumulative multiplier.
        Also increments wave_bar_points by the number of shots that hit.
        Emits vs_expand_event + duel_sequence_event.

        boosted: True during Stage 4 MegaDuelSpin (higher continue prob).
        """
        vs_expand_event(self, reel)

        # Determine shot pool (Hidden Bonus raises minimum)
        if self.bonus_tier == "hidden_bonus":
            shot_pool = [v for v in self.config.duel_shot_values
                         if v >= self.config.duel_hidden_min_shot_value]
        else:
            shot_pool = self.config.duel_shot_values

        # Determine continue probability
        if boosted:
            prob = self.config.duel_continue_prob["stage4"]
        else:
            prob = self.config.duel_continue_prob.get(
                self.bonus_tier,
                self.config.duel_continue_prob["bonus"],
            )

        shots = []
        # First shot is guaranteed
        shots.append(random.choice(shot_pool))

        # Subsequent shots depend on continue probability
        while (
            len(shots) < self.config.duel_max_shots
            and random.random() < prob
        ):
            shots.append(random.choice(shot_pool))

        final_mult = sum(shots)
        duel_sequence_event(self, reel, shots, final_mult)

        # Accumulate Wave Bar points (1 point per shot)
        self._add_wave_bar_points(len(shots))

        return final_mult

    # ── Wave Bar ──────────────────────────────────────────────────────────────

    def _add_wave_bar_points(self, points: int) -> None:
        """Add points to the Wave Bar and check for stage transitions."""
        if points <= 0:
            return

        prev_stage = self.wave_bar_stage
        self.wave_bar_points += points

        wave_bar_update_event(self, points, self.wave_bar_points, self.wave_bar_stage)

        # Check each stage threshold in ascending order
        for stage, threshold in sorted(self.config.wave_bar_thresholds.items()):
            if prev_stage < stage <= self._points_to_stage(self.wave_bar_points):
                self._trigger_wave_bar_stage(stage)

    def _points_to_stage(self, points: int) -> int:
        """Return the Wave Bar stage for a given point total."""
        stage = 1
        for s, threshold in sorted(self.config.wave_bar_thresholds.items()):
            if points >= threshold:
                stage = s
        return stage

    def _trigger_wave_bar_stage(self, stage: int) -> None:
        """Handle reaching a new Wave Bar stage. Sets pending_duel_spin."""
        self.wave_bar_stage = stage

        if stage == 2:
            spin_type = "duel_spin"
            self.pending_duel_spin = "duel_spin"
        elif stage == 3:
            spin_type = "duel_spin"
            self.pending_duel_spin = "duel_spin"
            # Guarantee a GSH within next 3 spins
            self.gs_guarantee_countdown = 3
        elif stage == 4:
            spin_type = "mega_duel_spin"
            self.pending_duel_spin = "mega_duel_spin"
            # +3 extra spins
            self.tot_fs += self.config.wave_bar_stage4_extra_spins

        wave_bar_stage_event(self, stage, spin_type)

    # ── VS symbol handling ────────────────────────────────────────────────────

    def expand_and_duel_vs(self, reel: int, boosted: bool = False) -> int:
        """
        Expand all rows on reel to VS (acts as wild), run duel sequence.
        Returns the per-reel multiplier. Stores in vs_reel_multipliers.
        """
        for row in range(len(self.board[reel])):
            self.board[reel][row] = self.create_symbol("VS")

        mult = self.run_duel_sequence(reel, boosted=boosted)
        self.vs_reel_multipliers[reel] = mult
        return mult

    def process_vs_symbols_on_board(self, boosted: bool = False) -> None:
        """
        Find all VS symbols currently on the board (reels 1-3, 0-indexed).
        Expand and duel each one.
        Called after Shovels and Golden Shovels are processed.
        """
        # Collect VS positions before expansion mutates the board
        vs_reels_seen = set()
        for reel in range(self.config.num_reels):
            for row in range(len(self.board[reel])):
                if (
                    self.board[reel][row].name == "VS"
                    and reel not in vs_reels_seen
                    and reel not in self.vs_reel_multipliers   # don't re-duel
                ):
                    vs_reels_seen.add(reel)

        for reel in sorted(vs_reels_seen):
            self.expand_and_duel_vs(reel, boosted=boosted)

        if vs_reels_seen:
            self.get_special_symbols_on_board()

    # ── Shovel ────────────────────────────────────────────────────────────────

    def apply_shovel(self, reel: int, row: int) -> None:
        """
        Place 1-3 simple W wilds at random non-SC/SH/GSH positions.
        W is now a plain substitute — no multiplier effect in any game mode.
        After placing, transform the SH position to a random paying symbol.
        """
        num_wilds = get_random_outcome(self.config.shovel_wild_count_weights)
        positions = self._placeable_positions(exclude=(reel, row))
        chosen    = random.sample(positions, min(num_wilds, len(positions)))

        placed = []
        for pos in chosen:
            r, ro = pos["reel"], pos["row"]
            self.board[r][ro] = self.create_symbol("W")
            placed.append({"reel": r, "row": ro})

        shovel_wilds_event(self, placed, reel, row)
        self.board[reel][row] = self.create_symbol(self._random_pay_symbol())
        self.get_special_symbols_on_board()

    # ── Golden Shovel ─────────────────────────────────────────────────────────

    def apply_golden_shovel(self, reel: int, row: int) -> None:
        """
        Place 1-2 VS symbols at random positions (bonus only).
        Each VS will expand and trigger its own Duel Sequence immediately.
        After placing, transform the GSH position to a random paying symbol.
        """
        num_vs = get_random_outcome(self.config.golden_shovel_vs_count_weights)
        positions = self._placeable_positions(exclude=(reel, row))
        chosen    = random.sample(positions, min(num_vs, len(positions)))

        placed = []
        for pos in chosen:
            r, ro = pos["reel"], pos["row"]
            self.board[r][ro] = self.create_symbol("VS")
            placed.append({"reel": r, "row": ro})

        golden_shovel_vs_event(self, placed, reel, row)

        # Immediately expand and duel each placed VS
        for pos in placed:
            r = pos["reel"]
            if r not in self.vs_reel_multipliers:
                self.expand_and_duel_vs(r)

        self.board[reel][row] = self.create_symbol(self._random_pay_symbol())
        self.get_special_symbols_on_board()

    # ── Nudge (base game only) ────────────────────────────────────────────────

    def apply_nudge(self) -> None:
        """
        When exactly 2 SC are visible, with nudge_probability attempt to push
        a SC (or W) from just above the visible window into view.
        """
        if self.count_special_symbols("scatter") != 2:
            return
        if random.random() >= self.config.nudge_probability:
            return
        if not self.config.include_padding or self.top_symbols is None:
            return

        scatter_reels = {p["reel"] for p in self.special_syms_on_board["scatter"]}
        candidates = [
            (reel, self.top_symbols[reel].name)
            for reel in range(self.config.num_reels)
            if reel not in scatter_reels
            and self.top_symbols[reel].name in ("SC", "W")
        ]

        if not candidates:
            other_reels = [r for r in range(self.config.num_reels) if r not in scatter_reels]
            if other_reels:
                nudge_event(self, random.choice(other_reels), "", success=False)
            return

        reel, sym_name = random.choice(candidates)
        height = len(self.board[reel])
        for row in range(height - 1, 0, -1):
            self.board[reel][row] = self.board[reel][row - 1]
        self.board[reel][0] = self.top_symbols[reel]

        reel_strip = self.config.reels[self.reelstrip_id][reel]
        reel_len   = len(reel_strip)
        self.reel_positions[reel] = (self.reel_positions[reel] - 1) % reel_len
        new_top_pos = (self.reel_positions[reel] - 1) % reel_len
        self.top_symbols[reel] = self.create_symbol(reel_strip[new_top_pos])

        self.get_special_symbols_on_board()
        nudge_event(self, reel, sym_name, success=True)

    # ── Retrigger ─────────────────────────────────────────────────────────────

    def check_and_award_retrigger(self) -> None:
        """3+ SC in bonus spin → +5 spins. Fires once per bonus session."""
        if (
            not self.retriggered_bonus
            and self.count_special_symbols("scatter")
            >= self.config.retrigger_scatter_threshold
        ):
            self.retriggered_bonus = True
            self.tot_fs += self.config.retrigger_spins
            retrigger_event(self, self.config.retrigger_spins)

    # ── GSH guarantee (Stage 3 Wave Bar mechanic) ─────────────────────────────

    def check_gs_guarantee(self) -> None:
        """
        If gs_guarantee_countdown is active, decrement it.
        When it hits 0, force a GSH placement on the current board.
        Called at the START of each bonus spin.
        """
        if self.gs_guarantee_countdown <= 0:
            return
        self.gs_guarantee_countdown -= 1
        if self.gs_guarantee_countdown == 0:
            # Force-place a GSH on the board at a safe position
            positions = self._placeable_positions()
            if positions:
                pos = random.choice(positions)
                self.board[pos["reel"]][pos["row"]] = self.create_symbol("GSH")
                self.get_special_symbols_on_board()

    # ── Pre-bonus activation ───────────────────────────────────────────────────

    def calc_pre_bonus_placement(self) -> list:
        """
        Pre-bonus sweep: place a mix of W and VS symbols before the first spin.
        Only runs for super_bonus and hidden_bonus.
        VS placements trigger immediate duel sequences.
        Points from those duels feed into the Wave Bar.
        Returns list of {reel, row, symbol} activations.
        """
        if self.bonus_tier not in self.config.pre_bonus_activation_weights:
            return []

        count_weights = self.config.pre_bonus_activation_weights[self.bonus_tier]
        n = get_random_outcome(count_weights)
        vs_prob = self.config.pre_bonus_vs_prob[self.bonus_tier]

        positions = self._placeable_positions()
        chosen    = random.sample(positions, min(n, len(positions)))

        activations = []
        for pos in chosen:
            sym = "VS" if random.random() < vs_prob else "W"
            self.board[pos["reel"]][pos["row"]] = self.create_symbol(sym)
            activations.append({"reel": pos["reel"], "row": pos["row"], "symbol": sym})

        self.get_special_symbols_on_board()

        # Run duel sequences for any VS placed during sweep
        for act in activations:
            if act["symbol"] == "VS":
                r = act["reel"]
                if r not in self.vs_reel_multipliers:
                    self.expand_and_duel_vs(r)

        return activations

    # ── Bonus entry ───────────────────────────────────────────────────────────

    def setup_bonus_entry(self, scatter_count: int) -> None:
        """
        Determine tier, set strip, set tot_fs, set Wave Bar starting stage,
        run pre-bonus activation (Super/Hidden), emit bonusTierEntry.
        """
        self.bonus_tier = self.config.bonus_tier_scatter_map.get(scatter_count, "bonus")

        strip_map = {
            "bonus":        "FR0",
            "super_bonus":  "FR_SUPER",
            "hidden_bonus": "FR_HIDDEN",
        }
        self.freegame_strip = strip_map.get(self.bonus_tier, "FR0")
        self.tot_fs = self.config.bonus_tier_spins[self.bonus_tier]

        # Set starting Wave Bar stage
        self.wave_bar_stage = self.config.bonus_tier_start_stage.get(self.bonus_tier, 1)

        # For Super Bonus (Stage 2 start): award initial DuelSpin immediately
        # For Hidden Bonus (Stage 3 start): award initial DuelSpin + set GSH guarantee
        if self.wave_bar_stage == 2:
            self.pending_duel_spin = "duel_spin"
        elif self.wave_bar_stage >= 3:
            self.pending_duel_spin = "duel_spin"
            self.gs_guarantee_countdown = 3

        # Pre-bonus activation sweep (Super/Hidden only)
        activations = self.calc_pre_bonus_placement()
        if activations:
            pre_bonus_sequence_event(self, activations)

        bonus_tier_entry_event(self, self.tot_fs)

    # ── Board special processing ──────────────────────────────────────────────

    def process_base_board_specials(self) -> None:
        """
        BASE GAME: no VS, SH, or GSH — nothing to process.
        W is a simple wild handled by the ways calculator.
        """
        pass

    def process_bonus_board_specials(self, boosted: bool = False) -> None:
        """
        BONUS GAME:
        1. Process GSH → places VS symbols that immediately expand + duel.
        2. Process SH  → places simple W wilds.
        3. Process any remaining VS on the board → expand + duel.

        boosted: True during Stage 4 MegaDuelSpin (higher duel continue prob).
        """
        # Reset VS reel multipliers for this spin
        self.vs_reel_multipliers = {}

        # Check GSH guarantee (Stage 3 mechanic)
        self.check_gs_guarantee()

        gsh = [dict(p) for p in self.special_syms_on_board.get("golden_shovel", [])]
        sh  = [dict(p) for p in self.special_syms_on_board.get("shovel", [])]

        for pos in gsh:
            self.apply_golden_shovel(pos["reel"], pos["row"])
        for pos in sh:
            self.apply_shovel(pos["reel"], pos["row"])

        # Process any VS drawn from the reel strip (not placed by GSH above)
        self.process_vs_symbols_on_board(boosted=boosted)

    # ── DuelSpin / MegaDuelSpin ───────────────────────────────────────────────

    def setup_duel_spin(self, spin_type: str) -> None:
        """
        Prepare the board for a DuelSpin or MegaDuelSpin.
        Guarantees 1, 2, or 3 VS symbols land as part of wins by placing
        them on eligible reel positions before win evaluation.

        spin_type: "duel_spin" | "mega_duel_spin"
        """
        guaranteed = {
            "duel_spin":      2 if self.wave_bar_stage == 3 else 1,
            "mega_duel_spin": 3,
        }.get(spin_type, 1)

        duel_spin_event(self, spin_type, guaranteed)

        # Place guaranteed VS on reels 1, 2, 3 (0-indexed) — the VS-eligible reels
        vs_reels = [1, 2, 3]
        chosen_reels = random.sample(vs_reels, min(guaranteed, len(vs_reels)))

        boosted = (spin_type == "mega_duel_spin")

        for reel in chosen_reels:
            # Place VS at row 2 (middle) — guaranteed to be part of ways wins
            self.board[reel][2] = self.create_symbol("VS")

        self.get_special_symbols_on_board()
        # VS expansion and duel happens in process_bonus_board_specials
        return boosted

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _placeable_positions(self, exclude: tuple = None) -> list:
        """Board positions not occupied by SC/SH/GSH (safe to overwrite with W or VS)."""
        blocked = {"SC", "SH", "GSH"}
        return [
            {"reel": r, "row": ro}
            for r in range(self.config.num_reels)
            for ro in range(len(self.board[r]))
            if self.board[r][ro].name not in blocked
            and (exclude is None or (r, ro) != exclude)
        ]

    def _random_pay_symbol(self) -> str:
        """Weighted random regular paying symbol (used when a special transforms)."""
        symbols = ["H1", "H2", "H3", "H4", "H5", "A", "K", "Q", "J", "10"]
        weights = [2,     3,     4,     5,     5,   6,   7,   7,   8,    8]
        return random.choices(symbols, weights=weights, k=1)[0]
