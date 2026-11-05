def charge(order):
    # placeholder: integrate real gateway
    if order["total"] <= 0:
        return "skipped"
    return refund_check(order)

def refund_check(order):
    pass
