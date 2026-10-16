from app.rules import Delivery, Shot, resolve_matchup


def test_yorker_helicopter_is_six():
    outcome = resolve_matchup(Delivery.YORKER, Shot.HELICOPTER)
    assert outcome.runs == 6
    assert not outcome.wicket
    assert not outcome.wide


def test_bouncer_duck_is_wide_and_one_run():
    outcome = resolve_matchup(Delivery.BOUNCER, Shot.DUCK)
    assert outcome.runs == 1
    assert outcome.wide
    assert not outcome.wicket


def test_spin_helicopter_is_wicket():
    outcome = resolve_matchup(Delivery.SPIN, Shot.HELICOPTER)
    assert outcome.wicket
    assert outcome.runs == 0


def test_all_nine_matchups_are_defined():
    from app.rules import MATCHUP_RULES

    assert len(MATCHUP_RULES) == 9
