"""
Wild vs Zombies — Game Configuration (v2)
==========================================
Board: 5x5 fixed. Win type: Ways-pay, min 3 adjacent reels.

Symbols
-------
High pays : H1 Cherry Bomb, H2 Chomper, H3 Wall-nut, H4 Peashooter, H5 Sunflower
Low pays  : A, K, Q, J, 10
Special   : W  (Lawnmower wild) - substitutes all, doubles global mult per wild,
                                  expands to full reel in bonus if creates connection
            SC (Gravestone scatter) - 3/4/5 -> Bonus/Super Bonus/Hidden Bonus
            SH (Shovel)  - places 1-5 wilds at random board positions
            GSH (Golden Shovel) - places 1-5 multiplier wilds (2-5x) randomly

Bonus tiers
-----------
Bonus        (3 SC): 10 spins, FR0 strip
Super Bonus  (4 SC): 12 spins, FR_SUPER, pre-bonus 3-4 wild activations
Hidden Bonus (5 SC): 15 spins, FR_HIDDEN, pre-bonus 5-6 activations,
                     guaranteed >=1500x, cannot be purchased

Retrigger: land 3 SC during bonus -> +5 spins
Nudge    : when 2 SC visible in base game, zombie hand may push a 3rd SC into
           view from just outside the visible window (15% probability)
"""

import os
from src.config.config import Config
from src.config.distributions import Distribution
from src.config.betmode import BetMode


class GameConfig(Config):
    """Wild vs Zombies game configuration."""

    def __init__(self):
        super().__init__()

        self.game_id        = "wild_vs_zombies"
        self.provider_number = 1
        self.working_name   = "Wild vs Zombies"
        self.rtp    = 0.96
        self.wincap = 20000
        self.win_type = "ways"

        self.construct_paths()
        # Override to use our local reels directory
        self.reels_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reels")

        # Board: fixed 5x5
        self.num_reels = 5
        self.num_rows  = [5, 5, 5, 5, 5]
        self.include_padding = True

        # Paytable — W is wild-only (no pay entry); it substitutes for H1 value.
        # Do NOT add W here: the Ways calculator treats it as both a symbol and a wild,
        # causing double-counting. Wilds pay via substitution (H1 line).
        self.paytable = {
            (5, "H1"): 10.00, (4, "H1"):  5.00, (3, "H1"): 2.00,   # Cherry Bomb
            (5, "H2"):  5.00, (4, "H2"):  2.00, (3, "H2"): 1.00,   # Chomper
            (5, "H3"):  3.00, (4, "H3"):  1.50, (3, "H3"): 0.70,   # Wall-nut
            (5, "H4"):  2.50, (4, "H4"):  1.20, (3, "H4"): 0.60,   # Peashooter
            (5, "H5"):  2.00, (4, "H5"):  1.00, (3, "H5"): 0.50,   # Sunflower
            (5, "A"):   1.00, (4, "A"):   0.50, (3, "A"):  0.20,   # Low symbols
            (5, "K"):   1.00, (4, "K"):   0.50, (3, "K"):  0.20,
            (5, "Q"):   1.00, (4, "Q"):   0.50, (3, "Q"):  0.20,
            (5, "J"):   1.00, (4, "J"):   0.50, (3, "J"):  0.20,
            (5, "10"):  1.00, (4, "10"):  0.50, (3, "10"): 0.20,
        }

        self.special_symbols = {
            "wild":          ["W"],
            "scatter":       ["SC"],
            "shovel":        ["SH"],
            "golden_shovel": ["GSH"],
        }

        # SDK freespin triggers (base game scatter counts → initial spins).
        # Freegame retrigger (+5 spins) is handled manually in check_and_award_retrigger.
        # Freegame entry uses 99 as a sentinel so SDK never auto-triggers retrigger
        # during bonus (we manage it ourselves).
        self.freespin_triggers = {
            self.basegame_type: {3: 10, 4: 12, 5: 15},
            self.freegame_type: {99: 5},  # sentinel — retrigger handled manually
        }

        # Global multiplier hard cap: prevents unbounded BigInt arithmetic.
        # Win is already capped at wincap; mult beyond wincap/min_pay has no effect.
        self.global_mult_cap = self.wincap
        self.anticipation_triggers = {
            self.basegame_type: 2,
            self.freegame_type: 0,
        }

        # Shovel mechanics
        self.shovel_wild_count_weights        = {1: 20, 2: 30, 3: 25, 4: 15, 5: 10}
        self.golden_shovel_wild_count_weights = {1: 30, 2: 25, 3: 20, 4: 15, 5: 10}
        self.golden_shovel_mult_weights       = {2: 40, 3: 30, 4: 20, 5: 10}

        # Bonus tiers
        self.bonus_tier_scatter_map = {3: "bonus", 4: "super_bonus", 5: "hidden_bonus"}
        self.bonus_tier_spins       = {"bonus": 10, "super_bonus": 12, "hidden_bonus": 15}

        # Pre-bonus wild activations (only Super + Hidden)
        self.pre_bonus_wild_count_weights = {
            "super_bonus":  {3: 2, 4: 3},
            "hidden_bonus": {5: 3, 6: 4},
        }

        # Retrigger
        self.retrigger_scatter_threshold = 3
        self.retrigger_spins = 5

        # Nudge probability when exactly 2 scatters in base-game spin
        self.nudge_probability = 0.15

        # Reel strips
        reel_files = {
            "BR0":       "BR0.csv",
            "FR0":       "FR0.csv",
            "FR_SUPER":  "FR_SUPER.csv",
            "FR_HIDDEN": "FR_HIDDEN.csv",
            "FRWCAP":    "FRWCAP.csv",
        }
        self.reels = {}
        for strip_id, filename in reel_files.items():
            self.reels[strip_id] = self.read_reels_csv(
                os.path.join(self.reels_path, filename)
            )

        self.bet_modes = [

            # BASE GAME
            BetMode(
                name="base",
                cost=1.25,
                rtp=self.rtp,
                max_win=self.wincap,
                auto_close_disabled=False,
                is_feature=True,
                is_buybonus=False,
                distributions=[
                    Distribution(
                        criteria="wincap",
                        quota=0.001,
                        win_criteria=self.wincap,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FRWCAP": 1},
                            },
                            # Mix of 3/4/5 SC — BR0 now has SC on all 5 reels.
                            # FRWCAP strip handles wincap regardless of bonus tier.
                            "scatter_triggers": {3: 60, 4: 30, 5: 10},
                            "force_wincap": True, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="freegame_hidden",
                        quota=0.004,
                        # No win_criteria: SDK check_repeat uses exact equality,
                        # so win_criteria=1500 would loop forever (FR_HIDDEN hits
                        # wincap almost every spin). The >=1500x guarantee is a
                        # reel-strip design property of FR_HIDDEN, not SDK-enforced.
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FR_HIDDEN": 1},
                            },
                            "scatter_triggers": {5: 1},
                            "force_wincap": False, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="freegame_super",
                        quota=0.020,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FR_SUPER": 1},
                            },
                            "scatter_triggers": {4: 1},
                            "force_wincap": False, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="freegame",
                        quota=0.075,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FR0": 1},
                            },
                            "scatter_triggers": {3: 1},
                            "force_wincap": False, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="0",
                        quota=0.40,
                        win_criteria=0.0,
                        conditions={
                            "reel_weights": {self.basegame_type: {"BR0": 1}},
                            "force_wincap": False, "force_freegame": False,
                        },
                    ),
                    Distribution(
                        criteria="basegame",
                        quota=0.50,
                        conditions={
                            "reel_weights": {self.basegame_type: {"BR0": 1}},
                            "force_wincap": False, "force_freegame": False,
                        },
                    ),
                ],
            ),

            # BONUS BUY — standard bonus only (Hidden cannot be purchased)
            BetMode(
                name="bonus",
                cost=100.0,
                rtp=self.rtp,
                max_win=self.wincap,
                auto_close_disabled=True,
                is_feature=False,
                is_buybonus=True,
                distributions=[
                    Distribution(
                        criteria="wincap",
                        quota=0.001,
                        win_criteria=self.wincap,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FRWCAP": 1},
                            },
                            "scatter_triggers": {3: 1},
                            "force_wincap": True, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="freegame",
                        quota=0.999,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FR0": 1},
                            },
                            "scatter_triggers": {3: 1},
                            "force_wincap": False, "force_freegame": True,
                        },
                    ),
                ],
            ),
        ]
