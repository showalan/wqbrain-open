from wqbrain_open.normalize import normalize_fastexpr, stable_dedupe


def test_normalize_replacements():
    s = "Ts_Rank(Rank(low), 9)"
    assert normalize_fastexpr(s) == "ts_rank(rank(low), 9)"


def test_stable_dedupe():
    assert stable_dedupe(["a", "b", "a", "c"]) == ["a", "b", "c"]
