from unittest.mock import patch
import pytest

from app.rules import (
    FAST_INVENTORY,
    MATCHUP_RULES,
    SPIN_INVENTORY,
    BatsmanIntent,
    BowlerProfile,
    DeliveryType,
    Outcome,
    consume_delivery,
    get_initial_inventory,
    resolve_matchup,
)


def test_all_54_matchups_are_defined_with_valid_weights():
    assert len(MATCHUP_RULES) == 54
    for d in DeliveryType:
        for i in BatsmanIntent:
            assert (d, i) in MATCHUP_RULES
            outcomes, weights = MATCHUP_RULES[(d, i)]

            assert isinstance(outcomes, list)
            assert isinstance(weights, list)
            assert len(outcomes) == len(weights)
            assert len(outcomes) > 0

            for out in outcomes:
                assert isinstance(out, Outcome)

            for w in weights:
                assert isinstance(w, int)
                assert w > 0

            # Weights must sum to exactly 100 for each matchup
            assert sum(weights) == 100


def test_example_matchup_yorker_defend_weights():
    outcomes, weights = MATCHUP_RULES[(DeliveryType.YORKER, BatsmanIntent.DEFEND_0)]
    assert outcomes == [Outcome(runs=0), Outcome(runs=0, wicket=True)]
    assert weights == [90, 10]
    assert sum(weights) == 100


def test_example_matchup_yorker_slog_weights():
    outcomes, weights = MATCHUP_RULES[(DeliveryType.YORKER, BatsmanIntent.SLOG_6)]
    assert outcomes == [Outcome(runs=0, wicket=True), Outcome(runs=1), Outcome(runs=6)]
    assert weights == [85, 10, 5]
    assert sum(weights) == 100


def test_resolve_matchup_uses_random_choices():
    mock_outcome = Outcome(runs=6)
    with patch("random.choices", return_value=[mock_outcome]) as mock_choices:
        result = resolve_matchup(DeliveryType.HALF_VOLLEY, BatsmanIntent.SLOG_6)
        mock_choices.assert_called_once()
        assert result.runs == 6
        assert result.wicket is False


def test_resolve_matchup_wicket_via_mock():
    mock_outcome = Outcome(runs=0, wicket=True)
    with patch("random.choices", return_value=[mock_outcome]):
        result = resolve_matchup(DeliveryType.YORKER, BatsmanIntent.SLOG_6)
        assert result.runs == 0
        assert result.wicket is True


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

    with pytest.raises(ValueError, match="0 remaining stock"):
        consume_delivery(inventory, DeliveryType.YORKER)
