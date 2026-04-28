"""
Wild vs Zombies — Game State Overrides
========================================
Overrides two SDK methods:

1. assign_special_sym_function()
   No per-symbol function assignment needed (unlike the expwilds sample game).

2. reset_book()
   Resets custom per-simulation state: global_multiplier, bonus_tier,
   freegame_strip, pre_bonus_steps, retriggered_bonus.

Note on reel strip selection
-----------------------------
Each distribution in game_config.py already specifies the correct
reel_weights[freegame_type] for its tier:

  "freegame"        → {"FR0": 1}
  "freegame_super"  → {"FR_SUPER": 1}
  "freegame_hidden" → {"FR_HIDDEN": 1}
  "wincap"          → {"FRWCAP": 1}

The SDK's create_board_reelstrips uses these weights directly for every
bonus spin (the criteria stays fixed for the full spin cycle). No injection
needed — and injecting would permanently mutate the shared distribution dict.
"""

from game_executables import GameExecutables


class GameStateOverride(GameExecutables):
    """First class in the MRO — overrides SDK core functions."""

    def assign_special_sym_function(self):
        """No per-symbol function assignment needed."""
        self.special_symbol_functions = {}

    def reset_book(self):
        """
        Calls SDK reset_book then resets all Wild vs Zombies state.
        """
        super().reset_book()

        # Global multiplier — starts at 1, doubles per wild in bonus.
        self.global_multiplier = 1

        # Bonus tier — set on bonus entry.
        # Values: "bonus" | "super_bonus" | "hidden_bonus"
        self.bonus_tier = "bonus"

        # Reel strip active during freegame (informational, used in events).
        # Actual strip selection comes from the distribution's reel_weights.
        self.freegame_strip = "FR0"

        # Pre-bonus wild activation steps (populated before first bonus spin).
        self.pre_bonus_steps = []

        # Retrigger fires at most once per bonus session.
        self.retriggered_bonus = False
