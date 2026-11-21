"""Recompute bounded Accounting choice contracts from public facts."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ACCOUNTING_SELECTED_RESPONSE_VERSION = "accounting-selected-response-v1"
AccountingOperation = Literal[
    "carriage_gross_profit",
    "sale_or_return_gross_profit",
    "credit_sale_correction",
    "net_share_premium",
    "cash_budget_balance",
    "contribution_per_unit",
    "material_variance_classification",
    "prime_entry_book",
    "liquidity_ratio_definition",
]
AccountingUnit = Literal["GBP", "entry_pair", "classification"]
_DECIMAL = re.compile(r"[0-9]{1,12}(?:\.[0-9]{1,4})?\Z")
_WHOLE_POUNDS = re.compile(r"(?:£0|-?£[1-9][0-9]{0,2}(?:,[0-9]{3})*)\Z")


class AccountingSelectedResponseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    version: Literal["accounting-selected-response-v1"]
    subject: Literal["accounting"]
    operation: AccountingOperation
    inputs: dict[str, str] = Field(min_length=1, max_length=10)
    unit: AccountingUnit


class MaterialVarianceFacts(BaseModel):
    """Qualitative public comparisons; purchases are not consumption evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    variance: Literal["price", "usage"]
    quantity_basis: Literal["purchased", "consumed"]
    quantity: Literal["positive"]
    comparison: Literal["below", "equal", "above"]


@dataclass(frozen=True)
class AccountingChoiceWorking:
    answer: str
    steps: tuple[str, ...]
    numeric_results: dict[str, float]
    journal_choices: tuple[str, ...] = ()
    classification_choices: tuple[str, ...] = ()
    paper_one_prompt: str | None = None
    maximum_reasoning_stages: int = 2


def pounds(value: Decimal) -> str:
    if not value.is_finite() or value != value.to_integral_value():
        raise ValueError("Accounting choice requires an exact whole-pound result")
    return f"-£{-value:,.0f}" if value < 0 else f"£{value:,.0f}"


def _values(
    contract: AccountingSelectedResponseContract, names: set[str]
) -> dict[str, Decimal]:
    if set(contract.inputs) != names:
        raise ValueError("Accounting choice has missing or unexpected public inputs")
    result = {}
    for name, text in contract.inputs.items():
        if not _DECIMAL.fullmatch(text):
            raise ValueError(
                f"Accounting public input {name} must be a finite nonnegative decimal"
            )
        result[name] = Decimal(text)
    return result


def _carriage(contract: AccountingSelectedResponseContract) -> AccountingChoiceWorking:
    v = _values(
        contract,
        {
            "revenue",
            "opening_inventory",
            "purchases",
            "purchase_returns",
            "carriage_inwards",
            "carriage_outwards",
            "closing_inventory",
        },
    )
    net_purchases = v["purchases"] - v["purchase_returns"]
    cost_of_sales = (
        v["opening_inventory"]
        + net_purchases
        + v["carriage_inwards"]
        - v["closing_inventory"]
    )
    if v["revenue"] <= 0 or net_purchases < 0 or cost_of_sales < 0:
        raise ValueError("Accounting gross-profit case has inconsistent public inputs")
    profit = v["revenue"] - cost_of_sales
    return AccountingChoiceWorking(
        pounds(profit),
        (
            f"Net purchases: {pounds(v['purchases'])} - {pounds(v['purchase_returns'])} = {pounds(net_purchases)}.",
            f"Cost of sales: {pounds(v['opening_inventory'])} + {pounds(net_purchases)} + {pounds(v['carriage_inwards'])} - {pounds(v['closing_inventory'])} = {pounds(cost_of_sales)}.",
            f"Carriage outwards is an expense after gross profit; gross profit is {pounds(v['revenue'])} - {pounds(cost_of_sales)} = {pounds(profit)}.",
        ),
        {
            "net_purchases": float(net_purchases),
            "cost_of_sales": float(cost_of_sales),
            "gross_profit": float(profit),
        },
        paper_one_prompt=(
            f"A sole trader reports revenue of {pounds(v['revenue'])}, opening inventory of "
            f"{pounds(v['opening_inventory'])}, purchases of {pounds(v['purchases'])}, purchase returns of "
            f"{pounds(v['purchase_returns'])} and closing inventory of {pounds(v['closing_inventory'])}. Carriage "
            f"inwards is {pounds(v['carriage_inwards'])} and carriage outwards is {pounds(v['carriage_outwards'])}. "
            "What is gross profit?"
        ),
        # Net purchases, cost of sales, then gross profit.
        maximum_reasoning_stages=3,
    )


def _sale_or_return(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    v = _values(
        contract,
        {
            "revenue",
            "opening_inventory",
            "purchases",
            "closing_inventory_excluding_return",
            "sale_or_return_selling_price",
            "markup_percent_on_cost",
        },
    )
    selling = v["sale_or_return_selling_price"]
    cost = selling / (1 + v["markup_percent_on_cost"] / 100)
    revenue = v["revenue"] - selling
    inventory = v["closing_inventory_excluding_return"] + cost
    cost_of_sales = v["opening_inventory"] + v["purchases"] - inventory
    if selling <= 0 or revenue < 0 or cost_of_sales < 0:
        raise ValueError(
            "Accounting sale-or-return case has inconsistent public inputs"
        )
    profit = revenue - cost_of_sales
    return AccountingChoiceWorking(
        pounds(profit),
        (
            f"The unapproved goods cost {pounds(selling)} / (1 + {v['markup_percent_on_cost']} / 100) = {pounds(cost)}.",
            f"Remove the unearned sale: revenue is {pounds(v['revenue'])} - {pounds(selling)} = {pounds(revenue)}.",
            f"Include goods still owned in closing inventory: {pounds(v['closing_inventory_excluding_return'])} + {pounds(cost)} = {pounds(inventory)}.",
            f"Cost of sales is {pounds(cost_of_sales)}; adjusted gross profit is {pounds(profit)}.",
        ),
        {
            "goods_cost": float(cost),
            "adjusted_revenue": float(revenue),
            "adjusted_inventory": float(inventory),
            "gross_profit": float(profit),
        },
        paper_one_prompt=(
            f"Revenue of {pounds(v['revenue'])} includes goods sent on sale or return for "
            f"{pounds(selling)} at a mark-up of {v['markup_percent_on_cost']}% on cost. The customer had "
            "not accepted them at the year end. Opening inventory is "
            f"{pounds(v['opening_inventory'])}, purchases are {pounds(v['purchases'])} and closing inventory "
            f"of {pounds(v['closing_inventory_excluding_return'])} excludes these goods. What is the corrected gross profit?"
        ),
        # Recover cost, correct revenue and inventory, then recompute profit.
        maximum_reasoning_stages=4,
    )


def _credit_sale(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    amount = _values(contract, {"credit_sale"})["credit_sale"]
    if amount <= 0:
        raise ValueError("Accounting credit sale must be positive")
    value = pounds(amount)
    answer = f"Debit trade receivables {value}; credit cash {value}"
    return AccountingChoiceWorking(
        answer,
        (
            "A credit sale requires a debit to trade receivables and a credit to sales; the recorded sales credit is already correct.",
            f"Transfer the incorrect cash debit to the receivable: {answer}.",
        ),
        {"correction_amount": float(amount)},
        (
            answer,
            f"Debit cash {value}; credit trade receivables {value}",
            f"Debit trade receivables {value}; credit sales {value}",
            f"Debit sales {value}; credit trade receivables {value}",
        ),
        paper_one_prompt=(
            f"A credit sale of {value} was recorded as a debit to cash and "
            "a credit to sales. Which journal entry corrects the error without "
            "recording the sale twice?"
        ),
    )


def _share_premium(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    v = _values(
        contract,
        {"shares_issued", "nominal_value_pence", "issue_price_pence", "issue_costs"},
    )
    shares = v["shares_issued"]
    nominal = v["nominal_value_pence"] / 100
    issue = v["issue_price_pence"] / 100
    gross_premium = shares * (issue - nominal)
    if (
        shares <= 0
        or shares != shares.to_integral_value()
        or nominal <= 0
        or issue <= nominal
        or v["issue_costs"] > gross_premium
    ):
        raise ValueError("Accounting share issue has inconsistent public inputs")
    premium = gross_premium - v["issue_costs"]
    return AccountingChoiceWorking(
        pounds(premium),
        (
            f"Convert the {v['nominal_value_pence']}p nominal value and {v['issue_price_pence']}p issue price to pounds before multiplying by shares.",
            f"Gross share premium: {shares:,.0f} x (£{issue} - £{nominal}) = {pounds(gross_premium)}.",
            f"Deduct the explicitly stated issue costs: {pounds(gross_premium)} - {pounds(v['issue_costs'])} = {pounds(premium)}.",
        ),
        {
            "gross_proceeds": float(shares * issue),
            "share_capital": float(shares * nominal),
            "net_share_premium": float(premium),
        },
        paper_one_prompt=(
            f"A company issues {shares:,.0f} ordinary shares with nominal value "
            f"{v['nominal_value_pence']}p for {v['issue_price_pence']}p each. Issue costs of {pounds(v['issue_costs'])} are "
            "deducted from share premium. What is the net increase in the share "
            "premium account?"
        ),
        # Convert units, calculate gross premium, then deduct issue costs.
        maximum_reasoning_stages=3,
    )


def _cash_budget(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    v = _values(contract, {"opening_balance", "receipts", "payments"})
    closing = v["opening_balance"] + v["receipts"] - v["payments"]
    return AccountingChoiceWorking(
        pounds(closing),
        (
            f"Add receipts to opening cash: {pounds(v['opening_balance'])} + {pounds(v['receipts'])}.",
            f"Deduct payments: closing cash is {pounds(closing)}.",
        ),
        {"closing_cash_balance": float(closing)},
    )


def _unit_contribution(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    v = _values(contract, {"selling_price", "variable_cost", "allocated_fixed_cost"})
    contribution = v["selling_price"] - v["variable_cost"]
    return AccountingChoiceWorking(
        pounds(contribution),
        (
            f"Subtract variable cost from selling price: {pounds(v['selling_price'])} - {pounds(v['variable_cost'])} = {pounds(contribution)} per unit.",
            f"Allocated fixed cost of {pounds(v['allocated_fixed_cost'])} per unit is not deducted when calculating contribution.",
        ),
        {"contribution_per_unit": float(contribution)},
    )


def _variance_facts(
    contract: AccountingSelectedResponseContract,
) -> MaterialVarianceFacts:
    facts = MaterialVarianceFacts.model_validate(contract.inputs)
    if facts.variance == "usage" and facts.quantity_basis != "consumed":
        raise ValueError(
            "Material usage variance requires actual consumption, not purchases"
        )
    return facts


def material_variance_prompt(raw: dict[str, Any]) -> str:
    """Render the exact public premise from the same facts used for derivation."""
    contract = AccountingSelectedResponseContract.model_validate(raw)
    if contract.operation != "material_variance_classification":
        raise ValueError("Material variance wording requires its own public contract")
    facts = _variance_facts(contract)
    if facts.variance == "price":
        verb = "buys" if facts.quantity_basis == "purchased" else "uses"
        comparison = "at" if facts.comparison == "equal" else facts.comparison
        return (
            f"A business {verb} a positive quantity of material {comparison} the standard price. "
            "What is the material price variance?"
        )
    comparison = "equal to" if facts.comparison == "equal" else facts.comparison
    return (
        f"A business uses a positive quantity of material {comparison} the standard "
        "quantity allowed for actual production. What is the material usage variance?"
    )


_PRIME_ENTRY_CASES = {
    "credit_purchase": (
        "A retailer receives an invoice for goods bought on credit for resale.",
        "Purchases journal",
    ),
    "credit_sale": (
        "A retailer sends a customer an invoice for goods sold on credit.",
        "Sales journal",
    ),
    "return_to_supplier": (
        "A retailer returns goods bought on credit and receives a credit note from its supplier.",
        "Purchases returns journal",
    ),
    "return_from_customer": (
        "A retailer accepts a return of goods sold on credit and sends the customer a credit note.",
        "Sales returns journal",
    ),
}
PRIME_ENTRY_TRANSACTIONS = tuple(_PRIME_ENTRY_CASES)


def _prime_entry_case(
    contract: AccountingSelectedResponseContract,
) -> tuple[str, str]:
    if contract.operation != "prime_entry_book" or set(contract.inputs) != {
        "transaction"
    }:
        raise ValueError("Prime entry requires exactly one public transaction")
    case = _PRIME_ENTRY_CASES.get(contract.inputs["transaction"])
    if case is None:
        raise ValueError("Unknown public prime-entry transaction")
    return case


def prime_entry_prompt(raw: dict[str, Any]) -> str:
    contract = AccountingSelectedResponseContract.model_validate(raw)
    event, _ = _prime_entry_case(contract)
    return f"{event} Which book of prime entry should the retailer use?"


def _prime_entry(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    event, answer = _prime_entry_case(contract)
    return AccountingChoiceWorking(
        answer,
        (
            event,
            f"Classify the transaction before posting to ledger accounts: {answer}.",
        ),
        {},
        classification_choices=tuple(book for _, book in _PRIME_ENTRY_CASES.values()),
    )


LIQUIDITY_INVENTORY_TREATMENTS = ("include", "exclude")
_LIQUIDITY_RATIO_CHOICES = (
    "Current ratio",
    "Liquid capital ratio (acid test ratio)",
    "Gross profit margin",
    "Capital gearing",
)


def _liquidity_ratio(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    if set(contract.inputs) != {"inventory_treatment"}:
        raise ValueError("Liquidity definition requires only the inventory treatment")
    treatment = contract.inputs["inventory_treatment"]
    if treatment not in LIQUIDITY_INVENTORY_TREATMENTS:
        raise ValueError("Unsupported liquidity inventory treatment")
    include = treatment == "include"
    answer = _LIQUIDITY_RATIO_CHOICES[0 if include else 1]
    if include:
        prompt = (
            "A supplier wants to compare a customer's total current assets with "
            "its current liabilities. Which ratio should the supplier use?"
        )
    else:
        prompt = (
            "A lender wants a measure of short-term liquidity that ignores "
            "inventory. Which ratio should the lender use?"
        )
    return AccountingChoiceWorking(
        answer,
        (
            "The current ratio uses all current assets; the liquid capital ratio removes inventory.",
            f"The requested inventory treatment therefore indicates the {answer.casefold()}.",
        ),
        {},
        classification_choices=_LIQUIDITY_RATIO_CHOICES,
        paper_one_prompt=prompt,
    )


def _material_variance(
    contract: AccountingSelectedResponseContract,
) -> AccountingChoiceWorking:
    facts = _variance_facts(contract)
    answer = {"below": "Favourable", "equal": "Zero", "above": "Adverse"}[
        facts.comparison
    ]
    basis = (
        "actual price with standard price"
        if facts.variance == "price"
        else "actual consumption with the standard allowance for actual production"
    )
    return AccountingChoiceWorking(
        answer,
        (
            f"The requested material {facts.variance} variance compares {basis}.",
            f"The actual value is {facts.comparison} its standard comparator for a positive quantity, giving a {answer.lower()} variance.",
        ),
        {},
        classification_choices=(
            "Favourable",
            "Adverse",
            "Zero",
            "Not measurable without the selling price",
        ),
    )


_OPERATIONS: dict[
    str,
    tuple[
        AccountingUnit,
        Callable[[AccountingSelectedResponseContract], AccountingChoiceWorking],
    ],
] = {
    "carriage_gross_profit": ("GBP", _carriage),
    "sale_or_return_gross_profit": ("GBP", _sale_or_return),
    "credit_sale_correction": ("entry_pair", _credit_sale),
    "net_share_premium": ("GBP", _share_premium),
    "cash_budget_balance": ("GBP", _cash_budget),
    "contribution_per_unit": ("GBP", _unit_contribution),
    "material_variance_classification": ("classification", _material_variance),
    "prime_entry_book": ("classification", _prime_entry),
    "liquidity_ratio_definition": ("classification", _liquidity_ratio),
}


def accounting_selected_response_contract(
    operation: AccountingOperation,
    inputs: dict[str, str],
) -> dict[str, Any]:
    unit, _ = _OPERATIONS[operation]
    return AccountingSelectedResponseContract(
        version=ACCOUNTING_SELECTED_RESPONSE_VERSION,
        subject="accounting",
        operation=operation,
        inputs=inputs,
        unit=unit,
    ).model_dump(mode="json")


def derive_accounting_choice(raw: dict[str, Any]) -> AccountingChoiceWorking:
    contract = AccountingSelectedResponseContract.model_validate(raw)
    unit, operation = _OPERATIONS[contract.operation]
    if contract.unit != unit:
        raise ValueError("Accounting selected-response output unit is inconsistent")
    return operation(contract)


def _checked_accounting_working(item: dict[str, Any]) -> AccountingChoiceWorking:
    context = item.get("authoring_context")
    if not isinstance(context, dict):
        raise ValueError("Accounting choice requires public authoring context")
    if (
        item.get("kind") != "multiple_choice"
        or type(item.get("marks")) is not int
        or item["marks"] != 1
    ):
        raise ValueError("Accounting choice requires a one-mark multiple-choice item")
    subject = item.get("subject") or context.get("objective_subject")
    if subject is not None and (
        not isinstance(subject, str)
        or subject
        not in {"accounting", "accounting_aqa", "Accounting", "aqa/accounting"}
    ):
        raise ValueError(
            "Accounting selected-response contract belongs to another subject"
        )
    raw = context.get("selected_response_contract")
    working = derive_accounting_choice(raw)
    if (
        working.paper_one_prompt is not None
        and item.get("prompt") != working.paper_one_prompt
    ):
        raise ValueError(
            "Accounting choice visible wording differs from its public facts"
        )
    if (
        isinstance(raw, dict)
        and raw.get("operation") == "material_variance_classification"
        and item.get("prompt") != material_variance_prompt(raw)
    ):
        raise ValueError(
            "Material variance visible wording differs from its public facts"
        )
    if raw["operation"] == "prime_entry_book" and item.get(
        "prompt"
    ) != prime_entry_prompt(raw):
        raise ValueError("Prime-entry visible wording differs from its public facts")
    choices = item.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) != 4
        or any(not isinstance(choice, str) or not choice.strip() for choice in choices)
    ):
        raise ValueError("Accounting choice requires four nonempty options")
    normalised = [" ".join(choice.casefold().split()) for choice in choices]
    if len(set(normalised)) != 4:
        raise ValueError("Accounting choice requires four distinct options")
    if working.journal_choices:
        if set(choices) != set(working.journal_choices):
            raise ValueError(
                "Accounting correction choices differ from the public journal case"
            )
    elif working.classification_choices:
        if set(choices) != set(working.classification_choices):
            raise ValueError(
                "Accounting choices differ from the public classification domain"
            )
    # The distractors only need a format check. Parsing them as decimals could
    # expand a short exponent into a very large string during currency formatting.
    elif any(_WHOLE_POUNDS.fullmatch(choice) is None for choice in choices):
        raise ValueError("Accounting numeric choice has an unsupported currency format")
    if choices.count(working.answer) != 1:
        raise ValueError("Accounting choice must contain exactly one derived answer")
    return working


def verified_paper_one_choice_ceiling(item: dict[str, Any]) -> int | None:
    context = item.get("authoring_context")
    if not isinstance(context, dict) or "selected_response_contract" not in context:
        return None
    working = _checked_accounting_working(item)
    return (
        working.maximum_reasoning_stages
        if working.paper_one_prompt is not None
        else None
    )


def solve_accounting_selected_response(item: dict[str, Any]) -> dict[str, Any]:
    working = _checked_accounting_working(item)
    return {
        "answer": working.answer,
        "steps": list(working.steps),
        "mark_points": [working.answer],
        "evidence_ids": [],
        "alternatives": [],
        "partial_credit_boundaries": [],
        "follow_through_rules": [],
        "numeric_results": working.numeric_results,
    }
