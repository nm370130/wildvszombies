"""
Wild vs Zombies — Game Calculations (v2)
==========================================
Ways-pay win evaluation using the SDK Ways calculator.

Wild key:
  - "wild" for all game modes (W is the only wild symbol).

Global multiplier is applied after all wilds are processed
(including expansions in the bonus).
"""

from src.executables.executables import Executables
from src.calculations.ways import Ways


class GameCalculations(Executables):
    """Ways-pay win calculation."""

    def evaluate_ways_board(self) -> None:
        """
        Calculate ways-pay wins for the current board state.
        global_multiplier is already fully updated before this is called.
        """
        self.win_data = Ways.get_ways_data(
            config=self.config,
            board=self.board,
            wild_key="wild",
            global_multiplier=self.global_multiplier,
            multiplier_strategy="global",
        )

        if self.win_data["totalWin"] > 0:
            Ways.record_ways_wins(self)
            self.win_manager.update_spinwin(self.win_data["totalWin"])

        Ways.emit_wayswin_events(self)
