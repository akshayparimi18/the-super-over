from app.rules import (
    FAST_INVENTORY,
    MATCHUP_RULES,
    SPIN_INVENTORY,
    BatsmanIntent,
    BowlerProfile,
    DeliveryType,
    consume_delivery,
    get_initial_inventory,
    resolve_matchup,
)
import pytest


def test_slog_6_plus_yorker_is_wicket():
    outcome = resolve_matchup(DeliveryType.YORKER, BatsmanIntent.SLOG_6)
    assert outcome.wicket is True
    assert outcome.runs == 0


def test_slog_6_plus_half_volley_is_six():
    outcome = resolve_matchup(DeliveryType.HALF_VOLLEY, BatsmanIntent.SLOG_6)
    assert outcome.runs == 6
    assert outcome.wicket is False


def test_defend_0_plus_yorker_is_zero():
    outcome = resolve_matchup(DeliveryType.YORKER, BatsmanIntent.DEFEND_0)
    assert outcome.runs == 0
    assert outcome.wicket is False


def test_inventories_have_six_deliveries_each():
    fast = get_initial_inventory(BowlerProfile.FAST)
    spin = get_initial_inventory(BowlerProfile.SPIN)

    assert sum(fast.values()) == 6
    assert fast["YORKER"] == 1
    assert fast["BOUNCER"] == 1
    assert fast["IN_SWINGER"] == 1
    assert fast["OUT_SWINGER"] == 1
    assert fast["HALF_VOLLEY"] == 2

    assert sum(spin.values()) == 6
    assert spin["OFF_BREAK"] == 1
    assert spin["LEG_BREAK"] == 1
    assert spin["GOOGLY"] == 1
    assert spin["TOP_SPIN"] == 1
    assert spin["HALF_VOLLEY"] == 2


def test_consume_delivery_decrements_and_raises_when_exhausted():
    inventory = {"YORKER": 1, "HALF_VOLLEY": 2}
    consume_delivery(inventory, DeliveryType.YORKER)
    assert inventory["YORKER"] == 0

    # Exhausted delivery raises ValueError
    with pytest.raises(ValueError, match="0 remaining stock"):
        consume_delivery(inventory, DeliveryType.YORKER)


def test_all_54_matchups_are_defined():
    # 9 deliveries x 6 batsman intents = 54 combinations
    assert len(MATCHUP_RULES) == 54
    for d in DeliveryType:
        for i in BatsmanIntent:
            assert (d, i) in MATCHUP_RULES
