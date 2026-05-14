from pogo_scout.filters.iv import iv_passes_floor


def test_iv_at_floor_passes():
    assert iv_passes_floor(iv_percent=90.0, iv_floor=90.0) is True


def test_iv_above_floor_passes():
    assert iv_passes_floor(iv_percent=98.5, iv_floor=90.0) is True


def test_iv_below_floor_fails():
    assert iv_passes_floor(iv_percent=89.999, iv_floor=90.0) is False


def test_iv_none_returns_false():
    assert iv_passes_floor(iv_percent=None, iv_floor=90.0) is False
