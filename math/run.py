"""
Wild vs Zombies — Simulation Runner
======================================
Always run via the helper script (it sets PYTHONPATH to the math-sdk):

    bash run.sh          # smoke test  (10 K sims)
    bash run.sh prod     # production  (1 M / 500 K sims)

Do NOT run this file directly with `python run.py` — the math-sdk must be
on PYTHONPATH for the imports below to resolve. run.sh handles that.

For a quick smoke test:  set num_sim_args values to int(1e3).
For a production run:    set num_sim_args to int(1e6) / int(5e5).
"""

from gamestate import GameState
from game_config import GameConfig
from game_optimization import OptimizationSetup
from src.state.run_sims import create_books
from src.write_data.write_configs import generate_configs

try:
    from optimization_program.run_script import OptimizationExecution
    _HAS_OPTIMIZER = True
except ImportError:
    _HAS_OPTIMIZER = False

try:
    from utils.game_analytics.run_analysis import create_stat_sheet
    _HAS_ANALYSIS = True
except ImportError:
    _HAS_ANALYSIS = False

try:
    from utils.rgs_verification import execute_all_tests
    _HAS_VERIFICATION = True
except ImportError:
    _HAS_VERIFICATION = False


if __name__ == "__main__":

    # Threading / compression
    threads      = 4
    rust_threads = 4
    batch_size   = 500   # must be <= num_sims; SDK runs min 1 full batch
    compress     = True
    profiling    = False

    # Sim counts
    # Smoke test : 1_000 / 1_000   (sims only, no optimization)
    # Production : 1_000_000 / 500_000  (+ run_optimization: True)
    num_sim_args = {
        "base":  1_000,   # smoke: 1_000  | prod: 1_000_000
        "bonus": 1_000,   # smoke: 1_000  | prod: 500_000
    }

    run_conditions = {
        "run_sims":          True,
        "run_optimization":  False,  # production only — needs ≥ 200K base sims (wincap quota=0.001)
        "run_analysis":      True,
        "run_format_checks": True,
    }

    target_modes = ["base", "bonus"]

    config    = GameConfig()
    gamestate = GameState(config)

    # Must be instantiated before create_books and optimization —
    # it sets config.opt_params which both the config writer and optimizer need.
    OptimizationSetup(config)

    if run_conditions["run_sims"]:
        create_books(
            gamestate,
            config,
            num_sim_args,
            batch_size,
            threads,
            compress,
            profiling,
        )

    generate_configs(gamestate)

    if run_conditions["run_optimization"]:
        OptimizationExecution().run_all_modes(config, target_modes, rust_threads)
        generate_configs(gamestate)

    if run_conditions["run_analysis"]:
        custom_keys = [
            {"symbol": "scatter"},
            {"symbol": "shovel"},
            {"symbol": "golden_shovel"},
            {"symbol": "wild"},
        ]
        create_stat_sheet(gamestate, custom_keys=custom_keys)

    if run_conditions["run_format_checks"]:
        execute_all_tests(config)
