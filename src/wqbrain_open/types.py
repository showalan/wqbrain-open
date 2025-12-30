from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormulaItem:
    formula_id: int
    raw: str
    normalized: str
