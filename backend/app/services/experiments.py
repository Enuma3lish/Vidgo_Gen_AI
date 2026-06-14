"""A/B cohort assignment foundation.

Deterministic hash-based bucketing: same user_id + experiment name always
maps to the same cohort label, so a user's experience is stable across
sessions and we can attribute outcomes correctly.

This module ships ONLY the assignment primitive. The experiment runner
(decide which model_used to call for which cohort) and the admin UI to
create / activate / compare experiments are intentionally NOT here yet —
they need a separate design pass (experiment lifecycle, statistical
significance, segmentation). What's here is enough to start tagging
metric rows with a cohort label once a caller opts in.

Usage from a future experiment runner:

    from app.services.experiments import assign_cohort

    cohort = assign_cohort(user_id, "kling_version_v2_6_vs_v2_5", weights={
        "control":   50,   # 50% → kling-2.6
        "treatment": 50,   # 50% → kling-2.5
    })
    if cohort == "treatment":
        params["version"] = "2.5"
    # ProviderRouter.route(...) will tag generation_metrics.cohort = cohort

The bucket math uses MD5 because we need stable hashing across Python
versions and instances — Python's built-in hash() is randomized per
process.
"""
from __future__ import annotations

import hashlib
from typing import Dict, Optional


def assign_cohort(
    user_id: Optional[str],
    experiment_name: str,
    weights: Dict[str, int],
) -> Optional[str]:
    """Deterministically bucket user_id into one of the weighted cohorts.

    Returns None when user_id is falsy (anonymous traffic stays unbucketed
    rather than getting a random cohort each request). Sum of weights must
    be > 0; the function normalizes so callers can pass arbitrary integers
    (50/50, 90/10, 33/33/33 etc.).
    """
    if not user_id or not weights:
        return None
    total = sum(int(w) for w in weights.values())
    if total <= 0:
        return None

    h = hashlib.md5(f"{experiment_name}:{user_id}".encode("utf-8")).hexdigest()
    # First 8 hex chars → 32-bit int → modulo total. Plenty of entropy for
    # cohort assignment; no need for the full 128-bit digest.
    bucket = int(h[:8], 16) % total

    cursor = 0
    for label, weight in weights.items():
        cursor += int(weight)
        if bucket < cursor:
            return label
    # Floating-point edge case shouldn't reach here, but be defensive.
    return next(iter(weights.keys()))
