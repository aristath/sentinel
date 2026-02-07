from sentinel.strategy.contrarian import (
    classify_lot_size,
    compute_contrarian_signal,
    compute_symbol_targets,
    effective_opportunity_score,
    recent_dd252_min,
)


def test_compute_contrarian_signal_detects_dip_and_turn():
    closes = [100.0] * 130 + [95.0, 90.0, 88.0, 87.0, 86.0, 87.0, 88.0, 89.0, 90.0, 91.0]
    signal = compute_contrarian_signal(closes)
    assert signal["dip_score"] >= 0.0
    assert 0.0 <= signal["opp_score"] <= 1.0
    assert signal["cycle_turn"] in (0, 1)
    assert signal["dd252_recent_min"] <= signal["dd252"]


def test_compute_contrarian_signal_blocks_freefall():
    closes = [200.0]
    for i in range(1, 180):
        step = 3.5 if i > 130 else 0.4
        closes.append(max(1.0, closes[-1] - step))
    signal = compute_contrarian_signal(closes)
    assert signal["freefall_block"] == 1
    assert signal["opp_score"] == 0.0


def test_classify_lot_size_coarse_for_small_portfolio():
    profile = classify_lot_size(
        price=50.0,
        lot_size=100,
        fx_rate_to_eur=1.0,
        portfolio_value_eur=20_000.0,
        fee_fixed_eur=2.0,
        fee_pct=0.002,
        standard_max_pct=0.08,
        coarse_max_pct=0.30,
    )
    assert profile["lot_class"] == "coarse"
    assert float(profile["ticket_pct"]) > 0.08


def test_compute_symbol_targets_fully_invested():
    signals = {
        "AAA": {"core_rank": 0.2, "opp_score": 0.8, "vol20": 0.02},
        "BBB": {"core_rank": 0.1, "opp_score": 0.1, "vol20": 0.03},
    }
    allocations, sleeves = compute_symbol_targets(
        signals,
        {"AAA": 1.0, "BBB": 1.0},
        core_target=0.7,
        opportunity_target=0.3,
        min_opp_score=0.55,
    )
    assert abs(sum(allocations.values()) - 1.0) < 1e-8
    assert sleeves["AAA"] == "opportunity"
    assert sleeves["BBB"] == "core"


def test_compute_symbol_targets_can_boost_opportunity_sleeve_when_breadth_is_broad_and_strong():
    signals = {
        "A": {"core_rank": 0.2, "opp_score": 0.9, "vol20": 0.02},
        "B": {"core_rank": 0.1, "opp_score": 0.85, "vol20": 0.02},
        "C": {"core_rank": 0.15, "opp_score": 0.82, "vol20": 0.02},
        "D": {"core_rank": 0.05, "opp_score": 0.80, "vol20": 0.03},
        "E": {"core_rank": 0.08, "opp_score": 0.78, "vol20": 0.03},
        "F": {"core_rank": 0.10, "opp_score": 0.76, "vol20": 0.03},
        "G": {"core_rank": 0.05, "opp_score": 0.74, "vol20": 0.03},
        "H": {"core_rank": 0.04, "opp_score": 0.72, "vol20": 0.03},
    }
    allocations, sleeves = compute_symbol_targets(
        signals,
        {k: 1.0 for k in signals},
        core_target=0.7,
        opportunity_target=0.3,
        min_opp_score=0.55,
        max_opportunity_target=0.45,
    )
    assert abs(sum(allocations.values()) - 1.0) < 1e-8
    opp_alloc = sum(allocations[s] for s, sleeve in sleeves.items() if sleeve == "opportunity")
    assert opp_alloc > 0.30


def test_effective_opportunity_score_boosts_on_recent_dip_turn_without_freefall():
    boosted = effective_opportunity_score(
        raw_opp_score=0.42,
        cycle_turn=1,
        freefall_block=0,
        recent_dd252_min_value=-0.22,
        entry_t1_dd=-0.10,
        entry_t3_dd=-0.22,
        max_boost=0.18,
    )
    assert boosted > 0.42


def test_effective_opportunity_score_does_not_boost_in_freefall():
    boosted = effective_opportunity_score(
        raw_opp_score=0.42,
        cycle_turn=1,
        freefall_block=1,
        recent_dd252_min_value=-0.25,
        entry_t1_dd=-0.10,
        entry_t3_dd=-0.22,
        max_boost=0.18,
    )
    assert boosted == 0.42


def test_recent_dd252_min_tracks_recent_window_dips():
    closes = [100.0] * 260 + [94.0, 90.0, 92.0, 95.0, 98.0, 100.0]
    recent = recent_dd252_min(closes, window_days=42)
    assert recent <= -0.099
