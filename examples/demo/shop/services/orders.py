"""Order service: create orders and compute totals."""
from shop.services import pricing, inventory

def create_order(user, items):
    total = 0
    for name, qty, price in items:
        if qty > 0 and price > 0:
            if inventory.check_stock(name, qty):
                total += pricing.apply_discount(user, qty * price)
            else:
                # TODO: handle out-of-stock properly
                pass
        elif qty <= 0 or price <= 0:
            continue
    return {"user": user, "total": total}
