from pogo_scout.events import WantedSpecies
from pogo_scout.filters.species import species_matches_wanted


def _w(pid: int, fid: int | None, wild: bool) -> WantedSpecies:
    return WantedSpecies(pokemon_id=pid, form_id=fid, is_wildcard=wild)


def test_exact_base_form_match():
    wanted = [_w(246, None, False)]
    assert species_matches_wanted(pokemon_id=246, form_id=None, wanted=wanted) is True


def test_exact_form_match():
    wanted = [_w(37, 65, False)]
    assert species_matches_wanted(pokemon_id=37, form_id=65, wanted=wanted) is True


def test_exact_form_does_not_match_base():
    wanted = [_w(37, 65, False)]
    assert species_matches_wanted(pokemon_id=37, form_id=None, wanted=wanted) is False


def test_base_form_does_not_match_form_variant():
    wanted = [_w(37, None, False)]
    assert species_matches_wanted(pokemon_id=37, form_id=65, wanted=wanted) is False


def test_wildcard_matches_any_form():
    wanted = [_w(37, None, True)]
    assert species_matches_wanted(pokemon_id=37, form_id=None, wanted=wanted) is True
    assert species_matches_wanted(pokemon_id=37, form_id=65, wanted=wanted) is True


def test_wildcard_does_not_match_other_species():
    wanted = [_w(37, None, True)]
    assert species_matches_wanted(pokemon_id=246, form_id=None, wanted=wanted) is False


def test_empty_wanted_list_never_matches():
    assert species_matches_wanted(pokemon_id=246, form_id=None, wanted=[]) is False
