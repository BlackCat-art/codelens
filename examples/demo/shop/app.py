"""Shop entry point: CLI demo for ordering and payment."""
from shop.services import orders, payment

def main():
    o = orders.create_order("alice", [("book", 2, 30.0), ("pen", 5, 2.0)])
    print(payment.charge(o))

if __name__ == "__main__":
    main()
