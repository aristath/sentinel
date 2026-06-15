"""Tests for rebalance_rules.py — pure function helpers."""

from datetime import datetime, timezone

from sentinel.planner.rebalance_rules import (
    calculate_priority,
    calculate_transaction_cost,
    generate_buy_reason,
    generate_sell_reason,
    get_forced_opportunity_exit,
)


class TestCalculatePriority:
    """Tests for calculate_priority function."""

    def test_buy_priority_multiplies_eur_gap_by_contrarian_weight(self):
        result = calculate_priority("buy", value_delta_eur=1000.0, contrarian_score=1.0, contrarian_weight_pct=25.0)
        expected = 1250.0
        assert result == expected

    def test_sell_priority_reduces_for_high_contrarian_score(self):
        result = calculate_priority("sell", value_delta_eur=-1000.0, contrarian_score=1.0, contrarian_weight_pct=25.0)
        expected = 750.0
        assert result == expected

    def test_buy_higher_priority_with_higher_score_for_same_eur_gap(self):
        r1 = calculate_priority("buy", 1000.0, 0.3)
        r2 = calculate_priority("buy", 1000.0, 0.8)
        assert r2 > r1

    def test_sell_lower_priority_with_higher_score(self):
        r1 = calculate_priority("sell", -1000.0, 0.3)
        r2 = calculate_priority("sell", -1000.0, 0.8)
        assert r1 > r2  # lower score = higher priority for sells

    def test_neutral_score_leaves_eur_gap_unchanged(self):
        result = calculate_priority("buy", 1000.0, 0.5)
        assert result == 1000.0

    def test_zero_weight_uses_plain_eur_gap(self):
        result = calculate_priority("buy", 1000.0, 0.0, contrarian_weight_pct=0.0)
        assert result == 1000.0


class TestCalculateTransactionCost:
    """Tests for calculate_transaction_cost function."""

    def test_base_case(self):
        assert calculate_transaction_cost(1000.0, 2.0, 0.002) == 4.0

    def test_only_fixed_fee(self):
        assert calculate_transaction_cost(1000.0, 2.0, 0.0) == 2.0

    def test_only_percentage_fee(self):
        assert calculate_transaction_cost(1000.0, 0.0, 0.002) == 2.0

    def test_zero_value(self):
        assert calculate_transaction_cost(0.0, 2.0, 0.002) == 2.0

    def test_large_value(self):
        result = calculate_transaction_cost(100000.0, 2.0, 0.002)
        assert result == 202.0  # 2.0 + 100000 * 0.002

    def test_half_percent_fee(self):
        result = calculate_transaction_cost(500.0, 1.0, 0.005)
        assert result == 3.5


class TestGenerateSellReason:
    """Tests for generate_sell_reason function."""

    def test_exit_not_in_target_portfolio(self):
        signal = {"sleeve": "core"}
        reason = generate_sell_reason(
            symbol="EXIT.EU",
            contrarian_score=0.5,
            current_alloc=0.10,
            target_alloc=0.0,
            signal=signal,
        )
        assert "not in target portfolio" in reason

    def test_exit_weak_contrarian_score(self):
        signal = {"sleeve": "opportunity"}
        reason = generate_sell_reason(
            symbol="WEAK.EU",
            contrarian_score=-0.5,
            current_alloc=0.10,
            target_alloc=0.0,
            signal=signal,
        )
        assert "weak contrarian score" in reason

    def test_overweight_reduce_to_target(self):
        signal = {"sleeve": "core"}
        reason = generate_sell_reason(
            symbol="OVER.EU",
            contrarian_score=0.5,
            current_alloc=0.15,
            target_alloc=0.08,
            signal=signal,
        )
        assert "Overweight by 7.0%" in reason
        assert "Reduce to target allocation" in reason

    def test_overweight_opportunity_sleeve(self):
        signal = {"sleeve": "opportunity"}
        reason = generate_sell_reason(
            symbol="OVER.OPP",
            contrarian_score=0.5,
            current_alloc=0.12,
            target_alloc=0.05,
            signal=signal,
        )
        assert "Overweight by 7.0%" in reason
        assert "opportunity sleeve" in reason


class TestGenerateBuyReason:
    """Tests for generate_buy_reason function."""

    def test_strategic_preference_buy(self):
        signal = {
            "clara_target_pct": 0.05,
            "user_multiplier": 0.8,
        }
        reason = generate_buy_reason(
            symbol="STRAT.EU",
            contrarian_score=0.5,
            current_alloc=0.02,
            target_alloc=0.07,
            signal=signal,
            lot_class="standard",
        )
        assert "Strategic preference buy" in reason
        assert "Clara target=5.0%" in reason

    def test_new_contrarian_entry(self):
        signal = {
            "dip_score": -0.15,
            "capitulation_score": -0.25,
            "cycle_turn": 1,
        }
        reason = generate_buy_reason(
            symbol="NEW.EU",
            contrarian_score=0.6,
            current_alloc=0.0,
            target_alloc=0.05,
            signal=signal,
            lot_class="coarse",
        )
        assert "New contrarian entry" in reason
        assert "coarse lot" in reason

    def test_underweight_regular_buy(self):
        signal = {
            "dip_score": -0.10,
            "capitulation_score": 0.0,
            "cycle_turn": 0,
        }
        reason = generate_buy_reason(
            symbol="UNDER.EU",
            contrarian_score=0.4,
            current_alloc=0.03,
            target_alloc=0.08,
            signal=signal,
            lot_class="standard",
        )
        assert "Underweight by 5.0%" in reason
        assert "Contrarian score=0.40" in reason


class TestForcedOpportunityExit:
    """Tests for get_forced_opportunity_exit function edge cases."""

    def test_zero_quantity_returns_none(self):
        signal = {"lot_size": 1}
        state = {}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=0,
            price=100.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_negative_quantity_returns_none(self):
        signal = {"lot_size": 1}
        state = {}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=-5,
            price=100.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_zero_entry_price_returns_none(self):
        signal = {"lot_size": 1}
        state = {}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=10,
            price=100.0,
            avg_cost=0.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_zero_price_returns_none(self):
        signal = {"lot_size": 1}
        state = {"last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=10,
            price=0.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_scaleout_t1_triggered(self):
        """+10% gain with scaleout_stage < 1 triggers 30% sell."""
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 0, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=110.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        assert result["reason_code"] == "scaleout_10"
        assert result["quantity"] == 30  # 30% of 100, rounded to lot_size

    def test_scaleout_t2_triggered(self):
        """+18% gain with scaleout_stage < 1 triggers T1 (checked first), not T2."""
        # Note: T1 is checked before T2 in the code, so +18% triggers T1 first
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 0, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=118.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        assert result["reason_code"] == "scaleout_10"  # T1 checked first

    def test_scaleout_t2_triggered_when_t1_already_done(self):
        """+18% gain with scaleout_stage >= 1 (T1 done) triggers T2."""
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 1, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=118.01,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        assert result["reason_code"] == "scaleout_18"

    def test_scaleout_t1_not_triggered_below_10pct(self):
        """+9% gain does not trigger scaleout T1."""
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 0, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=109.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_momentum_rollover_exit(self):
        """scaleout_stage >= 1, gain > 0, mom20 < mom60 triggers full exit."""
        signal = {"mom20": -0.02, "mom60": 0.01, "lot_size": 1}
        state = {"scaleout_stage": 1, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=112.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        assert result["reason_code"] == "exit_momentum"
        assert result["quantity"] == 100  # full exit

    def test_momentum_rollover_not_triggered_when_mom20_gt_mom60(self):
        signal = {"mom20": 0.02, "mom60": 0.01, "lot_size": 1}
        state = {"scaleout_stage": 1, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=112.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_time_stop_rotation_triggered(self):
        """Entry > 90 days ago, gain < 10% triggers time-stop."""
        signal = {"lot_size": 1}
        past_ts = datetime.now(timezone.utc).timestamp() - 91 * 86400
        state = {"scaleout_stage": 0, "last_entry_ts": past_ts, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=105.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        assert result["reason_code"] == "time_stop_rotation"
        assert result["quantity"] == 100

    def test_time_stop_not_triggered_when_gain_above_10pct(self):
        """+10% gain triggers scaleout T1 before time-stop is checked."""
        signal = {"lot_size": 1}
        past_ts = datetime.now(timezone.utc).timestamp() - 91 * 86400
        state = {"scaleout_stage": 0, "last_entry_ts": past_ts, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=110.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        # T1 triggers first (>=10%), so time-stop is not reached
        assert result is not None
        assert result["reason_code"] == "scaleout_10"

    def test_time_stop_not_triggered_when_entry_too_recent(self):
        signal = {"lot_size": 1}
        recent_ts = datetime.now(timezone.utc).timestamp() - 80 * 86400
        state = {"scaleout_stage": 0, "last_entry_ts": recent_ts, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=105.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_no_state_entry_ts_returns_none(self):
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=105.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_as_of_date_uses_provided_date(self):
        signal = {"lot_size": 1}
        entry_date = datetime(2025, 1, 1)
        state = {"scaleout_stage": 0, "last_entry_ts": int(entry_date.timestamp()), "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(  # as_of_date is 2025-04-01 — 90 days after entry
            signal=signal,
            state=state,
            current_qty=100,
            price=105.0,
            avg_cost=100.0,
            as_of_date="2025-04-01",
            time_stop_days=90,
        )
        assert result is not None
        assert result["reason_code"] == "time_stop_rotation"

    def test_lot_size_rounding_in_scaleout(self):
        """Quantity should be rounded down to lot size multiple."""
        signal = {"lot_size": 10}
        state = {"scaleout_stage": 0, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=105,
            price=110.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        # 30% of 105 = 31.5, floor to 30, floor to 30 (lot 10)
        assert result["quantity"] == 30

    def test_lot_size_minimum_applied(self):
        """Minimum quantity is one lot size."""
        signal = {"lot_size": 50}
        state = {"scaleout_stage": 0, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=55,
            price=110.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        assert result["quantity"] == 50  # min(lot_size, calculated)

    def test_scaleout_stage_blocks_t1_when_already_done(self):
        """scaleout_stage >= 1 skips T1 check."""
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 1, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=110.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        # Should not trigger T1 (stage >= 1), but might trigger momentum
        # with default signal values (mom20=0, mom60=0, so mom20 not < mom60)
        assert result is None

    def test_scaleout_stage_blocks_t2_when_already_done(self):
        """scaleout_stage >= 2 skips T2 check."""
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 2, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=118.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_loss_no_scaleout(self):
        """Price below entry does not trigger scaleout."""
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 0, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=90.0,
            avg_cost=100.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None

    def test_entry_price_fallback_to_state_last_entry_price(self):
        """When avg_cost is 0, falls back to state.last_entry_price."""
        signal = {"lot_size": 1}
        state = {"scaleout_stage": 0, "last_entry_price": 100.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=110.0,
            avg_cost=0.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is not None
        assert result["reason_code"] == "scaleout_10"

    def test_entry_price_fallback_to_current_price(self):
        """When both avg_cost and state are empty, falls back to price."""
        signal = {"lot_size": 1}
        state = {}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=100.0,
            avg_cost=0.0,
            as_of_date=None,
            time_stop_days=90,
        )
        # price == avg_cost (fallback) => gain = 0, no scaleout
        assert result is None

    def test_no_scaleout_when_stage_1_and_gain_zero(self):
        """scaleout_stage >= 1 but gain = 0 does not trigger momentum exit."""
        signal = {"mom20": -0.02, "mom60": 0.01, "lot_size": 1}
        state = {"scaleout_stage": 1, "last_entry_price": 110.0}
        result = get_forced_opportunity_exit(
            signal=signal,
            state=state,
            current_qty=100,
            price=110.0,
            avg_cost=110.0,
            as_of_date=None,
            time_stop_days=90,
        )
        assert result is None  # gain = 0, not > 0
