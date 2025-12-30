from pathlib import Path

from wqbrain_open.normalize import read_formulas_txt


def test_read_formulas_txt(tmp_path: Path):
    p = tmp_path / "a.txt"
    p.write_text("# c\n\nfoo\nbar\n", encoding="utf-8")
    assert read_formulas_txt(p) == ["foo", "bar"]
