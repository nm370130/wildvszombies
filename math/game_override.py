"""
Wild vs Zombies — Game State Overrides (v3)
============================================
Overrides two SDK methods:

1. assign_special_sym_function()
   No per-symbol function assignment needed.

2. reset_book()
   Resets all Wild vs Zombies per-simulation state.

State variables
---------------
vs_reel_multipliers   : dict {reel_index: int} — duel result per reel, reset each spin.
wave_bar_points       : int — cumulative Peashooter hits across entire bonus session.
wave_bar_stage        : int (1-4) — current Wave Bar stage.
pending_duel_spin     : str | None — "duel_spin" | "mega_duel_spin" if queued.
gs_guarantee_countdown: int — spins remaining before forced GSH (Stage 3 mechanic).
bonus_tier            : str — "bonus" | "super_bonus" | "hidden_bonus".
freegame_strip        : str — active reel strip name (informational, used in events).
pre_bonus_steps       : list — activations placed before first bonus spin.
retriggered_bonus     : bool — retrigger fires at most once per session.
"""

from game_executables import GameExecutables


class GameStateOverride(GameExecutables):
    """First class in the MRO — overrides SDK core functions."""

    def assign_special_sym_function(self):
        """No per-symbol function assignment needed."""
        self.special_symbol_functions = {}

    def reset_book(self):
        """Reset SDK state then reset all Wild vs Zombies session state."""
        super().reset_book()

        # Per-spin: VS reel multipliers (reel_index → duel multiplier value).
        # Reset at the start of process_bonus_board_specials each spin.
        self.vs_reel_multipliers = {}

        # Wave Bar — persists across entire bonus session, reset on bonus entry.
        self.wave_bar_points    = 0
        self.wave_bar_stage     = 1

        # DuelSpin queue — set by _trigger_wave_bar_stage or setup_bonus_entry.
        self.pending_duel_spin  = None

        # Stage 3 GSH guarantee countdown (decrements each spin, forces GSH at 0).
        self.gs_guarantee_countdown = 0

        # Bonus metadata
        self.bonus_tier    = "bonus"
        self.freegame_strip = "FR0"
        self.pre_bonus_steps = []

        # Retrigger fires at most once per bonus session
        self.retriggered_bonus = False
