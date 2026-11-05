"""Pricing and discount rules."""

def apply_discount(user, amount):
    if user.startswith("v") and amount > 100:
        return amount * 0.8
    if amount > 100:
        return amount * 0.9
    return amount

def calc_total(items):
    return sum(q * p for _, q, p in items)
