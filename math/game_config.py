"""
Wild vs Zombies — Game Configuration (v3)
==========================================
Board: 5x5 fixed. Win type: Ways-pay, min 3 adjacent reels.

Symbols
-------
High pays : H1 Cherry Bomb, H2 Chomper, H3 Wall-nut, H4 Peashooter, H5 Sunflower
Low pays  : A, K, Q, J, 10
Special   : W  (Lawnmower wild) - simple substitute only, no expansion, no multiplier
            VS (Versus)        - bonus-only; expands to full reel when part of a win,
                                 then triggers Duel Sequence for a per-reel multiplier
            SC (Gravestone scatter) - 3/4/5 -> Bonus/Super Bonus/Hidden Bonus
            SH (Shovel)  - bonus-only; places 1-3 simple wilds, transforms to paying sym
            GSH (Golden Shovel) - bonus-only; places 1-2 VS symbols, transforms to paying sym

Bonus tiers
-----------
Bonus        (3 SC): 10 spins, FR0 strip,      Wave Bar starts Stage 1
Super Bonus  (4 SC or buy): 12 spins, FR_SUPER, Wave Bar starts Stage 2
Hidden Bonus (5 SC, no buy): 15 spins, FR_HIDDEN, Wave Bar starts Stage 3

Duel Sequence (VS symbol)
--------------------------
First shot guaranteed. Roll from duel_shot_values {2,3,5,8,10}.
After each shot: duel_continue_prob chance to fire again, else zombie wins.
Shots accumulate additively. Max duel_max_shots shots.
Per-reel multiplier = cumulative shot sum.
Multiple VS reels in same win: multipliers are ADDED, then applied to that win.

Wave Bar (bonus-only progression)
----------------------------------
Points = total Peashooter shots that hit across all duels this bonus session.
Stage 2 (5 pts):  +1 DuelSpin  (1 guaranteed VS win, slightly better odds)
Stage 3 (12 pts): +1 DuelSpin  (2 guaranteed VS wins) + GSH guaranteed in next 3 spins
Stage 4 (20 pts): +1 MegaDuelSpin (3 guaranteed VS wins, boosted odds) + +3 extra spins

Retrigger: land 3 SC during bonus -> +5 spins (once per session)
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

        self.game_id         = "wild_vs_zombies"
        self.provider_number = 1
        self.working_name    = "Wild vs Zombies"
        self.rtp    = 0.96
        self.wincap = 20000
        self.win_type = "ways"

        self.construct_paths()
        self.reels_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reels")

        self.num_reels = 5
        self.num_rows  = [5, 5, 5, 5, 5]
        self.include_padding = True

        # Paytable — W and VS are wilds (no pay entry).
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
            "wild":          ["W", "VS"],   # VS acts as wild after expansion
            "scatter":       ["SC"],
            "shovel":        ["SH"],
            "golden_shovel": ["GSH"],
            "versus":        ["VS"],        # tracked separately for duel logic
        }

        self.freespin_triggers = {
            self.basegame_type: {3: 10, 4: 12, 5: 15},
            self.freegame_type: {99: 5},    # retrigger handled manually
        }

        # ── Shovel mechanics (updated) ────────────────────────────────────────
        # Shovel now places 1-3 simple wilds only (down from 1-5)
        self.shovel_wild_count_weights = {1: 30, 2: 40, 3: 30}

        # Golden Shovel now places 1-2 VS symbols (replaces multiplier wilds)
        self.golden_shovel_vs_count_weights = {1: 50, 2: 50}

        # ── Duel Sequence parameters ──────────────────────────────────────────
        # Shot values pool for the Peashooter duel
        self.duel_shot_values = [2, 3, 5, 8, 10]
        # Minimum shot value for Hidden Bonus ("minimum multiplier per shot raised")
        self.duel_hidden_min_shot_value = 3
        # Max shots per VS reel
        self.duel_max_shots = 5
        # Probability the Peashooter fires again after each shot (per tier/mode)
        self.duel_continue_prob = {
            "bonus":       0.50,
            "super_bonus": 0.55,
            "hidden_bonus": 0.65,
            "stage4":      0.70,   # boosted odds during MegaDuelSpin
        }

        # ── Wave Bar thresholds ───────────────────────────────────────────────
        # Points come from Peashooter shots that hit during any duel this bonus session
        self.wave_bar_thresholds = {2: 5, 3: 12, 4: 20}
        self.wave_bar_stage4_extra_spins = 3

        # ── Bonus tiers ───────────────────────────────────────────────────────
        self.bonus_tier_scatter_map = {3: "bonus", 4: "super_bonus", 5: "hidden_bonus"}
        self.bonus_tier_spins       = {"bonus": 10, "super_bonus": 12, "hidden_bonus": 15}
        # Starting Wave Bar stage per tier
        self.bonus_tier_start_stage = {"bonus": 1, "super_bonus": 2, "hidden_bonus": 3}

        # Pre-bonus sweep activation counts per tier (mix of W and VS placed)
        # Values are weights: {count: weight}
        self.pre_bonus_activation_weights = {
            "super_bonus":  {3: 3, 4: 7},      # 3-4 activations
            "hidden_bonus": {5: 5, 6: 5},       # 5-6 activations
        }
        # Probability each pre-bonus activation is VS (rest are W)
        self.pre_bonus_vs_prob = {
            "super_bonus":  0.50,
            "hidden_bonus": 0.60,
        }

        # ── Retrigger ─────────────────────────────────────────────────────────
        self.retrigger_scatter_threshold = 3
        self.retrigger_spins = 5

        # ── Anticipation / nudge ──────────────────────────────────────────────
        self.anticipation_triggers = {
            self.basegame_type: 2,
            self.freegame_type: 0,
        }
        self.nudge_probability = 0.15

        # ── Reel strips ───────────────────────────────────────────────────────
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

            # ── BASE GAME ────────────────────────────────────────────────────
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
                            "scatter_triggers": {3: 60, 4: 30, 5: 10},
                            "force_wincap": True, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="freegame_hidden",
                        quota=0.004,
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

            # ── BONUS HUNT (5x more likely to trigger a bonus round) ─────────
            BetMode(
                name="bonus_hunt",
                cost=6.25,          # 5x base cost
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
                            "scatter_triggers": {3: 60, 4: 30, 5: 10},
                            "force_wincap": True, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="freegame_hidden",
                        quota=0.020,
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
                        quota=0.100,
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
                        quota=0.375,    # 5x base freegame quota
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
                        quota=0.20,
                        win_criteria=0.0,
                        conditions={
                            "reel_weights": {self.basegame_type: {"BR0": 1}},
                            "force_wincap": False, "force_freegame": False,
                        },
                    ),
                    Distribution(
                        criteria="basegame",
                        quota=0.304,
                        conditions={
                            "reel_weights": {self.basegame_type: {"BR0": 1}},
                            "force_wincap": False, "force_freegame": False,
                        },
                    ),
                ],
            ),

            # ── BONUS BUY — standard bonus (10 spins) ───────────────────────
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

            # ── SUPER BONUS BUY — super bonus (12 spins, now purchasable) ───
            BetMode(
                name="super_bonus",
                cost=250.0,
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
                            "scatter_triggers": {4: 1},
                            "force_wincap": True, "force_freegame": True,
                        },
                    ),
                    Distribution(
                        criteria="freegame",
                        quota=0.999,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BR0": 1},
                                self.freegame_type: {"FR_SUPER": 1},
                            },
                            "scatter_triggers": {4: 1},
                            "force_wincap": False, "force_freegame": True,
                        },
                    ),
                ],
            ),
        ]
