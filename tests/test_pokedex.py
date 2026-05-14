import pytest

from pogo_scout.pokedex import (
    name_for,
    parse_species_input,
    PokedexLookupError,
)


def test_name_for_base_form():
    assert name_for(246, None) == "Larvitar"


def test_name_for_form():
    assert name_for(37, 65) == "Alolan Vulpix"


def test_name_for_unknown_form_falls_back_to_base():
    assert name_for(37, 999) == "Vulpix"


def test_name_for_unknown_id_raises():
    with pytest.raises(PokedexLookupError):
        name_for(9999, None)


def test_parse_input_by_name():
    pid, fid, wildcard = parse_species_input("Larvitar")
    assert (pid, fid, wildcard) == (246, None, False)


def test_parse_input_by_id():
    pid, fid, wildcard = parse_species_input("246")
    assert (pid, fid, wildcard) == (246, None, False)


def test_parse_input_form_qualified():
    pid, fid, wildcard = parse_species_input("Alolan Vulpix")
    assert (pid, fid, wildcard) == (37, 65, False)


def test_parse_input_wildcard():
    pid, fid, wildcard = parse_species_input("Vulpix *")
    assert (pid, fid, wildcard) == (37, None, True)


def test_parse_input_case_insensitive():
    pid, fid, _ = parse_species_input("larvitar")
    assert pid == 246


def test_parse_input_unknown_raises():
    with pytest.raises(PokedexLookupError):
        parse_species_input("Notapokemon")
