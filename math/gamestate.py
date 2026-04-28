"""
Wild vs Zombies — Game State (v2)
===================================
Implements run_spin() and run_freespin().

Base game flow
--------------
1. reset_book / reset_seed
2. draw_board  (SDK forces scatter count for freegame distributions)
3. process_base_board_specials  (GSH -> SH)
4. apply_nudge  (only when exactly 2 SC and not force_freegame)
5. evaluate_ways_board
6. update_gametype_wins
7. If 3+ scatters and distribution allows: run_freespin_from_base
8. evaluate_finalwin / check_repeat

Bonus flow
----------
1. reset_fs_spin  (sets gametype=freegame, triggered_freegame=True)
2. setup_bonus_entry  (tier, tot_fs, freegame_strip, pre-bonus wilds)
3. While fs < tot_fs:
   a. update_freespin
   b. draw_board  (SDK uses distribution's reel_weights[freegame] directly)
   c. sync freegame_strip from reelstrip_id (for events)
   d. process_bonus_board_specials  (strip wilds -> GSH -> SH -> expand)
   e. check_and_award_retrigger
   f. evaluate_ways_board
   g. update_gametype_wins
4. end_freespin

Reel strip selection in bonus
------------------------------
The SDK's create_board_reelstrips picks the strip from
distribution_conditions["reel_weights"][freegame_type].
Each distribution already has the right strip:
  freegame        → FR0
  freegame_super  → FR_SUPER
  freegame_hidden → FR_HIDDEN
  wincap          → FRWCAP
No injection needed.
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

            # Draw initial board (SDK forces scatter count when force_freegame=True)
            self.draw_board(emit_event=True)

            # Process GSH / SH (base game — no wild expansion, no global mult)
            self.process_base_board_specials()

            # Zombie hand nudge (only when exactly 2 scatters and not a forced spin)
            if not self.get_current_distribution_conditions()["force_freegame"]:
                self.apply_nudge()

            # Evaluate ways wins
            self.evaluate_ways_board()
            self.win_manager.update_gametype_wins(self.gametype)

            # Check scatter trigger
            if self.check_fs_condition() and self.check_freespin_entry():
                self.run_freespin_from_base()

            self.evaluate_finalwin()
            self.check_repeat()

        self.imprint_wins()

    # ── Free-spin bonus ───────────────────────────────────────────────────────

    def run_freespin(self) -> None:
        # Capture scatter count BEFORE reset_fs_spin changes gametype/board state.
        # This determines the bonus tier (3=bonus, 4=super, 5=hidden).
        scatter_count = self.count_special_symbols("scatter")

        # Reset to freegame state (gametype=freegame, fs=0, triggered_freegame=True)
        self.reset_fs_spin()

        # Determine tier, tot_fs, strip, place pre-bonus wilds (Super/Hidden only)
        self.setup_bonus_entry(scatter_count)

        while self.fs < self.tot_fs:
            self.update_freespin()

            # Draw bonus board — SDK picks strip from distribution reel_weights[freegame]
            self.draw_board(emit_event=True)

            # Sync freegame_strip from the strip actually drawn (used in events)
            self.freegame_strip = getattr(self, "reelstrip_id", self.freegame_strip)

            # Process specials: strip wilds -> GSH -> SH -> expand all wild reels
            self.process_bonus_board_specials()

            # Retrigger check (3+ SC → +5 spins, once per bonus session)
            self.check_and_award_retrigger()

            # Evaluate wins: board is fully expanded, global_mult is accumulated
            self.evaluate_ways_board()
            self.win_manager.update_gametype_wins(self.gametype)

        self.end_freespin()
