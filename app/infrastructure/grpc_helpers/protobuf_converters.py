"""Protobuf conversion utilities for domain models."""

from datetime import datetime
from typing import List, Optional

from app.domain.models import Security
from app.modules.planning.domain.holistic_planner import HolisticPlan, HolisticStep
from app.modules.portfolio.domain.models import Position
from app.shared.domain.value_objects.currency import Currency
from contracts import (  # type: ignore[attr-defined]
    common_pb2,
    planning_pb2,
    position_pb2,
    security_pb2,
)

# =============================================================================
# Money Conversions
# =============================================================================


def money_to_proto(amount: float) -> common_pb2.Money:
    """
    Convert float amount to Money protobuf.

    Args:
        amount: Amount in EUR

    Returns:
        Money protobuf message
    """
    return common_pb2.Money(amount=str(amount), currency="EUR")


def proto_to_money(proto: common_pb2.Money) -> float:
    """
    Convert Money protobuf to float.

    Args:
        proto: Money protobuf message

    Returns:
        Amount as float
    """
    return float(proto.amount)


# =============================================================================
# Timestamp Conversions
# =============================================================================


def timestamp_to_proto(dt: Optional[datetime] | str | None) -> common_pb2.Timestamp:
    """
    Convert datetime or ISO string to Timestamp protobuf.

    Args:
        dt: datetime object or ISO string

    Returns:
        Timestamp protobuf message
    """
    if dt is None:
        dt = datetime.now()
    elif isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    return common_pb2.Timestamp(
        seconds=int(dt.timestamp()),
        nanos=dt.microsecond * 1000,
    )


def proto_to_timestamp(proto: common_pb2.Timestamp) -> datetime:
    """
    Convert Timestamp protobuf to datetime.

    Args:
        proto: Timestamp protobuf message

    Returns:
        datetime object
    """
    return datetime.fromtimestamp(proto.seconds + proto.nanos / 1e9)


# =============================================================================
# Position Conversions
# =============================================================================


def position_to_proto(position: Position) -> position_pb2.Position:
    """
    Convert domain Position to protobuf Position.

    Args:
        position: Domain Position

    Returns:
        Position protobuf message
    """
    return position_pb2.Position(
        symbol=position.symbol,
        isin=position.isin or "",
        name=position.symbol,  # Note: Position doesn't have name, using symbol
        quantity=position.quantity,
        average_price=money_to_proto(position.avg_price),
        current_price=money_to_proto(position.current_price or position.avg_price),
        market_value=money_to_proto(position.market_value_eur or 0.0),
        cost_basis=money_to_proto(position.cost_basis_eur or 0.0),
        unrealized_pnl=money_to_proto(position.unrealized_pnl or 0.0),
        unrealized_pnl_pct=position.unrealized_pnl_pct or 0.0,
        account_id="default",  # Position doesn't have account_id
        last_updated=timestamp_to_proto(position.last_updated),
    )


def proto_to_position(proto: position_pb2.Position) -> Position:
    """
    Convert protobuf Position to domain Position.

    Args:
        proto: Position protobuf message

    Returns:
        Domain Position
    """
    return Position(
        symbol=proto.symbol,
        quantity=proto.quantity,
        avg_price=proto_to_money(proto.average_price),
        isin=proto.isin if proto.isin else None,
        currency=Currency.EUR,
        currency_rate=1.0,
        current_price=proto_to_money(proto.current_price),
        market_value_eur=proto_to_money(proto.market_value),
        cost_basis_eur=proto_to_money(proto.cost_basis),
        unrealized_pnl=proto_to_money(proto.unrealized_pnl),
        unrealized_pnl_pct=proto.unrealized_pnl_pct,
        last_updated=proto_to_timestamp(proto.last_updated).isoformat(),
    )


# =============================================================================
# Security Conversions
# =============================================================================


def security_to_proto(security: Security) -> security_pb2.Security:
    """
    Convert domain Security to protobuf Security.

    Args:
        security: Domain Security

    Returns:
        Security protobuf message
    """
    return security_pb2.Security(
        symbol=security.symbol,
        name=security.name,
        isin=security.isin or "",
        exchange=security.fullExchangeName or "",
        product_type=security.product_type.value if security.product_type else "",
        currency=security.currency.value if security.currency else "EUR",
        active=security.active,
        allow_buy=security.allow_buy,
        allow_sell=security.allow_sell,
        priority_multiplier=security.priority_multiplier,
        min_lot=security.min_lot,
    )


def proto_to_security(proto: security_pb2.Security) -> Security:
    """
    Convert protobuf Security to domain Security.

    Args:
        proto: Security protobuf message

    Returns:
        Domain Security
    """
    from app.domain.value_objects.product_type import ProductType

    return Security(
        symbol=proto.symbol,
        name=proto.name,
        fullExchangeName=proto.exchange if proto.exchange else None,
        product_type=ProductType(proto.product_type) if proto.product_type else None,
        isin=proto.isin if proto.isin else None,
        currency=Currency(proto.currency) if proto.currency else Currency.EUR,
        active=proto.active,
        allow_buy=proto.allow_buy,
        allow_sell=proto.allow_sell,
        priority_multiplier=proto.priority_multiplier,
        min_lot=proto.min_lot,
    )


# =============================================================================
# Planning Conversions
# =============================================================================


def holistic_step_to_proto(step: HolisticStep) -> planning_pb2.PlannedAction:
    """
    Convert domain HolisticStep to protobuf PlannedAction.

    Args:
        step: Domain HolisticStep

    Returns:
        PlannedAction protobuf message
    """
    # Map side string to protobuf TradeSide
    side_map = {
        "BUY": common_pb2.TRADE_SIDE_BUY,
        "SELL": common_pb2.TRADE_SIDE_SELL,
    }

    return planning_pb2.PlannedAction(
        side=side_map.get(step.side, common_pb2.TRADE_SIDE_UNSPECIFIED),
        symbol=step.symbol,
        isin="",  # HolisticStep doesn't have ISIN
        quantity=step.quantity,
        estimated_price=money_to_proto(step.estimated_price),
        estimated_cost=money_to_proto(abs(step.estimated_value)),
        reason=step.reason,
        priority=step.step_number,
    )


def proto_to_holistic_step(proto: planning_pb2.PlannedAction) -> HolisticStep:
    """
    Convert protobuf PlannedAction to domain HolisticStep.

    Args:
        proto: PlannedAction protobuf message

    Returns:
        Domain HolisticStep
    """
    # Map protobuf TradeSide to side string
    side_map = {
        common_pb2.TRADE_SIDE_BUY: "BUY",
        common_pb2.TRADE_SIDE_SELL: "SELL",
    }

    side_str = side_map.get(proto.side, "BUY")
    price = proto_to_money(proto.estimated_price)
    value = proto_to_money(proto.estimated_cost)

    # Adjust value sign based on side
    if side_str == "SELL":
        value = -value

    return HolisticStep(
        step_number=proto.priority,
        side=side_str,
        symbol=proto.symbol,
        name=proto.symbol,  # Use symbol as name
        quantity=int(proto.quantity),
        estimated_price=price,
        estimated_value=value,
        currency="EUR",
        reason=proto.reason,
        narrative=proto.reason,  # Use reason as narrative
        is_windfall=False,
        is_averaging_down=False,
        contributes_to=[],
    )


def holistic_plan_to_proto(plan: HolisticPlan) -> planning_pb2.Plan:
    """
    Convert domain HolisticPlan to protobuf Plan.

    Args:
        plan: Domain HolisticPlan

    Returns:
        Plan protobuf message
    """
    total_value = sum(abs(step.estimated_value) for step in plan.steps)

    return planning_pb2.Plan(
        id=str(hash(plan.narrative_summary))[:16],  # Generate ID from narrative
        portfolio_hash="",  # HolisticPlan doesn't have portfolio_hash
        actions=[holistic_step_to_proto(step) for step in plan.steps],
        score=plan.end_state_score,
        expected_cost=money_to_proto(plan.cash_required),
        expected_value=money_to_proto(total_value),
        created_at=timestamp_to_proto(None),
        status=planning_pb2.READY if plan.feasible else planning_pb2.DRAFT,
    )


def proto_to_holistic_plan(proto: planning_pb2.Plan) -> HolisticPlan:
    """
    Convert protobuf Plan to domain HolisticPlan.

    Args:
        proto: Plan protobuf message

    Returns:
        Domain HolisticPlan
    """
    steps = [proto_to_holistic_step(action) for action in proto.actions]

    return HolisticPlan(
        steps=steps,
        current_score=0.0,  # Not in protobuf
        end_state_score=proto.score,
        improvement=0.0,  # Not in protobuf
        narrative_summary="",  # Not in protobuf
        score_breakdown={},  # Not in protobuf
        cash_required=proto_to_money(proto.expected_cost),
        cash_generated=0.0,  # Not in protobuf
        feasible=proto.status == planning_pb2.READY,
    )


# =============================================================================
# List Conversions
# =============================================================================


def positions_to_proto_list(positions: List[Position]) -> List[position_pb2.Position]:
    """Convert list of domain Positions to protobuf Positions."""
    return [position_to_proto(pos) for pos in positions]


def proto_list_to_positions(protos: List[position_pb2.Position]) -> List[Position]:
    """Convert list of protobuf Positions to domain Positions."""
    return [proto_to_position(proto) for proto in protos]


def securities_to_proto_list(
    securities: List[Security],
) -> List[security_pb2.Security]:
    """Convert list of domain Securities to protobuf Securities."""
    return [security_to_proto(sec) for sec in securities]


def proto_list_to_securities(
    protos: List[security_pb2.Security],
) -> List[Security]:
    """Convert list of protobuf Securities to domain Securities."""
    return [proto_to_security(proto) for proto in protos]
