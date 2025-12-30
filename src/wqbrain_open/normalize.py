from __future__ import annotations

import re
from typing import Iterable


_NORMALIZE_REPLACEMENTS: list[tuple[str, str]] = [
    ("Ts_Rank", "ts_rank"),
    ("Ts_ArgMax", "ts_arg_max"),
    ("Ts_ArgMin", "ts_arg_min"),
    ("SignedPower", "signed_power"),
    ("Log", "log"),
    ("Rank", "rank"),
    ("Sign", "sign"),
    ("Abs", "abs"),
    # common arxiv->FASTEXPR operator name differences
    ("correlation", "ts_corr"),
    ("covariance", "ts_covariance"),
    ("stddev", "ts_std_dev"),
    ("delta", "ts_delta"),
    ("delay", "ts_delay"),
]


def normalize_fastexpr(formula: str) -> str:
    s = (formula or "").strip()
    for a, b in _NORMALIZE_REPLACEMENTS:
        s = re.sub(rf"\b{re.escape(a)}\b", b, s)

    # map function-like sum(...) to ts_sum(...) (avoid already namespaced variants)
    s = re.sub(r"\bsum\s*\(", "ts_sum(", s)

    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def read_formulas_txt(path) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        out.append(s)
    return out


def stable_dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out
