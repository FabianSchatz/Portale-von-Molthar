"""Tests for typed decisions that interrupt the normal turn flow."""

from collections import Counter

from portale_von_molthar.decisions import PaymentDecision
from portale_von_molthar.payments import PearlPayment, hand_resource_options, payment_plans
from portale_von_molthar.requirements import AnyOf, ExactValues, Parity, ParityValues


def test_payment_decision_uses_one_canonical_path_per_plan() -> None:
    resources = hand_resource_options(Counter({1: 1, 3: 1, 5: 1, 7: 1}))
    plans = payment_plans(
        resources,
        ParityValues(3, Parity.ODD),
    )
    decision = PaymentDecision(actor=0, target_owner=0, target_slot=1, plans=plans)
    assert {
        option.printed_value for option in decision.options() if isinstance(option, PearlPayment)
    } == {1, 3}

    pearl_one = next(
        option
        for option in decision.options()
        if isinstance(option, PearlPayment) and option.printed_value == 1
    )
    decision = decision.choose(pearl_one)
    pearl_five = next(
        option
        for option in decision.options()
        if isinstance(option, PearlPayment) and option.printed_value == 5
    )
    decision = decision.choose(pearl_five)
    assert decision.resolved_plan is not None
    assert decision.resolved_plan.discarded_values == (1, 5, 7)


def test_payment_decision_receives_no_dominated_longer_plan() -> None:
    requirement = AnyOf((ExactValues((1,)), ExactValues((1, 2))))
    resources = hand_resource_options(Counter({1: 1, 2: 1}))
    plans = payment_plans(resources, requirement)
    decision = PaymentDecision(actor=0, target_owner=0, target_slot=0, plans=plans)
    assert decision.resolved_plan is not None
    assert decision.resolved_plan.discarded_values == (1,)
