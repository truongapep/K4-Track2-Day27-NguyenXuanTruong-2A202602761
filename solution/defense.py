"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    if ctx.tools.budget_remaining() < 1.0:
        return Verdict(alert=False, pillar="checks", reason="Insufficient budget for batch profile")

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

    return Verdict(alert=bool(reasons), pillar="checks", reason="; ".join(reasons))


def check_contract_checkpoint(payload, ctx):
    if ctx.tools.budget_remaining() < 1.5:
        return Verdict(alert=False, pillar="contracts", reason="Insufficient budget for contract diff")

    diff = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if "error" in diff:
        return Verdict(alert=False, pillar="contracts", reason="Contract diff unavailable")

    reasons = []
    if diff["violations"]:
        reasons.append("contract violations reported")
    if diff["freshness_delay_min"] > ctx.baseline["freshness_delay_max_min"]:
        reasons.append("contract freshness delay above baseline")

    return Verdict(alert=bool(reasons), pillar="contracts", reason="; ".join(reasons))


def check_lineage_run(payload, ctx):
    # TODO: ctx.tools.lineage_graph_slice(payload["run_id"])
    return Verdict(alert=False, pillar="lineage")


def check_feature_materialization(payload, ctx):
    # TODO: ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    return Verdict(alert=False, pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    # TODO: ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    return Verdict(alert=False, pillar="ai_infra")
