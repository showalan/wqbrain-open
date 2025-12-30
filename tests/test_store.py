from pathlib import Path

from wqbrain_open.store import get_run_status, init_db, open_db, upsert_formula


def test_db_upsert(tmp_path: Path):
    db = tmp_path / "t.sqlite"
    conn = open_db(db)
    init_db(conn)

    upsert_formula(conn, formula_id=1, raw="x", normalized="y")
    assert get_run_status(conn, formula_id=1) == "PENDING"
