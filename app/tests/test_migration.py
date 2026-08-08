from alembic import command
from sqlalchemy import inspect

from dropme.db import engine


def test_migration_up_down_up(alembic_cfg):
    cfg = alembic_cfg
    command.upgrade(cfg, "head")
    assert "events" in inspect(engine).get_table_names()

    command.downgrade(cfg, "-1")
    assert "events" not in inspect(engine).get_table_names()

    command.upgrade(cfg, "head")
    assert "events" in inspect(engine).get_table_names()
