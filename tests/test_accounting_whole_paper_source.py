import json
from itertools import combinations
from pathlib import Path

import pytest
from aqaaccountgen.case_data import (
    IncomeStatementCase,
    NonCurrentAssetCase,
    PartnershipCase,
    SalesLedgerCase,
)
from aqaaccountgen.cli import _LIVE_ADAPTER

from Backend.Core import assessment_package as packages
from Backend.Core.whole_paper_review import (
    WHOLE_PAPER_REVIEW_V1,
    ReviewedPaper,
    _addressed_payload,
    _cross_item_windows,
    _review_payload,
    _within_item_windows,
)


@pytest.fixture
def paper():
    syllabus = _LIVE_ADAPTER.load_syllabus(
        Path("Resources/accounting/aqa/generator/data/syllabus.json")
    )
    return _LIVE_ADAPTER.build(_LIVE_ADAPTER.load_rule("1"), syllabus, 26080100)


def _stored_blueprint(paper):
    return json.loads(json.dumps(paper.model_dump(mode="json"), sort_keys=True))


def test_sales_journal_is_visible_only_to_its_owned_review_items(paper):
    option = paper.sections[0].options[0]
    sales = SalesLedgerCase.from_chart_values(option.title, option.chart_values)
    family = {"subject": "accounting_aqa", "paper_number": "1"}
    reviewed = packages.whole_paper_review_items(paper, **family)
    legacy = packages.whole_paper_review_items(
        _stored_blueprint(paper), **family, policy=WHOLE_PAPER_REVIEW_V1
    )
    changed = {
        after.id.split("@", 1)[0]: after
        for before, after in zip(legacy, reviewed, strict=True)
        if before != after
    }
    assert {"13.1", "13.2"} <= set(changed)
    assert not ({"01", "11"} & set(changed))
    for item in (changed["13.1"], changed["13.2"]):
        visible = "\n".join(item.context)
        assert "Sales journal" in visible
        assert f"£{sales.credit_sales:,}" in visible
        assert f"£{sales.sales_returns:,}" in visible
        assert f"£{sales.net_sales:,}" not in visible
        assert f"£{sales.closing_receivables:,}" not in visible
    assert _review_payload(reviewed) != _review_payload(legacy)


def test_staged_review_can_cover_every_pair_with_printed_sources(paper):
    reviewed = packages.whole_paper_review_items(
        paper, subject="accounting_aqa", paper_number="1"
    )
    cross = _cross_item_windows(reviewed)
    within = _within_item_windows(reviewed)
    by_id = {item.id for item in reviewed}
    assert {
        source.item_id for window in within for source in window.references.values()
    } == by_id
    prompt_pairs = set()
    exposure_pairs = set()
    for window in cross:
        if "answer_leakage" in window.kinds:
            exposure_pairs.update(
                (a, b)
                for a, first in window.references.items()
                for b, second in window.references.items()
                if first.field != "mark_scheme"
                and second.field == "mark_scheme"
                and first.item_id != second.item_id
            )
        if "duplicate_demand" not in window.kinds:
            continue
        owners = {
            source.item_id
            for source in window.references.values()
            if source.field == "prompt"
        }
        prompt_pairs.update(frozenset(pair) for pair in combinations(owners, 2))
    assert prompt_pairs == {frozenset(pair) for pair in combinations(by_id, 2)}
    _, references = _addressed_payload(reviewed)
    assert exposure_pairs == {
        (a, b)
        for a, first in references.items()
        for b, second in references.items()
        if first.field != "mark_scheme"
        and second.field == "mark_scheme"
        and first.item_id != second.item_id
    }


def test_assets_and_income_statement_use_the_actual_printed_inputs(paper):
    section_a = paper.sections[0].options[0]
    section_b = paper.sections[1].options[0]
    assets = NonCurrentAssetCase.from_chart_values(
        section_a.title, section_a.chart_values
    )
    income = IncomeStatementCase.from_chart_values(
        section_b.title, section_b.chart_values
    )
    items = {
        item.id.split("@", 1)[0]: "\n".join(item.context)
        for item in packages.whole_paper_review_items(
            paper, subject="accounting_aqa", paper_number="1"
        )
    }
    assert f"£{assets.plant_purchase:,}" in items["12"]
    assert "reducing-balance method" in items["12"]
    assert items["14.1"] == items["14.2"]
    for key in ("14.1", "14.2"):
        assert f"£{income.supplier_invoice:,}" in items[key]
        assert f"£{income.revenue:,}" in items[key]
        assert f"£{income.profit_for_year:,}" not in items[key]
    for unrelated in ("11", "13.1", "15.1"):
        assert f"£{income.supplier_invoice:,}" not in items[unrelated]


def test_partnership_context_follows_the_printed_question_dependencies(paper):
    option = paper.sections[1].options[0]
    case = PartnershipCase.from_chart_values(option.chart_values)
    items = {
        item.id.split("@", 1)[0]: "\n".join(item.context)
        for item in packages.whole_paper_review_items(
            paper, subject="accounting_aqa", paper_number="1"
        )
    }
    for key in ("15.1", "15.2", "15.3"):
        assert f"£{case.goodwill:,}" in items[key]
        assert f"£{case.cash_withdrawn['Alex']:,}" not in items[key]
    assert f"£{case.profit_for_year:,}" not in items["15.1"]
    for key in ("15.2", "15.3"):
        assert f"£{case.profit_for_year:,}" in items[key]
        assert "closing balances from 15.1" in items[key]
    assert f"£{case.goodwill:,}" not in items["14.1"]


def test_decision_cases_only_expose_their_published_inputs(paper):
    option = paper.sections[2].options[0]
    option.questions[0].authoring_context["verified_answers"] = {
        "private": "not printed system answer"
    }
    source = option.questions[1].authoring_context["candidate_source"]
    source["market_data"]["private_calculation"] = "not printed market answer"
    items = {
        item.id.split("@", 1)[0]: "\n".join(item.context)
        for item in packages.whole_paper_review_items(
            paper, subject="accounting_aqa", paper_number="1"
        )
    }
    assert "subscription increases" in items["16"]
    assert "buyback" not in items["16"]
    assert "not printed system answer" not in items["16"]
    assert "equipment" in items["17"]
    assert source["comparator"]["name"] in items["17"]
    assert "not printed market answer" not in items["17"]
    assert "subscription increases" not in items["17"]


def test_package_receipt_requires_current_source_for_current_publication(
    paper, tmp_path, monkeypatch
):
    # This seeded fixture does not use live model difficulty calibration.
    monkeypatch.setattr(packages, "_reference_demand_audit", lambda **kwargs: None)
    path = tmp_path / "receipt.json"
    family = {"subject": "accounting_aqa", "paper_number": "1"}
    identity = dict(**family, preview=False, provider="fixture", model="fixture")
    current = ReviewedPaper(packages.whole_paper_review_items(paper, **family), ())
    legacy = ReviewedPaper(
        packages.whole_paper_review_items(
            _stored_blueprint(paper), **family, policy=WHOLE_PAPER_REVIEW_V1
        ),
        (),
    )
    with pytest.raises(ValueError, match="review evidence"):
        packages.write_assessment_package(
            paper, path, **identity, whole_paper_review=legacy
        )
    assert not path.exists()
    packages.write_assessment_package(
        paper, path, **identity, whole_paper_review=current
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    receipt = document["whole_paper_review"]
    assert receipt["policy"] != WHOLE_PAPER_REVIEW_V1
    packages.validate_assessment_package(
        path, **identity, require_whole_paper_review=True
    )

    def write_receipt(value):
        document["whole_paper_review"] = value
        path.write_text(json.dumps(document), encoding="utf-8")

    write_receipt(legacy.receipt())
    original = path.read_bytes()
    packages.validate_assessment_package(path, **identity)
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="review evidence"):
        packages.validate_assessment_package(
            path, **identity, require_whole_paper_review=True
        )
    for altered in (
        {**receipt, "policy": "unknown"},
        {
            **receipt,
            "reviewed_content_sha256": legacy.receipt()["reviewed_content_sha256"],
        },
    ):
        write_receipt(altered)
        with pytest.raises(ValueError, match="review evidence"):
            packages.validate_assessment_package(path, **identity)
