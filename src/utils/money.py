from __future__ import annotations


def calc_pretax(amount_with_tax: float, tax_rate: float = 0.05) -> int:
    if amount_with_tax is None:
        return 0
    return round(float(amount_with_tax) / (1 + tax_rate))


def calc_tax(amount_with_tax: float, tax_rate: float = 0.05) -> int:
    pretax = calc_pretax(amount_with_tax, tax_rate)
    return int(round(float(amount_with_tax) - pretax))
