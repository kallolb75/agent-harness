"""The oracle: what ORDPRICE.cbl actually returns, written by hand in Python.

In a real modernization the oracle is the legacy system itself: you run the COBOL
with the test inputs and record its outputs (a "golden master"). This file stands
in for that run. It was checked against ORDPRICE.cbl compiled with GnuCOBOL.

The rule it enforces: an expected value written by a model is a CLAIM. It is
checked against the oracle, never trusted on its own.

Decimal, not float: float cannot hold 0.1 exactly, and money code that uses it
drifts by a cent. Same reason you'd use BigDecimal in Java or decimal in C#.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value):
    """Round half up to cents, the way COBOL ROUNDED does."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def price(inputs):
    """Return (total, status) for one order line, following ORDPRICE paragraph by paragraph."""
    cust = inputs["cust_type"]
    qty = int(inputs["qty"])
    unit_price = Decimal(str(inputs["unit_price"]))
    state = inputs["state"]
    credit_limit = Decimal(str(inputs["credit_limit"]))
    open_balance = Decimal(str(inputs["open_balance"]))

    # 1000-CUSTOMER-DISCOUNT
    discount = {"W": Decimal("0.080"), "G": Decimal("0.050")}.get(cust, Decimal("0"))
    gross = money(qty * unit_price)
    net = money(gross * (1 - discount))

    # 2000-VOLUME-DISCOUNT: applied to the already discounted net, so it compounds
    if qty >= 100:
        net = money(net * (1 - Decimal("0.030")))

    # 3000-SMALL-ORDER-FEE: added to net BEFORE tax, so the fee is taxed
    if net < Decimal("25.00") and cust != "G":
        net += Decimal("4.95")

    # 4000-SALES-TAX
    if cust == "G":
        tax_rate = Decimal("0")
    else:
        tax_rate = {"TX": Decimal("0.0625"), "CA": Decimal("0.0725")}.get(state, Decimal("0.0500"))
    tax = money(net * tax_rate)
    total = net + tax

    # 5000-CREDIT-CHECK: strictly greater than the limit holds; equal is approved
    status = "H" if open_balance + total > credit_limit else "A"
    return total, status
