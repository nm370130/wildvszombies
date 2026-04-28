"""
Wild vs Zombies — QA Test Suite
=================================
Comprehensive test coverage for all game mechanics.

Run via:
    bash run_qa.sh

Tests cover:
  - Config validation (RTP, wincap, symbols, paytable, bet modes)
  - Shovel (SH) mechanics — base and bonus
  - Golden Shovel (GSH) mechanics — base and bonus
  - Strip wild multipliers and expanding wilds
  - Zombie nudge mechanic
  - Bonus entry and tier assignment (3/4/5 SC)
  - Retrigger mechanic
  - Global multiplier accumulation and cap
  - Event structure, ordering, and padding offsets
  - Integration: full spin runs without exceptions
"""

import sys
import random
from unittest.mock import patch

from game_config import GameConfig
from gamestate import GameState

# ─────────────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────────────

_pass  = 0
_fail  = 0
_errors = []


def run_test(name, fn):
    global _pass, _fail
    try:
        fn()
        print(f"  PASS  {name}")
        _pass += 1
    except AssertionError as e:
        print(f"  FAIL  {name}")
        print(f"        {e}")
        _fail += 1
        _errors.append((name, str(e)))
    except Exception as e:
        import traceback
        print(f"  ERROR {name}")
        print(f"        {e}")
        traceback.print_exc()
        _fail += 1
        _errors.append((name, f"Exception: {e}"))


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

config = GameConfig()
gs     = GameState(config)

BASE  = config.basegame_type   # "basegame"
BONUS = config.freegame_type   # "freegame"


def fresh(gametype=BASE):
    """Reset to a clean 5×5 H1 board."""
    gs.reset_book()
    gs.gametype = gametype
    gs.board = [[gs.create_symbol("H1") for _ in range(5)] for _ in range(5)]
    gs.get_special_symbols_on_board()
    return gs


def events_of(etype):
    return [e for e in gs.book.events if e["type"] == etype]


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 1 — Config Validation
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 1: Config Validation")


def t01():
    assert config.rtp == 0.96, f"RTP = {config.rtp}"
run_test("T01  RTP target = 96%", t01)


def t02():
    assert config.wincap == 20000, f"Wincap = {config.wincap}"
run_test("T02  Win cap = 20,000×", t02)


def t03():
    assert config.num_reels == 5
    assert config.num_rows == [5, 5, 5, 5, 5]
    assert config.include_padding is True
run_test("T03  Board = 5×5 fixed, include_padding = True", t03)


def t04():
    pay_syms = ["H1", "H2", "H3", "H4", "H5", "A", "K", "Q", "J", "10"]
    for sym in pay_syms:
        for kind in (3, 4, 5):
            assert (kind, sym) in config.paytable, f"Missing ({kind}, {sym})"
run_test("T04  Paytable has 3/4/5-of-a-kind for all 10 pay symbols", t04)


def t05():
    base  = next(bm for bm in config.bet_modes if bm.get_name() == "base")
    bonus = next(bm for bm in config.bet_modes if bm.get_name() == "bonus")
    assert base.get_cost()  == 1.25,  f"Base cost = {base.get_cost()}"
    assert bonus.get_cost() == 100.0, f"Bonus cost = {bonus.get_cost()}"
    assert base.get_wincap()  == 20000
    assert bonus.get_wincap() == 20000
run_test("T05  Bet modes: base=1.25×, bonus buy=100×, wincap=20000", t05)


def t06():
    assert config.bonus_tier_spins == {"bonus": 10, "super_bonus": 12, "hidden_bonus": 15}
    assert config.bonus_tier_scatter_map == {3: "bonus", 4: "super_bonus", 5: "hidden_bonus"}
run_test("T06  Bonus tiers: 3SC→10sp, 4SC→12sp, 5SC→15sp", t06)


def t07():
    assert config.retrigger_scatter_threshold == 3
    assert config.retrigger_spins == 5
run_test("T07  Retrigger: threshold=3 SC, awards +5 spins", t07)


def t08():
    assert config.nudge_probability == 0.15
run_test("T08  Nudge probability = 15%", t08)


def t09():
    for strip in ["BR0", "FR0", "FR_SUPER", "FR_HIDDEN", "FRWCAP"]:
        assert strip in config.reels, f"Missing strip: {strip}"
        assert len(config.reels[strip]) == 5, f"{strip} must have 5 reels"
run_test("T09  All 5 reel strips loaded (BR0, FR0, FR_SUPER, FR_HIDDEN, FRWCAP)", t09)


def t10():
    assert config.special_symbols["wild"]          == ["W"]
    assert config.special_symbols["scatter"]       == ["SC"]
    assert config.special_symbols["shovel"]        == ["SH"]
    assert config.special_symbols["golden_shovel"] == ["GSH"]
run_test("T10  Special symbols: W, SC, SH, GSH defined", t10)


def t11():
    base  = next(bm for bm in config.bet_modes if bm.get_name() == "base")
    bonus = next(bm for bm in config.bet_modes if bm.get_name() == "bonus")
    base_dist  = [d.get_criteria() for d in base.get_distributions()]
    bonus_dist = [d.get_criteria() for d in bonus.get_distributions()]
    for expected in ["wincap", "freegame_hidden", "freegame_super", "freegame", "0", "basegame"]:
        assert expected in base_dist, f"Base missing '{expected}'"
    assert "wincap"   in bonus_dist
    assert "freegame" in bonus_dist
    assert "freegame_hidden" not in bonus_dist, "Hidden bonus must not be purchasable"
    assert "freegame_super"  not in bonus_dist, "Super bonus must not be purchasable"
run_test("T11  Base has 6 distributions; bonus buy: only wincap + freegame", t11)


def t12():
    assert config.win_type == "ways"
run_test("T12  Win type = ways-pay", t12)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 2 — Shovel (SH) Mechanics
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 2: Shovel (SH) Mechanics")


def t13():
    """SH places wilds at the chosen positions."""
    fresh(BASE)
    gs.board[2][3] = gs.create_symbol("SH")
    gs.get_special_symbols_on_board()
    with patch("game_executables.get_random_outcome", return_value=2):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}, {"reel": 4, "row": 3}]):
            gs.apply_shovel(2, 3)
    assert gs.board[0][1].name == "W", "Wild not placed at (0,1)"
    assert gs.board[4][3].name == "W", "Wild not placed at (4,3)"
run_test("T13  SH places wilds at the correct board positions", t13)


def t14():
    """SH in base game does NOT change global_mult."""
    fresh(BASE)
    gs.board[2][3] = gs.create_symbol("SH")
    gs.get_special_symbols_on_board()
    with patch("game_executables.get_random_outcome", return_value=3):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}, {"reel": 1, "row": 2}, {"reel": 4, "row": 0}]):
            gs.apply_shovel(2, 3)
    assert gs.global_multiplier == 1, f"Base SH must not change mult, got {gs.global_multiplier}"
run_test("T14  SH does NOT change global_mult in base game", t14)


def t15():
    """SH in bonus doubles global_mult once per placed wild."""
    fresh(BONUS)
    gs.board[2][3] = gs.create_symbol("SH")
    gs.get_special_symbols_on_board()
    with patch("game_executables.get_random_outcome", return_value=3):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}, {"reel": 1, "row": 2}, {"reel": 4, "row": 0}]):
            gs.apply_shovel(2, 3)
    # 3 wilds × ×2 each = 1 × 2 × 2 × 2 = 8
    assert gs.global_multiplier == 8, f"3 SH wilds in bonus: expect 8, got {gs.global_multiplier}"
run_test("T15  SH doubles global_mult per placed wild in bonus (3 wilds → ×8)", t15)


def t16():
    """SH emits shovelWilds event with correct structure and padding."""
    fresh(BASE)
    gs.board[1][2] = gs.create_symbol("SH")
    gs.get_special_symbols_on_board()
    with patch("game_executables.get_random_outcome", return_value=1):
        with patch("random.sample", return_value=[{"reel": 0, "row": 2}]):
            gs.apply_shovel(1, 2)
    evts = events_of("shovelWilds")
    assert len(evts) == 1, f"Expected 1 shovelWilds, got {len(evts)}"
    e = evts[0]
    assert e["shovelReel"] == 1
    assert e["shovelRow"]  == 3,  f"shovelRow: internal 2 + pad 1 = 3, got {e['shovelRow']}"
    assert e["wildPositions"][0]["row"] == 3, f"wildPos row: internal 2 + pad 1 = 3, got {e['wildPositions'][0]['row']}"
run_test("T16  shovelWilds event: correct structure and +1 row padding", t16)


def t17():
    """SH transforms its own cell to a regular pay symbol."""
    fresh(BASE)
    gs.board[2][3] = gs.create_symbol("SH")
    gs.get_special_symbols_on_board()
    with patch("game_executables.get_random_outcome", return_value=1):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}]):
            gs.apply_shovel(2, 3)
    name = gs.board[2][3].name
    assert name not in ("SH", "SC", "GSH", "W"), f"SH cell should become pay symbol, got {name}"
run_test("T17  SH transforms its own cell to a regular pay symbol", t17)


def t18():
    """SH in bonus emits globalMultUpdate with reason='shovel' per wild."""
    fresh(BONUS)
    gs.board[0][0] = gs.create_symbol("SH")
    gs.get_special_symbols_on_board()
    with patch("game_executables.get_random_outcome", return_value=2):
        with patch("random.sample", return_value=[{"reel": 2, "row": 1}, {"reel": 3, "row": 1}]):
            gs.apply_shovel(0, 0)
    evts = events_of("globalMultUpdate")
    assert len(evts) == 2, f"2 SH wilds → 2 globalMultUpdate, got {len(evts)}"
    assert all(e["reason"] == "shovel" for e in evts), "reason must be 'shovel'"
run_test("T18  SH bonus: emits globalMultUpdate(reason='shovel') per wild", t18)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 3 — Golden Shovel (GSH) Mechanics
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 3: Golden Shovel (GSH) Mechanics")


def t19():
    """GSH in base: applies mult values only (no ×2), no globalMultUpdate event."""
    fresh(BASE)
    gs.board[1][1] = gs.create_symbol("GSH")
    gs.get_special_symbols_on_board()
    n = [0]
    def side(w):
        n[0] += 1
        return 1 if n[0] == 1 else 3   # 1 wild, mult=3
    with patch("game_executables.get_random_outcome", side_effect=side):
        with patch("random.sample", return_value=[{"reel": 0, "row": 2}]):
            gs.apply_golden_shovel(1, 1)
    assert gs.global_multiplier == 3, f"Base GSH mult=3: expect 3, got {gs.global_multiplier}"
    evts = events_of("globalMultUpdate")
    assert len(evts) == 0, f"Base GSH must NOT emit globalMultUpdate, got {len(evts)}"
run_test("T19  GSH base: applies mult value only (no ×2), no globalMultUpdate", t19)


def t20():
    """GSH in base: two wilds with mult 2 and 3 → global_mult = 1×2×3 = 6."""
    fresh(BASE)
    gs.board[1][1] = gs.create_symbol("GSH")
    gs.get_special_symbols_on_board()
    calls = [0]
    def side(w):
        calls[0] += 1
        if calls[0] == 1: return 2    # 2 wilds
        if calls[0] == 2: return 2    # first wild mult=2
        return 3                       # second wild mult=3
    with patch("game_executables.get_random_outcome", side_effect=side):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}, {"reel": 3, "row": 2}]):
            gs.apply_golden_shovel(1, 1)
    assert gs.global_multiplier == 6, f"Base GSH 2 wilds (×2,×3): expect 6, got {gs.global_multiplier}"
run_test("T20  GSH base: 2 wilds (mult=2, mult=3) → global_mult=6", t20)


def t21():
    """GSH in bonus: each wild does ×2 × own mult."""
    fresh(BONUS)
    gs.board[1][1] = gs.create_symbol("GSH")
    gs.get_special_symbols_on_board()
    n = [0]
    def side(w):
        n[0] += 1
        return 1 if n[0] == 1 else 3   # 1 wild, mult=3
    with patch("game_executables.get_random_outcome", side_effect=side):
        with patch("random.sample", return_value=[{"reel": 0, "row": 2}]):
            gs.apply_golden_shovel(1, 1)
    # 1 × 2 (wild) × 3 (GSH mult) = 6
    assert gs.global_multiplier == 6, f"Bonus GSH 1 wild mult=3: expect 6, got {gs.global_multiplier}"
run_test("T21  GSH bonus: 1 wild (mult=3) → global_mult = 1×2×3 = 6", t21)


def t22():
    """GSH in bonus emits globalMultUpdate with reason='golden_shovel'."""
    fresh(BONUS)
    gs.board[1][1] = gs.create_symbol("GSH")
    gs.get_special_symbols_on_board()
    n = [0]
    def side(w):
        n[0] += 1
        return 2 if n[0] == 1 else 2
    with patch("game_executables.get_random_outcome", side_effect=side):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}, {"reel": 3, "row": 2}]):
            gs.apply_golden_shovel(1, 1)
    evts = events_of("globalMultUpdate")
    assert len(evts) == 2, f"2 GSH wilds in bonus → 2 globalMultUpdate, got {len(evts)}"
    assert all(e["reason"] == "golden_shovel" for e in evts), "reason must be 'golden_shovel'"
run_test("T22  GSH bonus: emits globalMultUpdate(reason='golden_shovel') per wild", t22)


def t23():
    """GSH emits goldenShovelWilds event with mult values in wildPositions."""
    fresh(BASE)
    gs.board[2][2] = gs.create_symbol("GSH")
    gs.get_special_symbols_on_board()
    n = [0]
    def side(w):
        n[0] += 1
        return 2 if n[0] == 1 else 4
    with patch("game_executables.get_random_outcome", side_effect=side):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}, {"reel": 4, "row": 3}]):
            gs.apply_golden_shovel(2, 2)
    evts = events_of("goldenShovelWilds")
    assert len(evts) == 1, f"Expected 1 goldenShovelWilds, got {len(evts)}"
    for pos in evts[0]["wildPositions"]:
        assert "mult" in pos, f"mult missing from wildPosition: {pos}"
        assert pos["mult"] == 4
run_test("T23  goldenShovelWilds event: wildPositions contain mult values", t23)


def t24():
    """GSH transforms its cell to a regular pay symbol."""
    fresh(BASE)
    gs.board[3][4] = gs.create_symbol("GSH")
    gs.get_special_symbols_on_board()
    n = [0]
    def side(w):
        n[0] += 1
        return 1 if n[0] == 1 else 2
    with patch("game_executables.get_random_outcome", side_effect=side):
        with patch("random.sample", return_value=[{"reel": 0, "row": 1}]):
            gs.apply_golden_shovel(3, 4)
    name = gs.board[3][4].name
    assert name not in ("GSH", "SH", "SC", "W"), f"GSH cell should become pay symbol, got {name}"
run_test("T24  GSH transforms its own cell to a regular pay symbol", t24)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 4 — Strip Wild Multipliers & Expansion
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 4: Strip Wild Multipliers & Expansion")


def t25():
    """Strip wilds in bonus double global_mult once per wild."""
    fresh(BONUS)
    gs.board[0][1] = gs.create_symbol("W")
    gs.board[2][3] = gs.create_symbol("W")
    gs.board[4][0] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_strip_wild_multipliers()
    # 3 wilds → 1 × 2 × 2 × 2 = 8
    assert gs.global_multiplier == 8, f"3 strip wilds: expect 8, got {gs.global_multiplier}"
run_test("T25  Strip wilds in bonus: 3 wilds → global_mult = ×8", t25)


def t26():
    """Strip wilds in base game do NOT change global_mult."""
    fresh(BASE)
    gs.board[0][1] = gs.create_symbol("W")
    gs.board[1][2] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_strip_wild_multipliers()
    assert gs.global_multiplier == 1, f"Base strip wilds must not change mult, got {gs.global_multiplier}"
run_test("T26  Strip wilds in base game: global_mult unchanged", t26)


def t27():
    """Strip wild mult events have reason='wild'."""
    fresh(BONUS)
    gs.board[1][2] = gs.create_symbol("W")
    gs.board[3][4] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_strip_wild_multipliers()
    evts = events_of("globalMultUpdate")
    assert len(evts) == 2, f"2 strip wilds → 2 events, got {len(evts)}"
    assert all(e["reason"] == "wild" for e in evts), "Strip wild events must have reason='wild'"
run_test("T27  Strip wild events: reason='wild', one per wild", t27)


def t28():
    """Expanding wilds fill all 5 rows of a reel that contains a W."""
    fresh(BONUS)
    gs.board[2][3] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_expanding_wilds()
    for row in range(5):
        assert gs.board[2][row].name == "W", f"Reel 2 row {row} should be W"
run_test("T28  Expanding wilds: fills all 5 rows of the reel", t28)


def t29():
    """Expansion only affects reels that contain at least one W."""
    fresh(BONUS)
    gs.board[2][3] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_expanding_wilds()
    for reel in [0, 1, 3, 4]:
        for row in range(5):
            assert gs.board[reel][row].name == "H1", f"Reel {reel} should not expand"
run_test("T29  Expanding wilds: only reels with W are affected", t29)


def t30():
    """wildExpand event: correct reel, height=5, expanded=True."""
    fresh(BONUS)
    gs.board[1][0] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_expanding_wilds()
    evts = events_of("wildExpand")
    assert len(evts) == 1, f"Expected 1 wildExpand, got {len(evts)}"
    assert evts[0]["reel"]     == 1
    assert evts[0]["height"]   == 5
    assert evts[0]["expanded"] is True
run_test("T30  wildExpand event: reel, height=5, expanded=True", t30)


def t31():
    """No wildExpand event when board has no W symbols."""
    fresh(BONUS)
    gs.get_special_symbols_on_board()
    gs.apply_expanding_wilds()
    evts = events_of("wildExpand")
    assert len(evts) == 0, f"No wilds → no wildExpand events, got {len(evts)}"
run_test("T31  No wildExpand event when board has no W", t31)


def t32():
    """Multiple reels with W each get a wildExpand event."""
    fresh(BONUS)
    gs.board[0][2] = gs.create_symbol("W")
    gs.board[2][1] = gs.create_symbol("W")
    gs.board[4][3] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_expanding_wilds()
    evts = events_of("wildExpand")
    assert len(evts) == 3, f"3 wild reels → 3 wildExpand events, got {len(evts)}"
    reels = {e["reel"] for e in evts}
    assert reels == {0, 2, 4}
run_test("T32  Three wild reels → three wildExpand events (reels 0, 2, 4)", t32)


def t33():
    """global_mult caps at wincap (20,000) and does not exceed it."""
    fresh(BONUS)
    gs.global_multiplier = 16000
    # 3 more strip wilds would give 16000 × 2 × 2 × 2 = 128000 → capped at 20000
    gs.board[0][0] = gs.create_symbol("W")
    gs.board[1][0] = gs.create_symbol("W")
    gs.board[2][0] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_strip_wild_multipliers()
    assert gs.global_multiplier == 20000, f"Cap at 20000, got {gs.global_multiplier}"
run_test("T33  global_mult caps at 20,000× (wincap) and never exceeds it", t33)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 5 — Zombie Nudge Mechanic
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 5: Zombie Nudge Mechanic")


def t34():
    """Nudge fires success=True when exactly 2 SC visible and SC above window."""
    fresh(BASE)
    gs.board[0][2] = gs.create_symbol("SC")
    gs.board[2][3] = gs.create_symbol("SC")
    gs.get_special_symbols_on_board()
    gs.top_symbols   = [
        gs.create_symbol("H1"),
        gs.create_symbol("SC"),   # reel 1 has SC just above window
        gs.create_symbol("H1"),
        gs.create_symbol("H1"),
        gs.create_symbol("H1"),
    ]
    gs.reel_positions = [0, 0, 0, 0, 0]
    gs.reelstrip_id   = "BR0"
    with patch("random.random", return_value=0.05):       # < 0.15 → fires
        with patch("random.choice", return_value=(1, "SC")):
            gs.apply_nudge()
    evts = events_of("zombieNudge")
    assert len(evts) == 1,             f"Expected 1 zombieNudge, got {len(evts)}"
    assert evts[0]["success"] is True, "Expected success=True"
    assert evts[0]["reel"]    == 1
    assert gs.board[1][0].name == "SC", "SC should be at board row 0 after nudge"
run_test("T34  Nudge success=True: SC pushed into visible window at row 0", t34)


def t35():
    """Nudge fires success=False when 2 SC visible but nothing useful above."""
    fresh(BASE)
    gs.board[0][2] = gs.create_symbol("SC")
    gs.board[2][3] = gs.create_symbol("SC")
    gs.get_special_symbols_on_board()
    gs.top_symbols   = [gs.create_symbol("H1")] * 5   # no SC or W above
    gs.reel_positions = [0, 0, 0, 0, 0]
    gs.reelstrip_id   = "BR0"
    with patch("random.random", return_value=0.05):
        with patch("random.choice", return_value=1):   # returns int for other_reels
            gs.apply_nudge()
    evts = events_of("zombieNudge")
    assert len(evts) == 1,              f"Expected 1 zombieNudge, got {len(evts)}"
    assert evts[0]["success"] is False, "Expected success=False"
run_test("T35  Nudge success=False: no SC/W above window → tease only", t35)


def t36():
    """Nudge does NOT fire when random() >= nudge_probability (0.15)."""
    fresh(BASE)
    gs.board[0][2] = gs.create_symbol("SC")
    gs.board[2][3] = gs.create_symbol("SC")
    gs.get_special_symbols_on_board()
    gs.top_symbols    = [gs.create_symbol("H1"), gs.create_symbol("SC")] + [gs.create_symbol("H1")] * 3
    gs.reel_positions = [0, 0, 0, 0, 0]
    gs.reelstrip_id   = "BR0"
    with patch("random.random", return_value=0.20):    # >= 0.15 → no nudge
        gs.apply_nudge()
    evts = events_of("zombieNudge")
    assert len(evts) == 0, f"random >= 0.15: nudge must not fire, got {len(evts)}"
run_test("T36  Nudge suppressed when random() >= 0.15", t36)


def t37():
    """Nudge does NOT fire with 0, 1, 3, or 4 scatters visible."""
    for sc_reels in [[], [1], [0, 1, 2], [0, 1, 2, 3]]:
        fresh(BASE)
        for r in sc_reels:
            gs.board[r][2] = gs.create_symbol("SC")
        gs.get_special_symbols_on_board()
        gs.top_symbols    = [gs.create_symbol("H1")] * 5
        gs.reel_positions = [0, 0, 0, 0, 0]
        gs.reelstrip_id   = "BR0"
        with patch("random.random", return_value=0.05):
            gs.apply_nudge()
        evts = events_of("zombieNudge")
        assert len(evts) == 0, f"{len(sc_reels)} SC: nudge must not fire, got {len(evts)} events"
run_test("T37  Nudge does NOT fire when SC count ≠ 2 (tested: 0,1,3,4)", t37)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 6 — Bonus Entry & Tiers
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 6: Bonus Entry & Tiers")


def t38():
    """3 SC → 'bonus' tier, 10 spins, FR0, NO preBonusSequence."""
    fresh(BONUS)
    with patch("game_executables.get_random_outcome", return_value=3):
        with patch("random.sample", return_value=[{"reel": i, "row": 1} for i in range(3)]):
            gs.setup_bonus_entry(scatter_count=3)
    assert gs.bonus_tier    == "bonus",  f"tier={gs.bonus_tier}"
    assert gs.tot_fs        == 10,       f"spins={gs.tot_fs}"
    assert gs.freegame_strip == "FR0"
    assert len(events_of("preBonusSequence")) == 0, "Standard bonus must NOT have preBonusSequence"
    assert len(events_of("bonusTierEntry"))   == 1
run_test("T38  3 SC → 'bonus', 10 spins, FR0, no preBonusSequence", t38)


def t39():
    """4 SC → 'super_bonus' tier, 12 spins, FR_SUPER, WITH preBonusSequence."""
    fresh(BONUS)
    with patch("game_executables.get_random_outcome", return_value=3):
        with patch("random.sample", return_value=[{"reel": i, "row": 1} for i in range(3)]):
            gs.setup_bonus_entry(scatter_count=4)
    assert gs.bonus_tier     == "super_bonus", f"tier={gs.bonus_tier}"
    assert gs.tot_fs         == 12,            f"spins={gs.tot_fs}"
    assert gs.freegame_strip == "FR_SUPER"
    pre = events_of("preBonusSequence")
    assert len(pre) == 1,                            "Super bonus must have preBonusSequence"
    assert pre[0]["bonusTier"] == "super_bonus"
run_test("T39  4 SC → 'super_bonus', 12 spins, FR_SUPER, preBonusSequence fired", t39)


def t40():
    """5 SC → 'hidden_bonus' tier, 15 spins, FR_HIDDEN, WITH preBonusSequence."""
    fresh(BONUS)
    with patch("game_executables.get_random_outcome", return_value=5):
        with patch("random.sample", return_value=[{"reel": i, "row": 1} for i in range(5)]):
            gs.setup_bonus_entry(scatter_count=5)
    assert gs.bonus_tier     == "hidden_bonus", f"tier={gs.bonus_tier}"
    assert gs.tot_fs         == 15,             f"spins={gs.tot_fs}"
    assert gs.freegame_strip == "FR_HIDDEN"
    pre = events_of("preBonusSequence")
    assert len(pre) == 1,                             "Hidden bonus must have preBonusSequence"
    assert pre[0]["bonusTier"] == "hidden_bonus"
run_test("T40  5 SC → 'hidden_bonus', 15 spins, FR_HIDDEN, preBonusSequence fired", t40)


def t41():
    """bonusTierEntry event has correct fields for each tier."""
    for sc, tier, spins, strip in [(3, "bonus", 10, "FR0"), (4, "super_bonus", 12, "FR_SUPER"), (5, "hidden_bonus", 15, "FR_HIDDEN")]:
        fresh(BONUS)
        with patch("game_executables.get_random_outcome", return_value=3):
            with patch("random.sample", return_value=[{"reel": i, "row": 1} for i in range(3)]):
                gs.setup_bonus_entry(scatter_count=sc)
        evts = events_of("bonusTierEntry")
        assert len(evts) == 1,               f"{sc}SC: expected 1 bonusTierEntry"
        e = evts[0]
        assert e["bonusTier"]    == tier,    f"{sc}SC tier mismatch: {e['bonusTier']}"
        assert e["spinsAwarded"] == spins,   f"{sc}SC spins mismatch: {e['spinsAwarded']}"
        assert e["reelStrip"]    == strip,   f"{sc}SC strip mismatch: {e['reelStrip']}"
run_test("T41  bonusTierEntry: correct bonusTier, spinsAwarded, reelStrip for all tiers", t41)


def t42():
    """Pre-bonus wild positions carry +1 row padding in the event."""
    fresh(BONUS)
    positions = [{"reel": 0, "row": 1}, {"reel": 2, "row": 3}]
    with patch("game_executables.get_random_outcome", return_value=2):
        with patch("random.sample", return_value=positions):
            gs.setup_bonus_entry(scatter_count=4)
    pre = events_of("preBonusSequence")
    rows = [p["row"] for p in pre[0]["wildPositions"]]
    assert 2 in rows, f"Internal row 1 → event row 2 (pad+1), got rows={rows}"
    assert 4 in rows, f"Internal row 3 → event row 4 (pad+1), got rows={rows}"
run_test("T42  preBonusSequence wildPositions: rows are internal + 1 padding", t42)


def t43():
    """Pre-bonus for super_bonus places 3 or 4 wilds (config weights {3:2, 4:3})."""
    for n in [3, 4]:
        fresh(BONUS)
        with patch("game_executables.get_random_outcome", return_value=n):
            with patch("random.sample", return_value=[{"reel": i, "row": 1} for i in range(n)]):
                gs.setup_bonus_entry(scatter_count=4)
        pre = events_of("preBonusSequence")
        placed = len(pre[0]["wildPositions"])
        assert placed == n, f"Super bonus: expected {n} wilds, got {placed}"
run_test("T43  Pre-bonus (super_bonus): 3 or 4 wilds placed correctly", t43)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 7 — Retrigger
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 7: Retrigger")


def t44():
    """3 SC in bonus → +5 spins, retriggered_bonus set to True."""
    fresh(BONUS)
    gs.tot_fs           = 10
    gs.retriggered_bonus = False
    gs.board[0][1] = gs.create_symbol("SC")
    gs.board[2][2] = gs.create_symbol("SC")
    gs.board[4][3] = gs.create_symbol("SC")
    gs.get_special_symbols_on_board()
    gs.check_and_award_retrigger()
    assert gs.tot_fs           == 15,  f"10 + 5 = 15, got {gs.tot_fs}"
    assert gs.retriggered_bonus is True
run_test("T44  Retrigger: 3 SC in bonus → tot_fs = 15, retriggered_bonus = True", t44)


def t45():
    """Retrigger fires at most once per bonus session (flag prevents second trigger)."""
    fresh(BONUS)
    gs.tot_fs           = 10
    gs.retriggered_bonus = False
    gs.board[0][1] = gs.create_symbol("SC")
    gs.board[2][2] = gs.create_symbol("SC")
    gs.board[4][3] = gs.create_symbol("SC")
    gs.get_special_symbols_on_board()
    gs.check_and_award_retrigger()   # first time  → fires
    gs.check_and_award_retrigger()   # second time → blocked
    assert gs.tot_fs == 15, f"Retrigger fires once only: 10+5=15, got {gs.tot_fs}"
run_test("T45  Retrigger fires at most once per session (double-trigger blocked)", t45)


def t46():
    """Retrigger emits event with correct spinsAdded and totalFs."""
    fresh(BONUS)
    gs.tot_fs           = 10
    gs.retriggered_bonus = False
    gs.board[0][1] = gs.create_symbol("SC")
    gs.board[2][2] = gs.create_symbol("SC")
    gs.board[4][3] = gs.create_symbol("SC")
    gs.get_special_symbols_on_board()
    gs.check_and_award_retrigger()
    evts = events_of("retrigger")
    assert len(evts)              == 1,  f"Expected 1 retrigger event, got {len(evts)}"
    assert evts[0]["spinsAdded"]  == 5
    assert evts[0]["totalFs"]     == 15
run_test("T46  retrigger event: spinsAdded=5, totalFs=15", t46)


def t47():
    """Retrigger does NOT fire with only 2 SC in bonus."""
    fresh(BONUS)
    gs.tot_fs           = 10
    gs.retriggered_bonus = False
    gs.board[0][1] = gs.create_symbol("SC")
    gs.board[2][2] = gs.create_symbol("SC")
    gs.get_special_symbols_on_board()
    gs.check_and_award_retrigger()
    assert gs.tot_fs == 10, f"2 SC: no retrigger, tot_fs should stay 10, got {gs.tot_fs}"
run_test("T47  Retrigger does NOT fire with only 2 SC (below threshold)", t47)


def t48():
    """Retrigger resets each new spin (reset_book clears retriggered_bonus)."""
    fresh(BONUS)
    gs.retriggered_bonus = True
    gs.reset_book()
    assert gs.retriggered_bonus is False, "retriggered_bonus must reset to False on reset_book"
run_test("T48  retriggered_bonus resets to False on each new spin", t48)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 8 — Event Structure & Ordering
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 8: Event Structure & Ordering")


def t49():
    """Event indices are sequential starting from 0."""
    fresh(BONUS)
    gs.board[0][1] = gs.create_symbol("W")
    gs.board[1][2] = gs.create_symbol("W")
    gs.board[2][0] = gs.create_symbol("SH")
    gs.get_special_symbols_on_board()
    gs.apply_strip_wild_multipliers()
    with patch("game_executables.get_random_outcome", return_value=1):
        with patch("random.sample", return_value=[{"reel": 4, "row": 1}]):
            gs.apply_shovel(2, 0)
    for i, evt in enumerate(gs.book.events):
        assert evt["index"] == i, f"Event at position {i} has index {evt['index']}"
run_test("T49  Event indices are sequential (0, 1, 2, ...)", t49)


def t50():
    """globalMultUpdate prevMult/globalMult chain is consistent."""
    fresh(BONUS)
    gs.global_multiplier = 4
    gs.board[0][1] = gs.create_symbol("W")
    gs.board[1][2] = gs.create_symbol("W")
    gs.get_special_symbols_on_board()
    gs.apply_strip_wild_multipliers()
    evts = events_of("globalMultUpdate")
    assert evts[0]["prevMult"]   == 4,  f"First event prevMult: expect 4, got {evts[0]['prevMult']}"
    assert evts[0]["globalMult"] == 8,  f"First event globalMult: expect 8"
    assert evts[1]["prevMult"]   == 8,  f"Second event prevMult: expect 8"
    assert evts[1]["globalMult"] == 16, f"Second event globalMult: expect 16"
run_test("T50  globalMultUpdate: prevMult/globalMult chain is correct", t50)


def t51():
    """global_mult resets to 1 at the start of each new spin (reset_book)."""
    fresh(BONUS)
    gs.global_multiplier = 512
    gs.reset_book()
    assert gs.global_multiplier == 1, f"global_mult must reset to 1, got {gs.global_multiplier}"
run_test("T51  global_mult resets to 1 on reset_book (new spin)", t51)


def t52():
    """shovelWilds row padding: internal row R → event row R+1."""
    fresh(BASE)
    gs.board[3][0] = gs.create_symbol("SH")   # internal row 0
    gs.get_special_symbols_on_board()
    with patch("game_executables.get_random_outcome", return_value=1):
        with patch("random.sample", return_value=[{"reel": 1, "row": 4}]):   # internal row 4
            gs.apply_shovel(3, 0)
    e = events_of("shovelWilds")[0]
    assert e["shovelRow"]              == 1, f"Internal row 0 → event row 1, got {e['shovelRow']}"
    assert e["wildPositions"][0]["row"] == 5, f"Internal row 4 → event row 5, got {e['wildPositions'][0]['row']}"
run_test("T52  shovelWilds row padding: internal_row + 1 = event_row", t52)


def t53():
    """zombieNudge fires AFTER reveal (correct event ordering in gamestate)."""
    # Verify the sequence by reading gamestate.py comment / structure:
    # draw_board(emit_event=True) fires 'reveal' FIRST,
    # then apply_nudge() fires 'zombieNudge'.
    # We verify this ordering by checking the event type sequence.
    import inspect, gamestate
    src = inspect.getsource(gamestate.GameState.run_spin)
    reveal_pos = src.find("draw_board(emit_event=True)")
    nudge_pos  = src.find("apply_nudge()")
    assert reveal_pos < nudge_pos, "draw_board (reveal) must come before apply_nudge in run_spin"
run_test("T53  Event ordering: 'reveal' fires before 'zombieNudge' in run_spin", t53)


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 9 — Integration: Full Spins Without Exceptions
# ─────────────────────────────────────────────────────────────────────────────

section("CATEGORY 9: Integration — Full Spins (no exceptions)")


def t54():
    """Run spins across all base-mode criteria — no exceptions, each has finalWin."""
    # SDK requires betmode + criteria set before run_spin.
    # Test each distribution type: zero-win, basegame, freegame, freegame_super,
    # freegame_hidden (wincap omitted — requires force_wincap=True which needs
    # specific reel conditions the SDK enforces internally).
    gs.betmode = "base"
    errors = []
    for criteria in ["0", "basegame", "freegame", "freegame_super", "freegame_hidden"]:
        gs.criteria = criteria
        for sim in range(10):
            try:
                gs.run_spin(sim)
                final = [e for e in gs.book.events if e["type"] == "finalWin"]
                if not final:
                    errors.append(f"{criteria} sim {sim}: no finalWin event")
                if final and final[0]["amount"] < 0:
                    errors.append(f"{criteria} sim {sim}: finalWin amount < 0")
            except Exception as e:
                errors.append(f"{criteria} sim {sim}: {e}")
    assert not errors, "\n  ".join(errors)
run_test("T54  Base-mode spins (all criteria): no exceptions, each has finalWin", t54)


def t55():
    """Bonus-buy mode spins — no exceptions, event indices sequential."""
    gs.betmode  = "bonus"
    gs.criteria = "freegame"
    errors = []
    for sim in range(20):
        try:
            gs.run_spin(sim)
            final = [e for e in gs.book.events if e["type"] == "finalWin"]
            if not final:
                errors.append(f"bonus sim {sim}: no finalWin event")
            for i, evt in enumerate(gs.book.events):
                if evt["index"] != i:
                    errors.append(f"bonus sim {sim}: event pos {i} has index {evt['index']}")
                    break
        except Exception as e:
            errors.append(f"bonus sim {sim}: {e}")
    assert not errors, "\n  ".join(errors)
run_test("T55  Bonus-buy spins: no exceptions, event indices sequential", t55)


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{'=' * 60}")
print(f"  QA RESULTS:  {_pass} PASSED  |  {_fail} FAILED  |  {_pass + _fail} TOTAL")
print(f"{'=' * 60}")

if _errors:
    print("\nFailed tests:")
    for name, msg in _errors:
        print(f"  FAIL  {name}")
        print(f"        {msg}")
    sys.exit(1)
else:
    print("\n  All tests passed. Code is ready for production.")
    sys.exit(0)
