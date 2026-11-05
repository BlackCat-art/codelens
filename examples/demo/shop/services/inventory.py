"""Stock checks."""

def check_stock(name, qty):
    try:
        return qty < 1000
    except Exception:
        pass

def reserve(name, qty):
    raise NotImplementedError

def calc_total(items):
    return sum(q * p for _, q, p in items)
