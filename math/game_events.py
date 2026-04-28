"""
Wild vs Zombies — Custom Events (v2)
=======================================
Game-specific event emitters.

Events
------
shovel_wilds_event      : Shovel placed 1-5 wilds on the board.
golden_shovel_wilds_event: Golden shovel placed 1-5 multiplier wilds.
wild_expand_event       : A wild reel expanded to cover all rows (bonus).
wild_mult_update_event  : Global multiplier changed.
nudge_event             : Zombie hand nudged a symbol into the visible window.
pre_bonus_sequence_event: Wild activation sweep before first bonus spin.
bonus_tier_entry_event  : Entered the free-spin bonus.
retrigger_event         : 3 scatters landed in bonus, +5 spins awarded.
"""

from src.events.events import *   # re-export all SDK events


# ── Shovel placed wilds ────────────────────────────────────────────────────────

def shovel_wilds_event(gamestate, positions: list, shovel_reel: int, shovel_row: int) -> None:
    """
    Fired when a SH symbol places wilds on the board.

    Payload
    -------
    shovelReel  : reel the SH symbol landed on (0-indexed).
    shovelRow   : row the SH landed on (padded: +1 if include_padding).
    wildPositions : list of {reel, row} positions where wilds were placed (padded).
    """
    pad = 1 if gamestate.config.include_padding else 0
    padded_positions = [{"reel": p["reel"], "row": p["row"] + pad} for p in positions]
    event = {
        "index":        len(gamestate.book.events),
        "type":         "shovelWilds",
        "shovelReel":   shovel_reel,
        "shovelRow":    shovel_row + pad,
        "wildPositions": padded_positions,
    }
    gamestate.book.add_event(event)


def golden_shovel_wilds_event(
    gamestate,
    positions: list,
    shovel_reel: int,
    shovel_row: int,
) -> None:
    """
    Fired when a GSH symbol places multiplier wilds on the board.

    Payload
    -------
    shovelReel  : reel GSH landed on.
    shovelRow   : row GSH landed on (padded).
    wildPositions : list of {reel, row, mult} where each wild was placed.
    """
    pad = 1 if gamestate.config.include_padding else 0
    padded_positions = [
        {"reel": p["reel"], "row": p["row"] + pad, "mult": p["mult"]}
        for p in positions
    ]
    event = {
        "index":         len(gamestate.book.events),
        "type":          "goldenShovelWilds",
        "shovelReel":    shovel_reel,
        "shovelRow":     shovel_row + pad,
        "wildPositions": padded_positions,
    }
    gamestate.book.add_event(event)


# ── Wild expansion ─────────────────────────────────────────────────────────────

def wild_expand_event(gamestate, reel: int) -> None:
    """
    Fired in the bonus when a reel expands to cover all rows with wilds.
    The 'Rev' tease animation is triggered by the frontend on this event.

    Payload
    -------
    reel    : reel that expanded (0-indexed).
    height  : number of rows expanded to (always config.num_rows[reel]).
    expanded: True if expansion happened; False if wild stalled (no connection).
    """
    event = {
        "index":    len(gamestate.book.events),
        "type":     "wildExpand",
        "reel":     reel,
        "height":   gamestate.config.num_rows[reel],
        "expanded": True,
    }
    gamestate.book.add_event(event)


def wild_stall_event(gamestate, reel: int) -> None:
    """
    Fired when a wild revved but stalled (no connection possible on this reel).
    Frontend plays the smoke-puff animation instead of expansion.
    """
    event = {
        "index":    len(gamestate.book.events),
        "type":     "wildExpand",
        "reel":     reel,
        "height":   gamestate.config.num_rows[reel],
        "expanded": False,
    }
    gamestate.book.add_event(event)


# ── Global multiplier update ───────────────────────────────────────────────────

def wild_mult_update_event(gamestate, reason: str, prev_mult: int) -> None:
    """
    Fired each time the global multiplier changes.

    reason
    ------
    "wild"        : base wild from reel strip (×2).
    "shovel"      : wild placed by SH (×2).
    "golden_shovel": wild placed by GSH (×2 × randMult).
    "expand"      : wild expansion does NOT trigger this; only original wilds do.

    Payload
    -------
    prevMult   : multiplier before this change.
    globalMult : multiplier after this change.
    reason     : see above.
    """
    event = {
        "index":      len(gamestate.book.events),
        "type":       "globalMultUpdate",
        "prevMult":   int(prev_mult),
        "globalMult": int(gamestate.global_multiplier),
        "reason":     reason,
    }
    gamestate.book.add_event(event)


# ── Zombie hand nudge ──────────────────────────────────────────────────────────

def nudge_event(
    gamestate,
    reel: int,
    nudged_symbol: str,
    success: bool,
) -> None:
    """
    Fired when the zombie hand animation plays in the base game.

    success=True  : a scatter (or wild) was nudged into the visible window.
    success=False : the hand appeared but could not find a useful symbol
                    (visual tease only, board is unchanged).

    Payload
    -------
    reel         : reel the nudge acted on.
    nudgedSymbol : name of the symbol pushed into view (or "" if failed).
    success      : bool.
    """
    pad = 1 if gamestate.config.include_padding else 0
    event = {
        "index":        len(gamestate.book.events),
        "type":         "zombieNudge",
        "reel":         reel,
        "nudgedSymbol": nudged_symbol,
        "success":      success,
    }
    gamestate.book.add_event(event)


# ── Pre-bonus sequence ─────────────────────────────────────────────────────────

def pre_bonus_sequence_event(gamestate, wild_positions: list) -> None:
    """
    Fired once before the first bonus spin for Super Bonus and Hidden Bonus.
    Lists wild positions that were pre-activated during the diagonal sweep.

    Payload
    -------
    bonusTier     : "super_bonus" | "hidden_bonus".
    wildPositions : list of {reel, row} for each pre-placed wild (padded).
    """
    pad = 1 if gamestate.config.include_padding else 0
    padded = [{"reel": p["reel"], "row": p["row"] + pad} for p in wild_positions]
    event = {
        "index":        len(gamestate.book.events),
        "type":         "preBonusSequence",
        "bonusTier":    gamestate.bonus_tier,
        "wildPositions": padded,
    }
    gamestate.book.add_event(event)


# ── Bonus tier entry ───────────────────────────────────────────────────────────

def bonus_tier_entry_event(gamestate, spins_awarded: int) -> None:
    """
    Fired once when entering free spins.

    Payload
    -------
    bonusTier    : "bonus" | "super_bonus" | "hidden_bonus".
    spinsAwarded : initial spin count.
    reelStrip    : active reel strip name.
    """
    event = {
        "index":        len(gamestate.book.events),
        "type":         "bonusTierEntry",
        "bonusTier":    gamestate.bonus_tier,
        "spinsAwarded": spins_awarded,
        "reelStrip":    gamestate.freegame_strip,
    }
    gamestate.book.add_event(event)


# ── Retrigger ──────────────────────────────────────────────────────────────────

def retrigger_event(gamestate, spins_added: int) -> None:
    """
    Fired when 3 scatters land during a bonus spin and add extra spins.

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
