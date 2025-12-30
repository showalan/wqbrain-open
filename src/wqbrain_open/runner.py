from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .client import (
    ThrottledError,
    UnsupportedOperatorError,
    WQClient,
    WQError,
    extract_unknown_operator,
    rewrite_operator,
)
from .normalize import normalize_fastexpr, read_formulas_txt, stable_dedupe
from .rate_limit import RateLimiter
from .store import (
    get_formula,
    init_db,
    list_to_run,
    mark_attempt,
    mark_error,
    mark_success,
    open_db,
    upsert_formula,
)


DEFAULT_SETTINGS: dict[str, Any] = {
    "nanHandling": "OFF",
    "instrumentType": "EQUITY",
    "delay": 1,
    "universe": "TOP3000",
    "truncation": 0.1,
    "unitHandling": "VERIFY",
    "pasteurization": "ON",
    "region": "USA",
    "language": "FASTEXPR",
    "decay": 6,
    "neutralization": "SUBINDUSTRY",
    "visualization": False,
}


_OPERATOR_ALIASES: dict[str, tuple[str, ...]] = {
    # common arXiv / pseudo-code aliases
    "delay": ("ts_delay",),
    "delta": ("ts_delta",),
    # Some environments expose min/max differently; try common variants.
    "ts_min": ("ts_minimum",),
    "ts_max": ("ts_maximum",),
}


_thread_local = threading.local()


def _get_client(credentials_path: Path) -> WQClient:
    if getattr(_thread_local, "client", None) is None:
        _thread_local.client = WQClient(credentials_path)
    return _thread_local.client


def _parse_result(alpha_platform_id: str, alpha_json: dict[str, Any]) -> dict[str, Any]:
    is_block = alpha_json.get("is", {}) if isinstance(alpha_json, dict) else {}
    checks = is_block.get("checks", []) if isinstance(is_block, dict) else []

    weight_check = None
    subsharpe = None
    self_corr = None

    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            name = check.get("name")
            if name == "CONCENTRATED_WEIGHT":
                weight_check = check.get("result")
            elif name == "LOW_SUB_UNIVERSE_SHARPE":
                subsharpe = check.get("value")
            elif name == "SELF_CORRELATION":
                self_corr = check.get("value")

    return {
        "alpha_platform_id": str(alpha_platform_id),
        "alpha_url": f"https://platform.worldquantbrain.com/alpha/{alpha_platform_id}",
        "sharpe": is_block.get("sharpe"),
        "fitness": is_block.get("fitness"),
        "turnover": (float(is_block.get("turnover")) * 100.0) if is_block.get("turnover") is not None else None,
        "weight_check": weight_check,
        "subsharpe": subsharpe,
        "self_corr": self_corr,
        "checks": {c.get("name"): c for c in checks if isinstance(c, dict) and c.get("name")},
    }


def _simulate_one(
    *,
    credentials_path: Path,
    limiter: RateLimiter,
    poll_seconds: float,
    formula: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    client = _get_client(credentials_path)

    limiter.wait()
    sim_url = client.create_simulation(formula=formula, settings=settings)

    limiter.wait()
    alpha_platform_id = client.poll_simulation(sim_url=sim_url, poll_seconds=poll_seconds)

    limiter.wait()
    alpha_json = client.fetch_alpha(alpha_platform_id)

    out = _parse_result(alpha_platform_id, alpha_json)
    out["simulation_url"] = sim_url
    return out


def _simulate_one_with_operator_fallback(
    *,
    credentials_path: Path,
    limiter: RateLimiter,
    poll_seconds: float,
    raw_formula: str,
    normalized_formula: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    try:
        result = _simulate_one(
            credentials_path=credentials_path,
            limiter=limiter,
            poll_seconds=poll_seconds,
            formula=normalized_formula,
            settings=settings,
        )
        result["effective_formula"] = normalized_formula
        return result
    except Exception as exc:
        msg = str(exc)
        op = extract_unknown_operator(msg)
        if not op:
            raise

        attempted = _OPERATOR_ALIASES.get(op, ())
        for repl in attempted:
            rewritten = rewrite_operator(normalized_formula, old=op, new=repl)
            if rewritten == normalized_formula:
                continue
            try:
                result = _simulate_one(
                    credentials_path=credentials_path,
                    limiter=limiter,
                    poll_seconds=poll_seconds,
                    formula=rewritten,
                    settings=settings,
                )
                result["effective_formula"] = rewritten
                if isinstance(result.get("checks"), dict):
                    result["checks"]["_operator_alias"] = {"from": op, "to": repl}
                return result
            except Exception:
                continue

        raise UnsupportedOperatorError(
            operator_name=op,
            attempted=attempted,
            message=f"Unsupported operator '{op}'. Tried aliases: {list(attempted)}. Last error: {msg}",
        )


def run_batch(
    *,
    input_path: Path,
    db_path: Path,
    credentials_path: Path,
    concurrency: int,
    batch_size: int,
    batch_sleep: float,
    min_request_interval: float,
    poll_seconds: float,
    force: bool,
) -> None:
    formulas_raw = stable_dedupe(read_formulas_txt(input_path))
    if not formulas_raw:
        print("No formulas found in input file")
        return

    conn = open_db(db_path)
    init_db(conn)

    for idx, raw in enumerate(formulas_raw, start=1):
        upsert_formula(conn, formula_id=idx, raw=raw, normalized=normalize_fastexpr(raw))

    to_run = list_to_run(conn, force=force)
    if not to_run:
        print("Nothing to run (all formulas already completed)")
        return

    limiter = RateLimiter(min_request_interval)
    total = len(to_run)
    print(f"Prepared {total} formulas to simulate. DB: {db_path}")

    pos = 0
    while pos < total:
        batch_ids = to_run[pos : pos + batch_size]
        pos += len(batch_ids)

        print(f"Running batch {pos - len(batch_ids) + 1}-{pos} / {total} ...")

        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {}
            for formula_id in batch_ids:
                row = get_formula(conn, formula_id=formula_id)
                raw_formula = row["raw_formula"]
                normalized = row["normalized"]

                mark_attempt(conn, formula_id=formula_id)

                futures[
                    ex.submit(
                        _simulate_one_with_operator_fallback,
                        credentials_path=credentials_path,
                        limiter=limiter,
                        poll_seconds=poll_seconds,
                        raw_formula=raw_formula,
                        normalized_formula=normalized,
                        settings=dict(DEFAULT_SETTINGS),
                    )
                ] = formula_id

            for fut in as_completed(futures):
                fid = futures[fut]
                try:
                    res = fut.result()
                    mark_success(conn, formula_id=fid, result=res)
                    print(f"  SUCCESS formula_id={fid} sharpe={res.get('sharpe')} fitness={res.get('fitness')}")
                except UnsupportedOperatorError as e:
                    mark_error(conn, formula_id=fid, status="UNSUPPORTED", error=str(e))
                    print(f"  UNSUPPORTED formula_id={fid}: {e}")
                except ThrottledError as e:
                    mark_error(conn, formula_id=fid, status="THROTTLED", error=str(e))
                    print(f"  THROTTLED formula_id={fid}: {e}")
                except (WQError, Exception) as e:
                    mark_error(conn, formula_id=fid, status="ERROR", error=str(e))
                    print(f"  ERROR formula_id={fid}: {e}")

        if pos < total and batch_sleep > 0:
            time.sleep(batch_sleep)
