"""Original multi-step Paper 1 choices with source-owned keys and distractors."""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from Backend.Core.subjects.accounting_selected_response import (
    LIQUIDITY_INVENTORY_TREATMENTS,
    PRIME_ENTRY_TRANSACTIONS,
    AccountingOperation,
    accounting_selected_response_contract,
    derive_accounting_choice,
    pounds,
    prime_entry_prompt,
)


@dataclass(frozen=True)
class AccountingChoiceScenario:
    prompt: str
    choices: list[str]
    correct_choice: int
    public_contract: dict[str, Any]


def build_prime_entry_choice(rng: random.Random) -> AccountingChoiceScenario:
    contract = accounting_selected_response_contract(
        "prime_entry_book", {"transaction": rng.choice(PRIME_ENTRY_TRANSACTIONS)}
    )
    working = derive_accounting_choice(contract)
    choices = list(working.classification_choices)
    rng.shuffle(choices)
    return AccountingChoiceScenario(
        prime_entry_prompt(contract), choices, choices.index(working.answer), contract
    )


def build_liquidity_choice(rng: random.Random) -> AccountingChoiceScenario:
    contract = accounting_selected_response_contract(
        "liquidity_ratio_definition",
        {"inventory_treatment": rng.choice(LIQUIDITY_INVENTORY_TREATMENTS)},
    )
    working = derive_accounting_choice(contract)
    if working.paper_one_prompt is None:
        raise ValueError("Accounting liquidity choice lacks its public wording")
    choices = list(working.classification_choices)
    rng.shuffle(choices)
    return AccountingChoiceScenario(
        working.paper_one_prompt, choices, choices.index(working.answer), contract
    )


def build_accounting_choice(index: int, rng: random.Random) -> AccountingChoiceScenario:
    if index == 5:
        operation: AccountingOperation = "carriage_gross_profit"
        revenue = Decimal(rng.randrange(220, 321, 5) * 1000)
        opening = Decimal(rng.randrange(15, 26) * 1000)
        purchases = Decimal(rng.randrange(130, 171, 5) * 1000)
        returns = Decimal(rng.choice((2000, 4000, 6000)))
        inward = Decimal(rng.choice((1000, 3000, 5000)))
        outward = Decimal(rng.choice((1500, 2500, 3500)))
        closing = Decimal(rng.randrange(18, 31) * 1000)
        inputs = {
            "revenue": str(revenue),
            "opening_inventory": str(opening),
            "purchases": str(purchases),
            "purchase_returns": str(returns),
            "carriage_inwards": str(inward),
            "carriage_outwards": str(outward),
            "closing_inventory": str(closing),
        }
        profit = revenue - (opening + purchases - returns + inward - closing)
        distractors = [
            pounds(profit + inward),
            pounds(profit - outward),
            pounds(profit - returns),
        ]
    elif index == 6:
        operation = "sale_or_return_gross_profit"
        revenue = Decimal(rng.randrange(240, 321, 10) * 1000)
        opening = Decimal(rng.randrange(15, 26) * 1000)
        purchases = Decimal(rng.randrange(130, 171, 5) * 1000)
        closing = Decimal(rng.randrange(18, 31) * 1000)
        returned_cost = Decimal(rng.randrange(6, 13) * 1000)
        markup = Decimal(rng.choice((20, 25, 40, 50)))
        selling = returned_cost * (1 + markup / 100)
        inputs = {
            "revenue": str(revenue),
            "opening_inventory": str(opening),
            "purchases": str(purchases),
            "closing_inventory_excluding_return": str(closing),
            "sale_or_return_selling_price": str(selling),
            "markup_percent_on_cost": str(markup),
        }
        unadjusted = revenue - (opening + purchases - closing)
        distractors = [
            pounds(unadjusted),
            pounds(unadjusted - selling),
            pounds(unadjusted + returned_cost),
        ]
    elif index == 7:
        operation = "credit_sale_correction"
        amount = Decimal(rng.randrange(15, 50) * 500)
        inputs = {"credit_sale": str(amount)}
        distractors = []
    elif index == 8:
        operation = "net_share_premium"
        shares = Decimal(rng.randrange(20, 101, 5) * 1000)
        nominal = Decimal(rng.choice((25, 50)))
        issue = Decimal(rng.choice((125, 150, 175, 200)))
        costs = Decimal(rng.randrange(10, 31, 5) * 100)
        inputs = {
            "shares_issued": str(shares),
            "nominal_value_pence": str(nominal),
            "issue_price_pence": str(issue),
            "issue_costs": str(costs),
        }
        gross_premium = shares * (issue - nominal) / 100
        distractors = [
            pounds(gross_premium),
            pounds(shares * issue / 100 - costs),
            pounds(shares * nominal / 100),
        ]
    else:
        raise ValueError(
            "Accounting multi-step choice requires Paper 1 question 6, 7, 8 or 9"
        )

    contract = accounting_selected_response_contract(operation, inputs)
    working = derive_accounting_choice(contract)
    if working.paper_one_prompt is None:
        raise ValueError("Accounting Paper 1 choice lacks its public wording")
    choices = (
        list(working.journal_choices)
        if working.journal_choices
        else [working.answer, *distractors]
    )
    if len(set(choices)) != 4:
        raise ValueError("Accounting choice construction produced ambiguous options")
    rng.shuffle(choices)
    return AccountingChoiceScenario(
        working.paper_one_prompt, choices, choices.index(working.answer), contract
    )
