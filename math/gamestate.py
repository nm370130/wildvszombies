"""
Wild vs Zombies — Game State (v3)
===================================
Implements run_spin() and run_freespin().

Base game flow
--------------
1. reset_book / reset_seed
2. draw_board
3. process_base_board_specials  (no-op: no specials in base game)
4. apply_nudge  (only when exactly 2 SC and not force_freegame)
5. evaluate_ways_board
6. update_gametype_wins
7. If 3+ scatters and distribution allows: run_freespin_from_base
8. evaluate_finalwin / check_repeat

Bonus flow
----------
1. reset_fs_spin
2. setup_bonus_entry  (tier, tot_fs, wave_bar_stage, pre-bonus activation)
3. While fs < tot_fs:
   a. update_freespin
   b. If pending_duel_spin: run special DuelSpin/MegaDuelSpin spin
      Otherwise: draw_board normally
   c. process_bonus_board_specials  (GSH → SH → VS strip expansion)
   d. check_and_award_retrigger
   e. evaluate_ways_board  (VS multipliers applied per-win)
   f. update_gametype_wins
4. end_freespin

DuelSpin / MegaDuelSpin
-----------------------
When pending_duel_spin is set:
  - Draw the board normally (strip-based).
  - Call setup_duel_spin(spin_type) which places guaranteed VS symbols.
  - process_bonus_board_specials runs with boosted=True for mega_duel_spin.
  - Clear pending_duel_spin after use.

GSH Guarantee (Stage 3)
------------------------
gs_guarantee_countdown decrements each spin. When it reaches 0,
check_gs_guarantee() forces a GSH onto the board before processing.
"""

from game_override import GameStateOverride


class GameState(GameStateOverride):
    """Full Wild vs Zombies game logic."""

    # ── Base game ─────────────────────────────────────────────────────────────

    def run_spin(self, sim: int, simulation_seed=None) -> None:
        self.reset_seed(sim, seed_override=simulation_seed)
        self.repeat = True

        while self.repeat:
            self.reset_book()
            self.draw_board(emit_event=True)

            # Base game: W is simple wild, no specials to process
            self.process_base_board_specials()

            # Zombie hand nudge (only when exactly 2 scatters, not a forced spin)
            if not self.get_current_distribution_conditions()["force_freegame"]:
                self.apply_nudge()

            self.evaluate_ways_board()
            self.win_manager.update_gametype_wins(self.gametype)

            if self.check_fs_condition() and self.check_freespin_entry():
                self.run_freespin_from_base()

            self.evaluate_finalwin()
            self.check_repeat()

        self.imprint_wins()

    # ── Free-spin bonus ───────────────────────────────────────────────────────

    def run_freespin(self) -> None:
        scatter_count = self.count_special_symbols("scatter")

        self.reset_fs_spin()

        # Determine tier, tot_fs, wave_bar_stage, pre-bonus activation
        self.setup_bonus_entry(scatter_count)

        while self.fs < self.tot_fs:
            self.update_freespin()

            # ── Handle pending DuelSpin / MegaDuelSpin ────────────────────
            duel_type = self.pending_duel_spin
            boosted   = False

            if duel_type is not None:
                self.pending_duel_spin = None
                # Draw the base board first (strip-based)
                self.draw_board(emit_event=True)
                self.freegame_strip = getattr(self, "reelstrip_id", self.freegame_strip)
                # Place guaranteed VS symbols on the board
                boosted = self.setup_duel_spin(duel_type)
            else:
                self.draw_board(emit_event=True)
                self.freegame_strip = getattr(self, "reelstrip_id", self.freegame_strip)

            # ── Process specials: GSH → SH → VS expansion + duel ─────────
            self.process_bonus_board_specials(boosted=boosted)

            # ── Retrigger check ───────────────────────────────────────────
            self.check_and_award_retrigger()

            # ── Win evaluation (VS multipliers applied per-win) ───────────
            self.evaluate_ways_board()
            self.win_manager.update_gametype_wins(self.gametype)

        self.end_freespin()
