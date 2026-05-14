from pogo_scout.filters.pvp import pvp_passes


def test_great_rank_at_floor_passes():
    assert pvp_passes(great=5, ultra=None, gl_floor=5, ul_floor=5) is True


def test_ultra_rank_at_floor_passes():
    assert pvp_passes(great=None, ultra=5, gl_floor=5, ul_floor=5) is True


def test_great_below_floor_passes_when_lower_number_means_better_rank():
    # rank 1 is "better" than rank 5; floor of 5 should accept rank 1.
    assert pvp_passes(great=1, ultra=None, gl_floor=5, ul_floor=5) is True


def test_both_above_floor_fails():
    assert pvp_passes(great=6, ultra=10, gl_floor=5, ul_floor=5) is False


def test_both_none_fails():
    assert pvp_passes(great=None, ultra=None, gl_floor=5, ul_floor=5) is False


def test_only_one_league_passes_required():
    assert pvp_passes(great=100, ultra=2, gl_floor=5, ul_floor=5) is True
