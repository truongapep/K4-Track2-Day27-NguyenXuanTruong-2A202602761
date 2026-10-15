"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
from api import Verdict
import math


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    profile = ctx.tools.batch_profile(payload["batch_id"])
    if "error" in profile:
        return Verdict(alert=False, pillar="checks", reason="Batch profile unavailable")

    baseline = ctx.baseline
    reasons = []
    if not baseline["row_count_min"] <= profile["row_count"] <= baseline["row_count_max"]:
        reasons.append("row count outside baseline")
    if profile["null_rate"]["customer_id"] > baseline["null_rate_max"]:
        reasons.append("customer_id null rate above baseline")
    if not baseline["mean_amount_min"] <= profile["mean_amount"] <= baseline["mean_amount_max"]:
        reasons.append("mean amount outside baseline")
    if profile["staleness_min"] > baseline["staleness_min_max"]:
        reasons.append("batch is stale")

    row_mean = (baseline["row_count_min"] + baseline["row_count_max"]) / 2
    row_sigma = (baseline["row_count_max"] - baseline["row_count_min"]) / 6
    amount_mean = (baseline["mean_amount_min"] + baseline["mean_amount_max"]) / 2
    amount_sigma = (baseline["mean_amount_max"] - baseline["mean_amount_min"]) / 6
    distance = math.sqrt(
        ((profile["row_count"] - row_mean) / row_sigma) ** 2
        + ((profile["mean_amount"] - amount_mean) / amount_sigma) ** 2
        + (profile["null_rate"]["customer_id"] / baseline["null_rate_max"]) ** 2
        + (profile["staleness_min"] / baseline["staleness_min_max"]) ** 2
    )
    # For two independent normal z-scores, z1^2 + z2^2 ~ chi-square(2).
    # Match the baseline's two-sided 3-sigma tail probability (~0.0027).
    # Clean null/staleness ratios each contribute at most 1 below their caps.
    # This is conservative; correlations/non-normal tails remain a limitation.
    composite_threshold = math.sqrt(-2 * math.log(0.0027) + 2)
    if distance > composite_threshold:
        reasons.append("combined batch deviation above threshold")

    return Verdict(alert=bool(reasons), pillar="checks", reason="; ".join(reasons))


def check_contract_checkpoint(payload, ctx):
    diff = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if "error" in diff:
        return Verdict(alert=False, pillar="contracts", reason="Contract diff unavailable")

    reasons = []
    if diff["violations"]:
        reasons.append("contract violations reported")
    if diff["freshness_delay_min"] > ctx.baseline["freshness_delay_max_min"]:
        reasons.append("contract freshness delay above baseline")
    declared_freshness = payload.get("declared_sla", {}).get("freshness_min")
    if declared_freshness is not None and diff["freshness_delay_min"] > declared_freshness:
        reasons.append("contract freshness delay exceeds declared SLA")

    return Verdict(alert=bool(reasons), pillar="contracts", reason="; ".join(reasons))


def check_lineage_run(payload, ctx):
    graph = ctx.tools.lineage_graph_slice(payload["run_id"])
    if "error" in graph:
        return Verdict(alert=False, pillar="lineage", reason="Lineage slice unavailable")

    reasons = []
    if graph["duration_ms"] > ctx.baseline["lineage_duration_ms_max"]:
        reasons.append("lineage runtime above baseline")
    # A model dependency is a schema rule, independent of event IDs or seeds.
    if "dbt:stg_orders" in payload.values():
        if {"raw.orders", "raw.customers"} - set(graph["actual_upstream"]):
            reasons.append("stg_orders missing required raw source")
    # Use declared expectations when present; do not invent an expected graph.
    expected_upstream = payload.get("expected_upstream")
    if expected_upstream is not None:
        if set(expected_upstream) - set(graph["actual_upstream"]):
            reasons.append("missing expected upstream dependencies")
    elif not graph["actual_upstream"]:
        reasons.append("no upstream dependencies")
    else:
        # Partition by event metadata, excluding the unique run identifier.
        # Require repeated observations before treating a topology as evidence.
        group = tuple(sorted((key, repr(value)) for key, value in payload.items()
                             if key != "run_id"))
        history = ctx.state.setdefault("lineage_topologies", {}).setdefault(group, {})
        upstream = frozenset(graph["actual_upstream"])
        if any(count >= 3 and upstream < previous
               for previous, count in history.items()):
            reasons.append("upstream dependencies missing from repeated topology")
        history[upstream] = history.get(upstream, 0) + 1
    if "expected_downstream_count" in payload:
        if graph["actual_downstream_count"] != payload["expected_downstream_count"]:
            reasons.append("downstream count differs from expectation")
    elif graph["actual_downstream_count"] <= 0:
        reasons.append("no downstream outputs")

    return Verdict(alert=bool(reasons), pillar="lineage", reason="; ".join(reasons))


def check_feature_materialization(payload, ctx):
    drift = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if "error" in drift:
        return Verdict(alert=False, pillar="ai_infra", reason="Feature drift unavailable")

    # Leave a margin above baseline for natural training-serving variation.
    threshold = max(ctx.baseline["feature_mean_shift_sigma_max"], 0.65)
    alert = drift["mean_shift_sigma"] > threshold
    return Verdict(alert=alert, pillar="ai_infra",
                   reason="training-serving feature skew above baseline" if alert else "")


def check_embedding_batch(payload, ctx):
    drift = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if "error" in drift:
        return Verdict(alert=False, pillar="ai_infra", reason="Embedding drift unavailable")

    reasons = []
    if drift["centroid_shift"] > min(ctx.baseline["embedding_centroid_shift_max"], 0.040):
        reasons.append("embedding centroid shift above baseline")
    if drift["avg_doc_age_days"] > min(ctx.baseline["corpus_avg_doc_age_days_max"], 44.0):
        reasons.append("corpus documents are stale")

    return Verdict(alert=bool(reasons), pillar="ai_infra", reason="; ".join(reasons))
