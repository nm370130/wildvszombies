"""
Wild vs Zombies — Game Calculations (v3)
==========================================
Ways-pay win evaluation with per-reel VS multipliers.

VS Multiplier Logic
-------------------
After VS symbols expand and duel, each expanded reel has a per-reel multiplier
stored in self.vs_reel_multipliers {reel_index: int}.

For each winning combination:
  - Determine which reels the win spans (wins always start from reel 0).
  - Sum the VS multipliers for any VS-expanded reels in that span.
  - If the sum > 0: final_win = base_win * sum_of_vs_mults
  - If no VS reels: win is at face value (1x multiplier, no change).

W (Lawnmower) is a simple wild — it substitutes but carries no multiplier.
"""

from src.executables.executables import Executables
from src.calculations.ways import Ways


class GameCalculations(Executables):
    """Ways-pay win calculation with VS per-reel multiplier support."""

    def evaluate_ways_board(self) -> None:
        """
        Calculate ways-pay wins for the current board state.
        Applies VS reel multipliers per win combination (not globally).
        """
        # Pass global_multiplier=1 — VS multipliers are applied per-win below
        self.win_data = Ways.get_ways_data(
            config=self.config,
            board=self.board,
            wild_key="wild",
            global_multiplier=1,
            multiplier_strategy="global",
        )

        # Apply per-reel VS multipliers if any VS expanded this spin
        if self.vs_reel_multipliers and self.win_data["wins"]:
            adjusted_total = 0.0
            for win in self.win_data["wins"]:
                # Wins always span reels 0..kind-1 consecutively
                kind = win["kind"]
                win_reels = set(range(kind))

                # Sum VS multipliers for reels participating in this win
                vs_mult = sum(
                    self.vs_reel_multipliers.get(r, 0)
                    for r in win_reels
                )

                if vs_mult > 0:
                    win["win"] = round(win["win"] * vs_mult, 2)
                    win["meta"]["globalMult"] = vs_mult

                adjusted_total += win["win"]

            self.win_data["totalWin"] = round(adjusted_total, 2)

        if self.win_data["totalWin"] > 0:
            Ways.record_ways_wins(self)
            self.win_manager.update_spinwin(self.win_data["totalWin"])

        Ways.emit_wayswin_events(self)
