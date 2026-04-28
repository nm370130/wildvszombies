"""
Wild vs Zombies — Game Executables (v2)
=========================================
Key mechanic rules (from GDD):
  BASE GAME:
    - W  : substitutes only (no multiplier building)
    - SH : places 1-5 wilds (substitute only, no mult)
    - GSH: places 1-5 wilds each with own 2-5x value.
           global_mult for this spin = product of all GSH wild values.
           (e.g. GSH places 3 wilds with 2x/3x/2x → spin mult = 1×2×3×2 = 12×)

  BONUS GAME:
    - W  : substitutes + doubles global_mult (persistent across spins)
    - SH : places 1-5 wilds, each doubles global_mult
    - GSH: places 1-5 wilds, each doubles global_mult × its own 2-5x value
    - Wild expands to cover full reel (before win calculation)
    - global_mult never resets mid-bonus

  RETRIGGER : 3 SC in bonus → +5 spins (once per session)
  NUDGE     : 2 SC in base game → 15% chance zombie hand pushes SC into view
  PRE-BONUS : Super/Hidden only — pre-place N wilds before first spin
"""

import random

from game_calculations import GameCalculations
from game_events import (
    shovel_wilds_event,
    golden_shovel_wilds_event,
    wild_expand_event,
    wild_mult_update_event,
    nudge_event,
    pre_bonus_sequence_event,
    bonus_tier_entry_event,
    retrigger_event,
)
from src.calculations.statistics import get_random_outcome


class GameExecutables(GameCalculations):
    """Wild vs Zombies mechanics layer."""

    # ── Multiplier helpers ────────────────────────────────────────────────────

    def _double_global_mult(self, reason: str) -> None:
        """Double global_multiplier (bonus only). Capped at global_mult_cap. Emits globalMultUpdate."""
        prev = self.global_multiplier
        self.global_multiplier = min(self.global_multiplier * 2, self.config.global_mult_cap)
        wild_mult_update_event(self, reason=reason, prev_mult=prev)

    def _apply_gshmult(self, mult_value: int) -> None:
        """Apply a GSH wild's own multiplier value to global_mult (capped).
        Base game only — no event emitted (frontend reads mult from winInfo.meta.globalMult).
        """
        self.global_multiplier = min(self.global_multiplier * mult_value, self.config.global_mult_cap)

    # ── Shovel ────────────────────────────────────────────────────────────────

    def apply_shovel(self, reel: int, row: int) -> None:
        """
        Place 1-5 wilds at random non-SC/SH/GSH positions.

        BASE  : wilds substitute only (no mult change).
        BONUS : each placed wild doubles global_mult.
        """
        num_wilds = get_random_outcome(self.config.shovel_wild_count_weights)
        positions = self._placeable_positions(exclude=(reel, row))
        chosen    = random.sample(positions, min(num_wilds, len(positions)))

        placed = []
        for pos in chosen:
            r, ro = pos["reel"], pos["row"]
            self.board[r][ro] = self.create_symbol("W")
            placed.append({"reel": r, "row": ro})
            if self.gametype == self.config.freegame_type:
                self._double_global_mult("shovel")

        shovel_wilds_event(self, placed, reel, row)
        self.board[reel][row] = self.create_symbol(self._random_pay_symbol())
        self.get_special_symbols_on_board()

    # ── Golden shovel ─────────────────────────────────────────────────────────

    def apply_golden_shovel(self, reel: int, row: int) -> None:
        """
        Place 1-5 multiplier wilds (2-5x each).

        BASE  : each wild applies its own mult value to global_mult
                (no ×2 for being a wild in base game).
        BONUS : each wild first doubles global_mult THEN applies its own value.
        """
        num_wilds = get_random_outcome(self.config.golden_shovel_wild_count_weights)
        positions = self._placeable_positions(exclude=(reel, row))
        chosen    = random.sample(positions, min(num_wilds, len(positions)))

        placed = []
        for pos in chosen:
            r, ro = pos["reel"], pos["row"]
            mult = get_random_outcome(self.config.golden_shovel_mult_weights)
            self.board[r][ro] = self.create_symbol("W")
            placed.append({"reel": r, "row": ro, "mult": mult})

            if self.gametype == self.config.freegame_type:
                # Bonus: ×2 for being a wild, then ×mult for GSH bonus (capped)
                prev = self.global_multiplier
                self.global_multiplier = min(
                    self.global_multiplier * 2 * mult,
                    self.config.global_mult_cap,
                )
                wild_mult_update_event(self, reason="golden_shovel", prev_mult=prev)
            else:
                # Base game: GSH mult only (no ×2)
                self._apply_gshmult(mult)

        golden_shovel_wilds_event(self, placed, reel, row)
        self.board[reel][row] = self.create_symbol(self._random_pay_symbol())
        self.get_special_symbols_on_board()

    # ── Strip wilds (bonus only mult doubling) ────────────────────────────────

    def apply_strip_wild_multipliers(self) -> None:
        """
        In BONUS: for every W currently on the board from the strip reveal
        (already present before shovels ran), double global_mult once per wild.
        Called after board is drawn, BEFORE shovels, so we only count strip wilds.

        In BASE: no-op.
        """
        if self.gametype != self.config.freegame_type:
            return
        wild_count = sum(
            1
            for reel in range(self.config.num_reels)
            for row in range(len(self.board[reel]))
            if self.board[reel][row].name == "W"
        )
        for _ in range(wild_count):
            self._double_global_mult("wild")

    # ── Expanding wilds (bonus only) ─────────────────────────────────────────

    def apply_expanding_wilds(self) -> None:
        """
        BONUS only. For each reel with at least one W: fill all rows with W.
        Called after shovels and strip-wild mult doubling, before win evaluation.
        Expansion does NOT add more mult doublings (already counted at placement).
        """
        for reel in range(self.config.num_reels):
            has_wild = any(
                self.board[reel][row].name == "W"
                for row in range(len(self.board[reel]))
            )
            if not has_wild:
                continue
            for row in range(len(self.board[reel])):
                self.board[reel][row] = self.create_symbol("W")
            wild_expand_event(self, reel)

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

    # ── Pre-bonus wild placement ───────────────────────────────────────────────

    def calc_pre_bonus_placement(self, num_wilds: int) -> list:
        """
        Pre-place num_wilds wilds (Super/Hidden bonus only).
        Each placed wild doubles global_mult (bonus context).
        """
        positions = self._placeable_positions()
        chosen    = random.sample(positions, min(num_wilds, len(positions)))
        for pos in chosen:
            self.board[pos["reel"]][pos["row"]] = self.create_symbol("W")
            self._double_global_mult("wild")

        self.get_special_symbols_on_board()
        self.pre_bonus_steps = chosen
        return chosen

    # ── Bonus entry ───────────────────────────────────────────────────────────

    def setup_bonus_entry(self, scatter_count: int) -> None:
        """Determine tier, set strip, set tot_fs, run pre-bonus, emit bonusTierEntry."""
        self.bonus_tier = self.config.bonus_tier_scatter_map.get(scatter_count, "bonus")

        strip_map = {
            "bonus":        "FR0",
            "super_bonus":  "FR_SUPER",
            "hidden_bonus": "FR_HIDDEN",
        }
        self.freegame_strip = strip_map.get(self.bonus_tier, "FR0")

        # Override tot_fs with tier-specific spin count (authoritative source)
        self.tot_fs = self.config.bonus_tier_spins[self.bonus_tier]

        if self.bonus_tier in self.config.pre_bonus_wild_count_weights:
            wt = self.config.pre_bonus_wild_count_weights[self.bonus_tier]
            n  = get_random_outcome(wt)
            positions = self.calc_pre_bonus_placement(n)
            pre_bonus_sequence_event(self, positions)

        bonus_tier_entry_event(self, self.tot_fs)

    # ── Board special processing ──────────────────────────────────────────────

    def process_base_board_specials(self) -> None:
        """
        BASE GAME: GSH (per-wild mult) → SH (place wilds, no mult) → done.
        Regular W symbols substitute but don't change global_mult.
        """
        gsh = [dict(p) for p in self.special_syms_on_board.get("golden_shovel", [])]
        sh  = [dict(p) for p in self.special_syms_on_board.get("shovel", [])]

        for pos in gsh:
            self.apply_golden_shovel(pos["reel"], pos["row"])
        for pos in sh:
            self.apply_shovel(pos["reel"], pos["row"])

    def process_bonus_board_specials(self) -> None:
        """
        BONUS GAME:
        1. Double mult for every W from the strip reveal.
        2. GSH → SH (each placed wild also doubles mult).
        3. Expand all wild-containing reels to full W.
        """
        # Step 1: strip wilds double mult
        self.apply_strip_wild_multipliers()

        # Step 2: shovels (may add more wilds and double mult per wild)
        gsh = [dict(p) for p in self.special_syms_on_board.get("golden_shovel", [])]
        sh  = [dict(p) for p in self.special_syms_on_board.get("shovel", [])]
        for pos in gsh:
            self.apply_golden_shovel(pos["reel"], pos["row"])
        for pos in sh:
            self.apply_shovel(pos["reel"], pos["row"])

        # Step 3: expand
        self.apply_expanding_wilds()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _placeable_positions(self, exclude: tuple = None) -> list:
        """Board positions not occupied by SC/SH/GSH (safe to overwrite)."""
        blocked = {"SC", "SH", "GSH"}
        return [
            {"reel": r, "row": ro}
            for r in range(self.config.num_reels)
            for ro in range(len(self.board[r]))
            if self.board[r][ro].name not in blocked
            and (exclude is None or (r, ro) != exclude)
        ]

    def _random_pay_symbol(self) -> str:
        """Weighted random regular paying symbol (replaces transformed special)."""
        symbols = ["H1", "H2", "H3", "H4", "H5", "A", "K", "Q", "J", "10"]
        weights = [2,     3,     4,     5,     5,   6,   7,   7,   8,    8]
        return random.choices(symbols, weights=weights, k=1)[0]
