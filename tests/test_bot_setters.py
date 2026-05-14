from pogo_scout.bot.commands import (
    cmd_radius, cmd_iv, cmd_raidtier, cmd_pvprank,
    cmd_shinyalert, cmd_mapimage, cmd_silencethreshold, cmd_silencealert,
    cmd_wanted,
)
from pogo_scout.db import repo
from pogo_scout.events import WantedSpecies


def test_radius_sets_kv_and_returns_confirmation(db):
    reply = cmd_radius(["500"], conn=db)
    assert "500" in reply
    assert repo.get_kv(db, "radius_m", default=1000) == 500


def test_radius_rejects_non_int(db):
    reply = cmd_radius(["abc"], conn=db)
    assert "usage" in reply.lower() or "invalid" in reply.lower()
    assert repo.get_kv(db, "radius_m", default=1000) == 1000


def test_iv_sets_kv(db):
    reply = cmd_iv(["95"], conn=db)
    assert "95" in reply
    assert repo.get_kv(db, "iv_floor", default=90.0) == 95.0


def test_raidtier_sets_kv(db):
    reply = cmd_raidtier(["6"], conn=db)
    assert "6" in reply
    assert repo.get_kv(db, "raid_tier_floor", default=5) == 6


def test_pvprank_great(db):
    reply = cmd_pvprank(["great", "1"], conn=db)
    assert "great" in reply.lower() and "1" in reply
    assert repo.get_kv(db, "gl_rank_floor", default=5) == 1


def test_pvprank_ultra(db):
    reply = cmd_pvprank(["ultra", "3"], conn=db)
    assert repo.get_kv(db, "ul_rank_floor", default=5) == 3


def test_shinyalert_toggle(db):
    cmd_shinyalert(["off"], conn=db)
    assert repo.get_kv(db, "shiny_alert", default=True) is False
    cmd_shinyalert(["on"], conn=db)
    assert repo.get_kv(db, "shiny_alert", default=True) is True


def test_mapimage_toggle(db):
    cmd_mapimage(["off"], conn=db)
    assert repo.get_kv(db, "map_image_enabled", default=True) is False


def test_silencethreshold_sets_kv(db):
    reply = cmd_silencethreshold(["60m"], conn=db)
    assert "60" in reply
    assert repo.get_kv(db, "silence_threshold_min", default=45) == 60


def test_silencealert_toggle(db):
    cmd_silencealert(["off"], conn=db)
    assert repo.get_kv(db, "silence_alert_enabled", default=True) is False


def test_wanted_add_list_remove(db):
    cmd_wanted(["add", "Larvitar"], conn=db)
    assert WantedSpecies(246, None, False) in repo.wanted_list(db)
    listed = cmd_wanted(["list"], conn=db)
    assert "Larvitar" in listed
    cmd_wanted(["remove", "Larvitar"], conn=db)
    assert WantedSpecies(246, None, False) not in repo.wanted_list(db)


def test_wanted_add_form_qualified(db):
    cmd_wanted(["add", "Alolan", "Vulpix"], conn=db)
    assert WantedSpecies(37, 65, False) in repo.wanted_list(db)


def test_wanted_add_wildcard(db):
    cmd_wanted(["add", "Vulpix", "*"], conn=db)
    assert WantedSpecies(37, None, True) in repo.wanted_list(db)


def test_wanted_add_unknown_returns_error(db):
    reply = cmd_wanted(["add", "Notapokemon"], conn=db)
    assert "unknown" in reply.lower()
