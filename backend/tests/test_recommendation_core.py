"""Recommendation core on in-memory data: options, pricing, signals, bands, the rule-based
choice and choice validation. No database, no model."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.orchestration.schema import (
    AgentResult,
    Capability,
    CustomerHistoryResult,
    HistorySignal,
    SubstituteAvailabilityResult,
    SubstituteCandidate,
    SubstituteCompatibilityResult,
    SubstituteStock,
    SupplierAvailabilityResult,
    SupplierDelivery,
    TaskOutcome,
    TaskStatus,
)
from app.recommendation.options import (
    PricedProduct,
    RecommendationInputs,
    build_options,
    recommendation_facts,
)
from app.recommendation.recommender import (
    ChoiceRejected,
    FakeRecommender,
    RecommenderNotConfigured,
    UnconfiguredRecommender,
    get_recommender,
    validate_choice,
)
from app.recommendation.schema import (
    RecommendationOption,
    RecommendationResult,
    RecommenderChoice,
)
from app.settings import Settings

# Seed data (migrations 0006, 0007, 0009).
ABC_100 = PricedProduct("ABC-100", "Czujnik ciśnienia ABC-100", Decimal("120.00"), Decimal("84.00"))
ABC_110 = PricedProduct("ABC-110", "Czujnik ciśnienia ABC-110", Decimal("125.00"), Decimal("90.00"))
XYZ_300 = PricedProduct(
    "XYZ-300", "Zawór proporcjonalny XYZ-300", Decimal("240.00"), Decimal("170.00")
)
XYZ_310 = PricedProduct(
    "XYZ-310", "Zawór proporcjonalny XYZ-310", Decimal("250.00"), Decimal("180.00")
)
PRODUCTS = {p.code: p for p in (ABC_100, ABC_110, XYZ_300, XYZ_310)}
SUPPLIER_COSTS = {
    ("Sensortech Polska", "ABC-100"): Decimal("96.00"),
    ("Hydro-Valve", "XYZ-300"): Decimal("185.00"),
}
SENSORTECH = "Sensortech Polska"
HYDRO_VALVE = "Hydro-Valve"


# --- Builders ---------------------------------------------------------------------------


def _task(
    capability: Capability, result: AgentResult | None, status: TaskStatus = "completed"
) -> TaskOutcome:
    return TaskOutcome(
        capability=capability,
        agent="test-agent",
        reason="test",
        depends_on=["substitute-compatibility"] if capability == "substitute-availability" else [],
        stage=2 if capability == "substitute-availability" else 1,
        status=status,
        steps=[] if status == "skipped" else [f"agent:{capability}"],
        error_type="RuntimeError" if status == "failed" else None,
        result=result if status == "completed" else None,
    )


def _compatibility(code: str, compatibility: str = "full") -> TaskOutcome:
    candidate = SubstituteCandidate.model_validate(
        {"code": code, "name": PRODUCTS[code].name, "compatibility": compatibility, "note": "n"}
    )
    return _task("substitute-compatibility", SubstituteCompatibilityResult(candidates=[candidate]))


def _availability(code: str, stock: int, shortage: int) -> TaskOutcome:
    candidate = SubstituteStock(code=code, stock=stock, covers_shortage=stock >= shortage)
    return _task("substitute-availability", SubstituteAvailabilityResult(candidates=[candidate]))


def _supplier(
    supplier: str,
    quantity: int,
    lead_time_days: int,
    *,
    reference_date: date,
    deadline: date | None,
    shortage: int,
) -> TaskOutcome:
    available_on = date.fromordinal(reference_date.toordinal() + lead_time_days)
    offer = SupplierDelivery(
        supplier=supplier,
        quantity=quantity,
        lead_time_days=lead_time_days,
        available_on=available_on,
        meets_deadline=None if deadline is None else available_on <= deadline,
        covers_shortage=quantity >= shortage,
    )
    return _task("supplier-availability", SupplierAvailabilityResult(offers=[offer]))


def _history(signal: HistorySignal) -> TaskOutcome:
    return _task(
        "customer-history",
        CustomerHistoryResult(
            orders_count=1, substitutes_offered=1, substitutes_accepted=0, signal=signal
        ),
    )


ACME_REFERENCE = date(2026, 11, 2)
ACME_DEADLINE = date(2026, 11, 6)
OMEGA_REFERENCE = date(2026, 11, 5)
OMEGA_DEADLINE = date(2026, 11, 12)
DELTA_REFERENCE = date(2026, 11, 3)


def _acme(**changes: object) -> RecommendationInputs:
    """ACME 80x ABC-100 by 2026-11-06, consent confirmed, 5% discount."""
    inputs = RecommendationInputs(
        product=ABC_100,
        requested=80,
        available=50,
        shortage=30,
        deadline=ACME_DEADLINE,
        reference_date=ACME_REFERENCE,
        consent="confirmed",
        discount_percent=Decimal("5.00"),
        products_by_code=PRODUCTS,
        supplier_costs=SUPPLIER_COSTS,
        tasks=[
            _compatibility("ABC-110"),
            _availability("ABC-110", 40, 30),
            _supplier(
                SENSORTECH,
                200,
                7,
                reference_date=ACME_REFERENCE,
                deadline=ACME_DEADLINE,
                shortage=30,
            ),
            _history("accepted_before"),
        ],
    )
    return replace(inputs, **changes)  # type: ignore[arg-type]


def _omega(**changes: object) -> RecommendationInputs:
    """Omega 120x XYZ-300 by 2026-11-12, consent refused, 3% discount."""
    inputs = RecommendationInputs(
        product=XYZ_300,
        requested=120,
        available=60,
        shortage=60,
        deadline=OMEGA_DEADLINE,
        reference_date=OMEGA_REFERENCE,
        consent="refused",
        discount_percent=Decimal("3.00"),
        products_by_code=PRODUCTS,
        supplier_costs=SUPPLIER_COSTS,
        tasks=[
            _supplier(
                HYDRO_VALVE,
                80,
                5,
                reference_date=OMEGA_REFERENCE,
                deadline=OMEGA_DEADLINE,
                shortage=60,
            ),
            _history("declined_before"),
        ],
    )
    return replace(inputs, **changes)  # type: ignore[arg-type]


def _delta(**changes: object) -> RecommendationInputs:
    """Delta 500x ABC-100 without a deadline, consent unconfirmed, 10% discount."""
    inputs = RecommendationInputs(
        product=ABC_100,
        requested=500,
        available=50,
        shortage=450,
        deadline=None,
        reference_date=DELTA_REFERENCE,
        consent="unconfirmed",
        discount_percent=Decimal("10.00"),
        products_by_code=PRODUCTS,
        supplier_costs=SUPPLIER_COSTS,
        tasks=[
            _compatibility("ABC-110"),
            _availability("ABC-110", 40, 450),
            _supplier(
                SENSORTECH, 200, 7, reference_date=DELTA_REFERENCE, deadline=None, shortage=450
            ),
            _history("no_substitute_history"),
        ],
    )
    return replace(inputs, **changes)  # type: ignore[arg-type]


def _by_id(options: list[RecommendationOption]) -> dict[str, RecommendationOption]:
    return {o.id: o for o in options}


def _codes(option: RecommendationOption, polarity: str | None = None) -> list[str]:
    return [s.code for s in option.signals if polarity is None or s.polarity == polarity]


def _choose(inputs: RecommendationInputs) -> tuple[RecommendationOption, RecommenderChoice]:
    options = build_options(inputs)
    choice = FakeRecommender().choose(recommendation_facts(inputs), options).choice
    validate_choice(choice, options)
    return _by_id(options)[choice.option_id], choice


# --- Seed scenarios ---------------------------------------------------------------------


def test_acme_takes_the_substitute() -> None:
    options = build_options(_acme())

    assert [o.id for o in options] == ["stock", "stock+ABC-110", f"stock+supplier:{SENSORTECH}"]
    by_id = _by_id(options)
    assert {o.id: (o.kind, o.band) for o in options} == {
        "stock": ("partial_delivery", "LOW"),
        "stock+ABC-110": ("substitute", "HIGH"),
        f"stock+supplier:{SENSORTECH}": ("other_source", "LOW"),
    }
    substitute = by_id["stock+ABC-110"]
    assert [(line.product_code, line.source, line.quantity) for line in substitute.lines] == [
        ("ABC-100", "stock", 50),
        ("ABC-110", "substitute_stock", 30),
    ]
    assert [line.unit_price for line in substitute.lines] == [
        Decimal("114.00"),
        Decimal("118.75"),
    ]
    assert (substitute.value, substitute.cost) == (Decimal("9262.50"), Decimal("6900.00"))
    assert substitute.margin_percent == Decimal("25.51")
    assert (substitute.covered_quantity, substitute.requested_quantity) == (80, 80)
    assert (substitute.fulfilled_on, substitute.meets_deadline) == (ACME_REFERENCE, True)
    assert _codes(substitute, "positive") == [
        "full_coverage",
        "deadline_met",
        "compat_full",
        "consent_confirmed",
        "history_accepted",
    ]
    assert _codes(substitute, "risk") == []

    supplier = by_id[f"stock+supplier:{SENSORTECH}"]
    assert supplier.fulfilled_on == date(2026, 11, 9)
    assert supplier.meets_deadline is False
    assert "deadline_missed" in _codes(supplier, "risk")

    chosen, choice = _choose(_acme())
    assert chosen.id == "stock+ABC-110"
    assert choice.cited_signals == _codes(chosen, "positive")


def test_omega_takes_the_supplier() -> None:
    options = build_options(_omega())

    assert [o.id for o in options] == ["stock", f"stock+supplier:{HYDRO_VALVE}"]
    chosen, _ = _choose(_omega())
    assert chosen.id == f"stock+supplier:{HYDRO_VALVE}"
    assert chosen.kind == "other_source"
    assert chosen.band == "HIGH"
    assert [(line.source, line.supplier, line.quantity) for line in chosen.lines] == [
        ("stock", None, 60),
        ("supplier", HYDRO_VALVE, 60),
    ]
    assert chosen.lines[1].available_on == date(2026, 11, 10)
    assert all(line.unit_price == Decimal("232.80") for line in chosen.lines)
    assert (chosen.value, chosen.cost) == (Decimal("27936.00"), Decimal("21300.00"))
    assert chosen.margin_percent == Decimal("23.75")
    assert (chosen.covered_quantity, chosen.fulfilled_on) == (120, date(2026, 11, 10))
    # Refused substitutes are not "not checked", and history does not concern this option.
    assert _codes(chosen) == ["full_coverage", "deadline_met"]


def test_delta_takes_the_combined_option_with_low_confidence() -> None:
    options = build_options(_delta())

    combined_id = f"stock+ABC-110+supplier:{SENSORTECH}"
    assert [o.id for o in options] == [
        "stock",
        "stock+ABC-110",
        f"stock+supplier:{SENSORTECH}",
        combined_id,
    ]
    assert {o.band for o in options} == {"LOW"}
    chosen, choice = _choose(_delta())
    assert chosen.id == combined_id
    assert chosen.kind == "combined"
    assert [(line.source, line.quantity) for line in chosen.lines] == [
        ("stock", 50),
        ("substitute_stock", 40),
        ("supplier", 200),
    ]
    assert (chosen.covered_quantity, chosen.requested_quantity) == (290, 500)
    assert (chosen.value, chosen.cost) == (Decimal("31500.00"), Decimal("27000.00"))
    assert chosen.margin_percent == Decimal("14.29")
    assert chosen.meets_deadline is None
    assert _codes(chosen, "risk") == ["incomplete_coverage", "consent_unconfirmed", "two_sources"]
    assert _codes(chosen, "info") == ["no_deadline", "history_none"]
    assert set(choice.cited_signals) == set(_codes(chosen, "positive") + _codes(chosen, "risk"))


def test_combined_only_when_neither_source_covers_alone() -> None:
    # ACME: the substitute covers the 30 missing on its own.
    assert all(o.kind != "combined" for o in build_options(_acme()))


# --- Consent and task states ------------------------------------------------------------


def test_refused_consent_gives_no_substitute_option() -> None:
    options = build_options(_acme(consent="refused"))

    assert [o.id for o in options] == ["stock", f"stock+supplier:{SENSORTECH}"]
    for option in options:
        assert not any(code.startswith("consent_") for code in _codes(option))


@pytest.mark.parametrize(
    ("compatibility_status", "availability_status"),
    [("failed", "skipped"), ("completed", "failed")],
)
def test_failed_substitute_task_removes_substitute_options(
    compatibility_status: TaskStatus, availability_status: TaskStatus
) -> None:
    base = _acme()
    tasks = [
        _task(t.capability, t.result, compatibility_status)
        if t.capability == "substitute-compatibility"
        else _task(t.capability, t.result, availability_status)
        if t.capability == "substitute-availability"
        else t
        for t in base.tasks
    ]
    options = build_options(replace(base, tasks=tasks))

    assert [o.id for o in options] == ["stock", f"stock+supplier:{SENSORTECH}"]
    stock = options[0]
    info = _codes(stock, "info")
    assert "alternative_not_checked:substitute-availability" in info
    if compatibility_status == "failed":
        assert "alternative_not_checked:substitute-compatibility" in info


def test_failed_history_task_is_a_risk_of_the_substitute_option() -> None:
    base = _acme()
    tasks = [
        _task("customer-history", None, "failed") if t.capability == "customer-history" else t
        for t in base.tasks
    ]
    by_id = _by_id(build_options(replace(base, tasks=tasks)))

    substitute = by_id["stock+ABC-110"]
    assert "task_failed:customer-history" in _codes(substitute, "risk")
    assert "history_accepted" not in _codes(substitute)
    assert substitute.band == "MEDIUM"
    # The supplier option does not rely on the history.
    assert "alternative_not_checked:customer-history" in _codes(
        by_id[f"stock+supplier:{SENSORTECH}"], "info"
    )


def test_unplanned_supplier_check_keeps_the_substitute_high() -> None:
    base = _acme()
    tasks = [t for t in base.tasks if t.capability != "supplier-availability"]
    options = build_options(replace(base, tasks=tasks))

    assert [o.id for o in options] == ["stock", "stock+ABC-110"]
    substitute = options[1]
    assert substitute.band == "HIGH"
    assert "alternative_not_checked:supplier-availability" in _codes(substitute, "info")
    assert not any(code.startswith("not_checked") for code in _codes(substitute))


def test_unplanned_check_is_a_risk_only_where_it_is_used() -> None:
    base = _acme(deadline=None)
    tasks = [t for t in base.tasks if t.capability != "customer-history"]
    by_id = _by_id(build_options(replace(base, tasks=tasks)))

    substitute = by_id["stock+ABC-110"]
    assert "not_checked:customer-history" in _codes(substitute, "risk")
    assert substitute.band == "MEDIUM"
    supplier = by_id[f"stock+supplier:{SENSORTECH}"]
    assert "alternative_not_checked:customer-history" in _codes(supplier, "info")
    assert supplier.band == "HIGH"


def test_supplier_task_failure_is_a_risk_of_supplier_options_only() -> None:
    delta = _delta()
    tasks = [
        _task("supplier-availability", None, "failed")
        if t.capability == "supplier-availability"
        else t
        for t in delta.tasks
    ]
    options = build_options(replace(delta, tasks=tasks))

    assert [o.id for o in options] == ["stock", "stock+ABC-110"]
    assert "alternative_not_checked:supplier-availability" in _codes(options[1], "info")


# --- Option building --------------------------------------------------------------------


def test_no_own_stock_gives_no_stock_option() -> None:
    options = build_options(_acme(available=0, shortage=80))

    assert [o.id for o in options] == ["ABC-110", f"supplier:{SENSORTECH}"]
    substitute = options[0]
    assert [(line.source, line.quantity) for line in substitute.lines] == [("substitute_stock", 40)]
    assert substitute.covered_quantity == 40
    assert all(line.source != "stock" for o in options for line in o.lines)


def test_no_own_stock_and_no_alternatives_gives_no_options() -> None:
    assert build_options(_acme(available=0, shortage=80, tasks=[])) == []


def test_substitute_unknown_to_the_catalogue_is_skipped() -> None:
    options = build_options(_acme(products_by_code={}))

    assert [o.id for o in options] == ["stock", f"stock+supplier:{SENSORTECH}"]


def test_supplier_offer_without_cost_is_skipped() -> None:
    options = build_options(_acme(supplier_costs={}))

    assert [o.id for o in options] == ["stock", "stock+ABC-110"]


# --- Signals and bands ------------------------------------------------------------------


def test_partial_compatibility_caps_the_band_at_medium() -> None:
    omega = _omega(consent="confirmed")
    tasks = [
        _compatibility("XYZ-310", "partial"),
        _availability("XYZ-310", 100, 60),
        *omega.tasks,
    ]
    by_id = _by_id(build_options(replace(omega, tasks=tasks)))

    substitute = by_id["stock+XYZ-310"]
    assert substitute.covered_quantity == 120
    assert substitute.meets_deadline is True
    assert "compat_partial" in _codes(substitute, "risk")
    assert substitute.band == "MEDIUM"


def test_no_deadline_does_not_lower_the_band() -> None:
    by_id = _by_id(build_options(_acme(deadline=None)))

    substitute = by_id["stock+ABC-110"]
    assert substitute.meets_deadline is None
    assert "no_deadline" in _codes(substitute, "info")
    assert substitute.band == "HIGH"
    assert by_id[f"stock+supplier:{SENSORTECH}"].band == "HIGH"


def test_date_equal_to_the_deadline_meets_it() -> None:
    by_id = _by_id(build_options(_acme(deadline=date(2026, 11, 9))))

    supplier = by_id[f"stock+supplier:{SENSORTECH}"]
    assert supplier.fulfilled_on == date(2026, 11, 9)
    assert supplier.meets_deadline is True
    assert "deadline_met" in _codes(supplier, "positive")
    assert supplier.band == "HIGH"


def test_covered_equal_to_requested_is_full_coverage() -> None:
    # 40 own + 40 substitute pcs: covered == requested.
    by_id = _by_id(build_options(_acme(available=40, shortage=40)))

    substitute = by_id["stock+ABC-110"]
    assert substitute.covered_quantity == substitute.requested_quantity == 80
    assert "full_coverage" in _codes(substitute, "positive")
    assert "incomplete_coverage" not in _codes(substitute)


def test_uncertain_input_is_a_risk_of_every_option() -> None:
    options = build_options(_acme(uncertain_inputs=["quantity"]))

    for option in options:
        assert "uncertain_input:quantity" in _codes(option, "risk")
    assert _by_id(options)["stock+ABC-110"].band == "MEDIUM"


def test_declined_history_is_a_risk_of_the_substitute_option() -> None:
    base = _acme()
    tasks = [
        _history("declined_before") if t.capability == "customer-history" else t for t in base.tasks
    ]
    substitute = _by_id(build_options(replace(base, tasks=tasks)))["stock+ABC-110"]

    assert "history_declined" in _codes(substitute, "risk")
    assert substitute.band == "MEDIUM"


def test_every_signal_has_a_label() -> None:
    for option in build_options(_delta(uncertain_inputs=["customer"])):
        assert all(signal.label for signal in option.signals)


# --- Choice -----------------------------------------------------------------------------


def test_fake_ranking_breaks_a_coverage_tie_by_date() -> None:
    # Without a deadline both full-coverage options are HIGH; the substitute is earlier.
    chosen, choice = _choose(_acme(deadline=None))

    assert chosen.id == "stock+ABC-110"
    assert choice.justification.startswith("Wybrano opcję stock+ABC-110")
    assert "no_deadline" not in choice.cited_signals


def test_fake_recommender_names() -> None:
    recommender = FakeRecommender()

    assert (recommender.name, recommender.step_kind) == ("rule-based", "deterministic")


def test_validate_choice_accepts_the_options_signals() -> None:
    options = build_options(_acme())
    validate_choice(
        RecommenderChoice(
            option_id="stock+ABC-110",
            justification="Zamiennik w terminie.",
            cited_signals=["compat_full", "deadline_met"],
        ),
        options,
    )


@pytest.mark.parametrize(
    ("choice", "code"),
    [
        (
            RecommenderChoice(option_id="stock+XYZ-999", justification="x", cited_signals=[]),
            "unknown_option",
        ),
        (
            # deadline_missed belongs to the supplier option, not to the substitute.
            RecommenderChoice(
                option_id="stock+ABC-110", justification="x", cited_signals=["deadline_missed"]
            ),
            "foreign_signal",
        ),
        (
            RecommenderChoice(option_id="stock+ABC-110", justification="  ", cited_signals=[]),
            "empty_justification",
        ),
    ],
)
def test_validate_choice_rejects(choice: RecommenderChoice, code: str) -> None:
    with pytest.raises(ChoiceRejected) as raised:
        validate_choice(choice, build_options(_acme()))
    assert raised.value.code == code


# --- Factory and stored shape -----------------------------------------------------------


def test_get_recommender_fake_is_rule_based() -> None:
    assert isinstance(get_recommender(Settings(llm_provider="fake")), FakeRecommender)


@pytest.mark.parametrize("provider", ["groq", "openrouter"])
def test_get_recommender_without_key_is_not_configured(provider: str) -> None:
    recommender = get_recommender(
        Settings.model_validate({"llm_provider": provider, "llm_api_key": ""})
    )

    assert isinstance(recommender, UnconfiguredRecommender)
    assert (recommender.name, recommender.step_kind) == (provider, "llm")
    with pytest.raises(RecommenderNotConfigured) as raised:
        recommender.choose(recommendation_facts(_acme()), build_options(_acme()))
    assert raised.value.transient is False


def test_result_round_trips_through_json_with_decimal_strings() -> None:
    options = build_options(_acme())
    choice = FakeRecommender().choose(recommendation_facts(_acme()), options).choice
    result = RecommendationResult(recommender="rule-based", options=options, choice=choice)

    dumped = result.model_dump(mode="json")
    substitute = next(o for o in dumped["options"] if o["id"] == "stock+ABC-110")
    assert substitute["margin_percent"] == "25.51"
    assert substitute["lines"][1]["unit_price"] == "118.75"
    assert RecommendationResult.model_validate(dumped) == result


def test_facts_carry_the_customer_history_signal() -> None:
    assert recommendation_facts(_acme()).customer_history == "accepted_before"
    assert recommendation_facts(_omega()).customer_history == "declined_before"
    without_history = [t for t in _acme().tasks if t.capability != "customer-history"]
    assert recommendation_facts(_acme(tasks=without_history)).customer_history is None
