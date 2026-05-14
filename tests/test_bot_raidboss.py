from pogo_scout.bot.commands import cmd_raidboss
from pogo_scout.db import repo


def test_raidboss_add_by_name(db):
    reply = cmd_raidboss(["add", "Garchomp"], conn=db)
    assert "Garchomp" in reply
    assert repo.raid_boss_list(db) == {445}


def test_raidboss_add_by_id(db):
    cmd_raidboss(["add", "149"], conn=db)
    assert 149 in repo.raid_boss_list(db)


def test_raidboss_remove(db):
    cmd_raidboss(["add", "Garchomp"], conn=db)
    cmd_raidboss(["remove", "Garchomp"], conn=db)
    assert repo.raid_boss_list(db) == set()


def test_raidboss_list_empty(db):
    reply = cmd_raidboss(["list"], conn=db)
    assert "empty" in reply.lower() or "no" in reply.lower()


def test_raidboss_list_with_entries(db):
    cmd_raidboss(["add", "Garchomp"], conn=db)
    cmd_raidboss(["add", "Dragonite"], conn=db)
    reply = cmd_raidboss(["list"], conn=db)
    assert "Garchomp" in reply and "Dragonite" in reply


def test_raidboss_clear(db):
    cmd_raidboss(["add", "Garchomp"], conn=db)
    reply = cmd_raidboss(["clear"], conn=db)
    assert "cleared" in reply.lower()
    assert repo.raid_boss_list(db) == set()


def test_raidboss_unknown_species(db):
    reply = cmd_raidboss(["add", "Notapokemon"], conn=db)
    assert "unknown" in reply.lower()
