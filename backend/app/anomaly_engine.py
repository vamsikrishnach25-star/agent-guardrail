"""
Week 12: Anomaly Detection - a third safety net alongside Policy and Risk.

Policy asks "does this violate an explicit rule someone wrote down?" Risk
asks "how dangerous is this action, in general, for any agent?" (see
risk_engine.py's own docstring, which flagged this module as future work
back in Week 2). Anomaly asks a genuinely different question: "is this
unusual for THIS agent, compared to its own history?" A $50 transfer is
unremarkable in general - low risk score, no policy targets it - but it's
a real anomaly for an agent that has, until now, only ever called
get_balance. Policy and Risk both miss that, because neither one looks at
an individual agent's own behavioral baseline; this module is the one
place that does.

Two layers, not one - and the split between them is a real lesson from
building this, not a design chosen up front:

1. Two explicit, deterministic checks for the two clearest and most
   explainable individual signals: a tool this agent has never called
   before, and an amount far above its own historical average.
2. scikit-learn's IsolationForest on top, for subtler *combinations* of
   features that no single rule would catch (an ordinary amount, at an
   ordinary hour, on a tool this agent uses often - just not usually
   together).

The deterministic layer exists because IsolationForest turned out to be
genuinely unreliable at exactly the case it sounds like it should ace: a
single feature that's astronomically outside its training range. It
isolates points via *relative* threshold splits drawn from the training
data's own observed min/max at each node - it has no notion of
"999999 is a thousand times bigger than anything I've seen," only "is
this point above or below a threshold drawn from what I've seen." A
brand-new agent calling `transfer_money` with an amount 100x its own
average, when every historical amount clustered near zero, does not
reliably get isolated any faster than an ordinary point, because the
random split thresholds are drawn from that same near-zero range and a
sizeable share of ordinary points end up on the same side of them as the
genuine outlier. Confirmed directly against this model (not assumed):
fit on a training set with a near-constant feature, a test point 6+
orders of magnitude outside that range still came back as a normal
inlier. That's a real, reproducible property of the algorithm, not a
tuning mistake - and it's a better interview answer than pretending the
model catches everything: know what your model is actually good at (
joint, multivariate pattern deviation across many small history samples,
which is exactly the "unusual combination" case above) and what it
structurally is not (a single blatant outlier in a thin-tailed feature),
and don't rely on it for the second.

Cold start: a brand-new agent (or one that just hasn't accumulated much
history yet) has no baseline to compare against - MIN_HISTORY events are
required before this module will flag anything at all, deterministic
checks included. Below that threshold this always returns "not enough
history yet" rather than guessing, the same fail-safe-not-fail-loud
posture the rest of this project takes (see policy_dsl.py's evaluate()
on failing a single bad comparison closed, not crashing the whole
pipeline).

The IsolationForest layer is trained fresh, per request, on that specific
agent's own recent history - not offline in a periodic batch job.
Deliberately, at this project's scale: history sizes are small enough
(HISTORY_WINDOW caps it at 200 events) that fitting takes single-digit
milliseconds, and fitting fresh each time means every event is always
scored against the most current possible baseline, with no stale cached
model to invalidate. At real production volume - thousands of agents,
each with deep history - this would move to a model per agent that's
retrained on a schedule (hourly/daily) and cached, not refit on every
single tool call; noted here rather than silently, same as every other
proportionate-for-this-project's-scale call this codebase makes (see
migrations.py and the approvals-table-not-Redis note in models.py for
the same kind of trade-off, made the same way: named, not hidden).
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Event

MIN_HISTORY = 20             # fewer historical events than this and there's no reliable baseline - cold start
HISTORY_WINDOW = 200          # only the agent's most recent N events set the baseline - old behavior shouldn't anchor it forever
CONTAMINATION = 0.05          # assumed fraction of an agent's own history that was itself unusual
AMOUNT_MULTIPLIER = 3         # a current amount this many times the agent's own historical average trips the deterministic check
AMOUNT_FLOOR = 100            # ...but only once the amount is at least this large, so $2 vs a $0.50 average doesn't trip it


@dataclass
class AnomalyAssessment:
    is_anomaly: bool
    score: int  # 0-100, higher = more unusual for this specific agent. 0 when there's not enough history to judge.
    reason: str
    sample_size: int = 0


def _numeric_amount(arguments: dict) -> float:
    amount = arguments.get("amount")
    return float(amount) if isinstance(amount, (int, float)) else 0.0


def _features(tool_name: str, arguments: dict, hour: int, risk_score: float, tool_freq: dict) -> list[float]:
    """One feature vector per event: time of day, how dangerous the Risk
    Engine independently scored it, the raw amount involved (0 if none),
    and how often *this agent specifically* has historically called this
    tool. Kept even though the two clearest signals it could carry (a
    brand-new tool, a wildly large amount) are handled deterministically
    below, not by the model - it still contributes to the model's view of
    what an ordinary combination of tool/amount/timing looks like for
    this agent, which is what IsolationForest is actually being asked
    to judge here."""
    return [
        float(hour),
        float(risk_score or 0.0),
        _numeric_amount(arguments),
        tool_freq.get(tool_name, 0.0),
    ]


def detect_anomaly(db: Session, agent_id: str, tool_name: str, arguments: dict, risk_score: float) -> AnomalyAssessment:
    rows = db.execute(
        select(Event.tool_name, Event.arguments, Event.risk_score, Event.created_at)
        .where(Event.agent_id == agent_id)
        .order_by(Event.created_at.desc())
        .limit(HISTORY_WINDOW)
    ).all()

    sample_size = len(rows)
    if sample_size < MIN_HISTORY:
        return AnomalyAssessment(
            is_anomaly=False,
            score=0,
            reason=f"not enough history yet to judge ({sample_size}/{MIN_HISTORY} events for this agent)",
            sample_size=sample_size,
        )

    tool_counts: dict[str, int] = {}
    for row in rows:
        tool_counts[row.tool_name] = tool_counts.get(row.tool_name, 0) + 1
    tool_freq = {name: count / sample_size for name, count in tool_counts.items()}

    x_train = [
        _features(row.tool_name, row.arguments or {}, row.created_at.hour, row.risk_score, tool_freq)
        for row in rows
    ]
    current_hour = datetime.now(timezone.utc).hour
    x_current = _features(tool_name, arguments, current_hour, risk_score, tool_freq)

    # --- Layer 1: deterministic checks for the two clearest signals ---
    reasons = []
    rule_triggered = False

    if tool_freq.get(tool_name, 0.0) == 0.0:
        reasons.append(f"'{tool_name}' has never been called by this agent before")
        rule_triggered = True

    current_amount = x_current[2]
    historical_amounts = [f[2] for f in x_train if f[2] > 0]
    if current_amount >= AMOUNT_FLOOR and historical_amounts:
        avg_amount = sum(historical_amounts) / len(historical_amounts)
        if avg_amount > 0 and current_amount > AMOUNT_MULTIPLIER * avg_amount:
            reasons.append(
                f"amount ({current_amount:g}) is more than {AMOUNT_MULTIPLIER}x this "
                f"agent's historical average ({avg_amount:.0f})"
            )
            rule_triggered = True

    # --- Layer 2: IsolationForest, for combinations no single rule covers ---
    model = IsolationForest(contamination=CONTAMINATION, random_state=42, n_estimators=100)
    model.fit(x_train)
    raw_score = model.decision_function([x_current])[0]  # higher = more normal, lower (can go negative) = more anomalous
    model_flagged = bool(model.predict([x_current])[0] == -1)

    # decision_function is centered on the model's own fitted decision boundary (0 = right at
    # the threshold, positive = normal side, negative = anomalous side) - map it onto a 0-100
    # "unusualness" score pointing the same direction as risk_score (higher = worse), with a
    # small floor so a comfortably-normal point reads as comfortably low, not a misleading ~50.
    model_score = int(max(0, min(100, round((0 - raw_score) * 200 + 30))))

    is_anomaly = rule_triggered or model_flagged
    score = 100 if rule_triggered else model_score

    if reasons:
        reason = "; ".join(reasons)
    elif model_flagged:
        reason = "unusual combination of timing/amount/tool relative to this agent's own history"
    else:
        reason = "consistent with this agent's historical behavior"

    return AnomalyAssessment(is_anomaly=is_anomaly, score=score, reason=reason, sample_size=sample_size)
