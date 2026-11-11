"""Confidence of an option from explicit rules: a band and the signals behind it, no number.

Every signal has a stable code and a Polish label, so the UI and the recommender speak about
the same facts. A missing or failed check is a risk only for the options that use it; for
the other options it is information, so the band describes the option, not the plan.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from app.orchestration.planning import SUBSTITUTE_CAPABILITIES
from app.orchestration.registry import CAPABILITIES
from app.orchestration.schema import (
    Capability,
    Compatibility,
    HistorySignal,
    SubstituteConsent,
    TaskStatus,
)
from app.recommendation.schema import ConfidenceBand, RecommendationOption, Signal

# Capabilities whose results an option relies on, by what the option takes the shortage from.
SUBSTITUTE_USES: frozenset[Capability] = frozenset(
    {"substitute-compatibility", "substitute-availability", "customer-history"}
)
SUPPLIER_USES: frozenset[Capability] = frozenset({"supplier-availability"})

# Risks that alone make an option LOW.
LOW_RISKS = frozenset({"incomplete_coverage", "deadline_missed"})

CAPABILITY_LABELS: dict[Capability, str] = {
    "substitute-compatibility": "zgodność zamiennika",
    "substitute-availability": "stan zamiennika",
    "supplier-availability": "dostępność u dostawcy",
    "customer-history": "historia klienta",
}
INPUT_LABELS: dict[str, str] = {
    "customer": "klient",
    "product_code": "kod produktu",
    "quantity": "ilość",
}


@dataclass(frozen=True)
class ConfidenceContext:
    deadline: date | None
    consent: SubstituteConsent
    task_statuses: Mapping[Capability, TaskStatus]  # planned capabilities only
    compatibility: Mapping[str, Compatibility]  # substitute code -> compatibility
    history: HistorySignal | None  # None without a completed customer-history task
    uncertain_inputs: Sequence[str]


def _positive(code: str, label: str) -> Signal:
    return Signal(code=code, polarity="positive", label=label)


def _risk(code: str, label: str) -> Signal:
    return Signal(code=code, polarity="risk", label=label)


def _info(code: str, label: str) -> Signal:
    return Signal(code=code, polarity="info", label=label)


def _substitute_signals(code: str, context: ConfidenceContext) -> list[Signal]:
    signals: list[Signal] = []
    compatibility = context.compatibility.get(code)
    if compatibility == "full":
        signals.append(_positive("compat_full", f"Zamiennik {code} w pełni zgodny"))
    elif compatibility == "partial":
        signals.append(_risk("compat_partial", f"Zamiennik {code} zgodny tylko częściowo"))
    if context.consent == "confirmed":
        signals.append(_positive("consent_confirmed", "Klient zgodził się na zamiennik"))
    elif context.consent == "unconfirmed":
        signals.append(_risk("consent_unconfirmed", "Brak potwierdzenia zgody na zamiennik"))
    if context.history == "accepted_before":
        signals.append(_positive("history_accepted", "Klient przyjmował już zamienniki"))
    elif context.history == "declined_before":
        signals.append(_risk("history_declined", "Klient odrzucał już zamienniki"))
    elif context.history == "no_substitute_history":
        signals.append(_info("history_none", "Klient nie dostawał dotąd zamienników"))
    elif context.history == "mixed":
        signals.append(_info("history_mixed", "Klient raz przyjmował, raz odrzucał zamienniki"))
    return signals


def _check_signals(uses: frozenset[Capability], context: ConfidenceContext) -> list[Signal]:
    """Failed, skipped or unplanned checks: a risk when the option uses them, else info.

    Substitute checks left out because the customer refused substitutes give no signal.
    """
    signals: list[Signal] = []
    for capability in CAPABILITIES:
        label = CAPABILITY_LABELS[capability]
        status = context.task_statuses.get(capability)
        if status == "completed":
            continue
        if status is None:
            if context.consent == "refused" and capability in SUBSTITUTE_CAPABILITIES:
                continue
            problem, text = "not_checked", f"Nie sprawdzono: {label}"
        else:
            problem, text = "task_failed", f"Nie udało się sprawdzić: {label}"
        if capability in uses:
            signals.append(_risk(f"{problem}:{capability}", text))
        else:
            text = f"Alternatywy nie sprawdzono: {label}"
            signals.append(_info(f"alternative_not_checked:{capability}", text))
    return signals


def band_of(signals: Sequence[Signal]) -> ConfidenceBand:
    risks = {s.code for s in signals if s.polarity == "risk"}
    if risks & LOW_RISKS:
        return "LOW"
    return "MEDIUM" if risks else "HIGH"


def assess(
    option: RecommendationOption, context: ConfidenceContext
) -> tuple[ConfidenceBand, list[Signal]]:
    """The band and signals of an option; its own `band` and `signals` are ignored."""
    signals: list[Signal] = []
    if option.covered_quantity >= option.requested_quantity:
        signals.append(_positive("full_coverage", "Pokrywa całą zamówioną ilość"))
    else:
        signals.append(
            _risk(
                "incomplete_coverage",
                f"Pokrywa {option.covered_quantity} z {option.requested_quantity} szt.",
            )
        )
    if context.deadline is None:
        signals.append(_info("no_deadline", "Zapytanie bez terminu"))
    elif option.fulfilled_on <= context.deadline:
        signals.append(_positive("deadline_met", "Realizacja w terminie klienta"))
    else:
        signals.append(
            _risk(
                "deadline_missed",
                f"Realizacja {option.fulfilled_on.isoformat()} po terminie "
                f"{context.deadline.isoformat()}",
            )
        )

    substitute_codes = [
        line.product_code for line in option.lines if line.source == "substitute_stock"
    ]
    has_supplier = any(line.source == "supplier" for line in option.lines)
    for code in substitute_codes:
        signals.extend(_substitute_signals(code, context))
    if option.kind == "combined":
        signals.append(
            _risk("two_sources", "Brak uzupełniany z dwóch źródeł: zamiennik i dostawca")
        )
    for field in context.uncertain_inputs:
        signals.append(
            _risk(
                f"uncertain_input:{field}",
                f"Niepewne pole analizy: {INPUT_LABELS.get(field, field)}",
            )
        )

    uses: frozenset[Capability] = frozenset()
    if substitute_codes:
        uses |= SUBSTITUTE_USES
    if has_supplier:
        uses |= SUPPLIER_USES
    signals.extend(_check_signals(uses, context))
    return band_of(signals), signals
