"""
Wild vs Zombies — Optimization Setup
======================================
Sets game_config.opt_params, which the Rust optimizer reads to balance
simulation weights so that each distribution achieves its target RTP share.

RTP allocation (base mode, total = 0.96):
  wincap          0.02   (rare 20,000× hits)
  freegame_hidden 0.06   (hidden bonus, 5 SC, ≥1500×)
  freegame_super  0.08   (super bonus, 4 SC)
  freegame        0.25   (standard bonus, 3 SC)
  0               0.00   (zero-win spins)
  basegame        0.55   (base wins without bonus)

RTP allocation (bonus mode, total = 0.96):
  wincap          0.01   (rare 20,000× hits inside buy-bonus)
  freegame        0.95   (standard bonus payout)

These values are starting targets. Re-run after reel-strip tuning if
the optimizer cannot converge within ±0.5% of 0.96.
"""

from optimization_program.optimization_config import (
    ConstructScaling,
    ConstructParameters,
    ConstructConditions,
    ConstructFenceBias,
    verify_optimization_input,
)


class OptimizationSetup:
    """Sets game_config.opt_params for the Rust optimization program."""

    def __init__(self, game_config):
        self.game_config = game_config

        wincaps = {}
        for bm in game_config.bet_modes:
            wincaps[bm.get_name()] = bm.get_wincap()

        wincap_base  = wincaps["base"]   # 20000
        wincap_bonus = wincaps["bonus"]  # 20000

        self.game_config.opt_params = {

            # ── BASE BET MODE ─────────────────────────────────────────────────
            "base": {
                "conditions": {
                    "wincap": ConstructConditions(
                        rtp=0.02,
                        av_win=wincap_base,
                        search_conditions=wincap_base,
                    ).return_dict(),

                    "freegame_hidden": ConstructConditions(
                        rtp=0.06,
                        hr=25,
                        search_conditions={"symbol": "scatter", "kind": "5"},
                    ).return_dict(),

                    "freegame_super": ConstructConditions(
                        rtp=0.08,
                        hr=40,
                        search_conditions={"symbol": "scatter", "kind": "4"},
                    ).return_dict(),

                    "freegame": ConstructConditions(
                        rtp=0.25,
                        hr=50,
                        search_conditions={"symbol": "scatter", "kind": "3"},
                    ).return_dict(),

                    "0": ConstructConditions(
                        rtp=0.0,
                        av_win=0.0,
                        search_conditions=0,
                    ).return_dict(),

                    "basegame": ConstructConditions(
                        rtp=0.55,
                        hr=3.5,
                    ).return_dict(),
                },

                "scaling": ConstructScaling(
                    [
                        # Boost small base-game wins (improves hit-rate feel)
                        {
                            "criteria": "basegame",
                            "scale_factor": 1.3,
                            "win_range": (0.5, 2.0),
                            "probability": 1.0,
                        },
                        # Moderate pull-back on very large base-game wins
                        {
                            "criteria": "basegame",
                            "scale_factor": 0.8,
                            "win_range": (50, 200),
                            "probability": 1.0,
                        },
                        # Pull back mid-range bonus wins slightly (keeps volatility high)
                        {
                            "criteria": "freegame",
                            "scale_factor": 0.85,
                            "win_range": (200, 800),
                            "probability": 1.0,
                        },
                        # Boost large bonus wins for excitement
                        {
                            "criteria": "freegame",
                            "scale_factor": 1.2,
                            "win_range": (2000, 5000),
                            "probability": 1.0,
                        },
                        # Super bonus — pull back lower wins
                        {
                            "criteria": "freegame_super",
                            "scale_factor": 0.8,
                            "win_range": (500, 1500),
                            "probability": 1.0,
                        },
                    ]
                ).return_dict(),

                "parameters": ConstructParameters(
                    num_show=5000,          # smoke: 200  | prod: 5000
                    num_per_fence=10000,     # smoke: 200  | prod: 10000
                    min_m2m=4,
                    max_m2m=10,
                    pmb_rtp=1.0,
                    sim_trials=5000,        # smoke: 200  | prod: 5000
                    test_spins=[50, 100, 200, 500],   # smoke: fast | prod: [50,100,200,500]
                    test_weights=[0.25, 0.35, 0.25, 0.15],
                    score_type="rtp",
                ).return_dict(),

                "distribution_bias": ConstructFenceBias(
                    applied_criteria=["basegame"],
                    bias_ranges=[(1.0, 3.0)],
                    bias_weights=[0.4],
                ).return_dict(),
            },

            # ── BONUS BUY MODE ────────────────────────────────────────────────
            "bonus": {
                "conditions": {
                    "wincap": ConstructConditions(
                        rtp=0.01,
                        av_win=wincap_bonus,
                        search_conditions=wincap_bonus,
                    ).return_dict(),

                    "freegame": ConstructConditions(
                        rtp=0.95,
                        hr=1.0,
                    ).return_dict(),
                },

                "scaling": ConstructScaling(
                    [
                        # Pull back lower bonus-buy wins
                        {
                            "criteria": "freegame",
                            "scale_factor": 0.85,
                            "win_range": (20, 80),
                            "probability": 1.0,
                        },
                        # Moderate pull-back on mid-range
                        {
                            "criteria": "freegame",
                            "scale_factor": 0.8,
                            "win_range": (500, 1500),
                            "probability": 1.0,
                        },
                        # Boost large bonus-buy wins
                        {
                            "criteria": "freegame",
                            "scale_factor": 1.2,
                            "win_range": (3000, 6000),
                            "probability": 1.0,
                        },
                    ]
                ).return_dict(),

                "parameters": ConstructParameters(
                    num_show=5000,          # smoke: 200  | prod: 5000
                    num_per_fence=10000,     # smoke: 200  | prod: 10000
                    min_m2m=4,
                    max_m2m=10,
                    pmb_rtp=1.0,
                    sim_trials=5000,        # smoke: 200  | prod: 5000
                    test_spins=[10, 20, 50],   # smoke: fast | prod: [10,20,50]
                    test_weights=[0.5, 0.3, 0.2],
                    score_type="rtp",
                ).return_dict(),
            },
        }

        verify_optimization_input(self.game_config, self.game_config.opt_params)
