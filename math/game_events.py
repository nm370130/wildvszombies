"""
Wild vs Zombies — Custom Events (v3)
=======================================
Game-specific event emitters.

Events
------
shovel_wilds_event       : Shovel placed 1-3 simple wilds.
golden_shovel_vs_event   : Golden Shovel placed 1-2 VS symbols.
vs_expand_event          : VS symbol expanded to full reel (becomes wild).
duel_sequence_event      : Duel Sequence result (shots, multiplier) for one reel.
wave_bar_update_event    : Wave Bar points/stage changed.
duel_spin_event          : DuelSpin or MegaDuelSpin triggered by Wave Bar stage.
nudge_event              : Zombie hand nudged a symbol into the visible window.
pre_bonus_sequence_event : W/VS activation sweep before first bonus spin.
bonus_tier_entry_event   : Entered the free-spin bonus.
retrigger_event          : 3 scatters landed in bonus, +5 spins awarded.
"""

from src.events.events import *   # re-export all SDK events


# ── Shovel placed wilds ────────────────────────────────────────────────────────

def shovel_wilds_event(gamestate, positions: list, shovel_reel: int, shovel_row: int) -> None:
    """
    Fired when a SH symbol places 1-3 simple wilds on the board.

    Payload
    -------
    shovelReel    : reel the SH landed on (0-indexed).
    shovelRow     : row the SH landed on (padded).
    wildPositions : list of {reel, row} where wilds were placed (padded).
    """
    pad = 1 if gamestate.config.include_padding else 0
    event = {
        "index":         len(gamestate.book.events),
        "type":          "shovelWilds",
        "shovelReel":    shovel_reel,
        "shovelRow":     shovel_row + pad,
        "wildPositions": [{"reel": p["reel"], "row": p["row"] + pad} for p in positions],
    }
    gamestate.book.add_event(event)


# ── Golden Shovel placed VS symbols ───────────────────────────────────────────

def golden_shovel_vs_event(
    gamestate,
    vs_positions: list,
    shovel_reel: int,
    shovel_row: int,
) -> None:
    """
    Fired when a GSH symbol places 1-2 VS symbols on the board.
    The VS symbols will immediately expand and trigger duel sequences.

    Payload
    -------
    shovelReel  : reel GSH landed on.
    shovelRow   : row GSH landed on (padded).
    vsPositions : list of {reel, row} for each VS placed (padded).
    """
    pad = 1 if gamestate.config.include_padding else 0
    event = {
        "index":      len(gamestate.book.events),
        "type":       "goldenShovelVS",
        "shovelReel": shovel_reel,
        "shovelRow":  shovel_row + pad,
        "vsPositions": [{"reel": p["reel"], "row": p["row"] + pad} for p in vs_positions],
    }
    gamestate.book.add_event(event)


# ── VS expansion ───────────────────────────────────────────────────────────────

def vs_expand_event(gamestate, reel: int) -> None:
    """
    Fired when a VS symbol on a reel expands to cover all rows (becomes wild).
    Precedes the duel_sequence_event for the same reel.

    Payload
    -------
    reel   : reel that expanded (0-indexed).
    height : number of rows (always config.num_rows[reel]).
    """
    event = {
        "index":  len(gamestate.book.events),
        "type":   "vsExpand",
        "reel":   reel,
        "height": gamestate.config.num_rows[reel],
    }
    gamestate.book.add_event(event)


# ── Duel Sequence result ───────────────────────────────────────────────────────

def duel_sequence_event(
    gamestate,
    reel: int,
    shots: list,
    final_mult: int,
) -> None:
    """
    Fired after a Duel Sequence resolves on one reel.

    Payload
    -------
    reel      : reel the duel happened on (0-indexed).
    shots     : list of individual shot multiplier values e.g. [3, 5] = 8x total.
    finalMult : cumulative sum of all shots (the reel multiplier applied to wins).
    shotCount : number of successful Peashooter shots.
    """
    event = {
        "index":     len(gamestate.book.events),
        "type":      "duelSequence",
        "reel":      reel,
        "shots":     shots,
        "finalMult": final_mult,
        "shotCount": len(shots),
    }
    gamestate.book.add_event(event)


# ── Wave Bar update ────────────────────────────────────────────────────────────

def wave_bar_update_event(gamestate, points_added: int, total_points: int, stage: int) -> None:
    """
    Fired whenever the Wave Bar accumulates new points.

    Payload
    -------
    pointsAdded  : how many new points were added this duel.
    totalPoints  : running total for this bonus session.
    stage        : current Wave Bar stage (1-4).
    stageChanged : True if a new stage was reached by this update.
    """
    event = {
        "index":        len(gamestate.book.events),
        "type":         "waveBarUpdate",
        "pointsAdded":  points_added,
        "totalPoints":  total_points,
        "stage":        stage,
        "stageChanged": False,  # set True by caller when stage advances
    }
    gamestate.book.add_event(event)


def wave_bar_stage_event(gamestate, new_stage: int, spin_type: str) -> None:
    """
    Fired when the Wave Bar crosses a stage threshold.

    Payload
    -------
    newStage : 2, 3, or 4.
    spinType : "duel_spin" | "mega_duel_spin" — the special spin awarded.
    """
    event = {
        "index":    len(gamestate.book.events),
        "type":     "waveBarStage",
        "newStage": new_stage,
        "spinType": spin_type,
    }
    gamestate.book.add_event(event)


# ── DuelSpin / MegaDuelSpin ────────────────────────────────────────────────────

def duel_spin_event(gamestate, spin_type: str, guaranteed_vs: int) -> None:
    """
    Fired at the start of a DuelSpin or MegaDuelSpin.

    Payload
    -------
    spinType      : "duel_spin" | "mega_duel_spin".
    guaranteedVS  : number of VS symbols guaranteed to land as part of wins.
    """
    event = {
        "index":        len(gamestate.book.events),
        "type":         "duelSpin",
        "spinType":     spin_type,
        "guaranteedVS": guaranteed_vs,
    }
    gamestate.book.add_event(event)


# ── Zombie hand nudge ──────────────────────────────────────────────────────────

def nudge_event(gamestate, reel: int, nudged_symbol: str, success: bool) -> None:
    """
    Fired when the zombie hand animation plays in the base game.

    Payload
    -------
    reel         : reel the nudge acted on.
    nudgedSymbol : name of the symbol pushed into view (or "" if failed).
    success      : True if a useful symbol was pushed in.
    """
    event = {
        "index":        len(gamestate.book.events),
        "type":         "zombieNudge",
        "reel":         reel,
        "nudgedSymbol": nudged_symbol,
        "success":      success,
    }
    gamestate.book.add_event(event)


# ── Pre-bonus sequence ─────────────────────────────────────────────────────────

def pre_bonus_sequence_event(gamestate, activations: list) -> None:
    """
    Fired once before the first bonus spin for Super Bonus and Hidden Bonus.
    Lists all pre-placed symbols (W and VS) with their positions and types.

    Payload
    -------
    bonusTier   : "super_bonus" | "hidden_bonus".
    activations : list of {reel, row, symbol} for each placed symbol (padded).
                  symbol is "W" or "VS".
    """
    pad = 1 if gamestate.config.include_padding else 0
    padded = [
        {"reel": p["reel"], "row": p["row"] + pad, "symbol": p["symbol"]}
        for p in activations
    ]
    event = {
        "index":       len(gamestate.book.events),
        "type":        "preBonusSequence",
        "bonusTier":   gamestate.bonus_tier,
        "activations": padded,
    }
    gamestate.book.add_event(event)


# ── Bonus tier entry ───────────────────────────────────────────────────────────

def bonus_tier_entry_event(gamestate, spins_awarded: int) -> None:
    """
    Fired once when entering free spins.

    Payload
    -------
    bonusTier      : "bonus" | "super_bonus" | "hidden_bonus".
    spinsAwarded   : initial spin count.
    reelStrip      : active reel strip name.
    waveBarStage   : starting Wave Bar stage (1/2/3 depending on tier).
    """
    event = {
        "index":        len(gamestate.book.events),
        "type":         "bonusTierEntry",
        "bonusTier":    gamestate.bonus_tier,
        "spinsAwarded": spins_awarded,
        "reelStrip":    gamestate.freegame_strip,
        "waveBarStage": gamestate.wave_bar_stage,
    }
    gamestate.book.add_event(event)


# ── Retrigger ──────────────────────────────────────────────────────────────────

def retrigger_event(gamestate, spins_added: int) -> None:
    """
    Fired when 3 scatters land during a bonus spin, adding extra spins.

    Payload
    -------
    spinsAdded : always config.retrigger_spins (5).
    totalFs    : updated total spin count.
    """
    event = {
        "index":      len(gamestate.book.events),
        "type":       "retrigger",
        "spinsAdded": spins_added,
        "totalFs":    int(gamestate.tot_fs),
    }
    gamestate.book.add_event(event)
