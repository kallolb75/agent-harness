"""Parity demo for segment 4: seeded translation defects against the compiled COBOL.

Each variant is a plausible translation of ORDPRICE with one defect a fluent but
careless translation makes. The COBOL is the oracle: every expected value comes
from running ORDPRICE.cbl, never from Python.

Two input sets:
  random   - 3,000 orders from verify_oracle.random_order (seed 7), production-like
  boundary - cases built at every threshold: the $25.00 fee line, qty 99/100/101,
             rounding ties on tax, credit limit exactly equal, government orders

Needs GnuCOBOL (`cobc`) on the PATH, like evals/verify_oracle.py:

    uv run python -m evals.translation_parity

The point it makes: a random sample misses defects that sit on a threshold. Ask for
boundary tests; a pass rate on random inputs alone can hide these defects.
"""

import itertools
import shutil
import subprocess
import sys
import tempfile
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from random import Random

from evals.oracle import price as oracle_price
from evals.verify_oracle import compile_cobol, random_order, to_record

CENT = Decimal("0.01")
RATES = {"TX": Decimal("0.0625"), "CA": Decimal("0.0725")}


def make_variant(*, use_float=False, add_discounts=False, fee_after_tax=False,
                 half_even=False, credit_ge=False, fee_le=False):
    """Return a price() function carrying the chosen defects."""
    def money(v):
        if use_float:
            return round(float(v), 2)
        return Decimal(v).quantize(CENT, rounding=ROUND_HALF_EVEN if half_even else ROUND_HALF_UP)

    def num(x):
        return float(x) if use_float else Decimal(str(x))

    def price(o):
        cust, qty, state = o["cust_type"], int(o["qty"]), o["state"]
        unit, limit, bal = num(o["unit_price"]), num(o["credit_limit"]), num(o["open_balance"])
        disc = {"W": num("0.080"), "G": num("0.050")}.get(cust, num("0"))
        vol = num("0.030") if qty >= 100 else num("0")
        gross = money(qty * unit)
        if add_discounts:
            net = money(gross * (1 - disc - vol))
        else:
            net = money(gross * (1 - disc))
            if qty >= 100:
                net = money(net * (1 - vol))
        threshold = num("25.00")
        fee_applies = (net <= threshold if fee_le else net < threshold) and cust != "G"
        fee = num("4.95") if fee_applies else num("0")
        rate = num("0") if cust == "G" else num(RATES.get(state, Decimal("0.0500")))
        if fee_after_tax:
            tax = money(net * rate)
            total = net + tax + fee
        else:
            net = net + fee
            tax = money(net * rate)
            total = net + tax
        total = money(total)
        held = (bal + total >= limit) if credit_ge else (bal + total > limit)
        return Decimal(str(total)).quantize(CENT), "H" if held else "A"
    return price


VARIANTS = {
    "correct (oracle.py)": oracle_price,
    "float instead of decimal": make_variant(use_float=True),
    "discounts added, not compounded": make_variant(add_discounts=True),
    "fee added after tax": make_variant(fee_after_tax=True),
    "half-even rounding": make_variant(half_even=True),
    "credit hold at >= limit": make_variant(credit_ge=True),
    "fee at <= $25.00": make_variant(fee_le=True),
    "all six defects together": make_variant(use_float=True, add_discounts=True, fee_after_tax=True,
                                             half_even=True, credit_ge=True, fee_le=True),
}


def boundary_orders():
    """Cases at every threshold the rules contain. Inputs only; answers come from COBOL."""
    out = []
    base = {"state": "TX", "credit_limit": Decimal("9999999.99"), "open_balance": Decimal("0")}
    # 1. the $25.00 fee line, per customer type (qty 1 so net = unit price for retail)
    for cust, price_cents in itertools.product("RWG", [2499, 2500, 2501, 2717, 2718, 2719, 2631, 2632, 2633]):
        out.append({**base, "cust_type": cust, "qty": 1, "unit_price": Decimal(price_cents) / 100})
    # 2. the volume break
    for cust, qty in itertools.product("RWG", [99, 100, 101]):
        out.append({**base, "cust_type": cust, "qty": qty, "unit_price": Decimal("10.07")})
    # 3. rounding ties: retail, qty 1, net * rate lands exactly on half a cent
    rng = Random(11)
    for state, rate in [("TX", Decimal("0.0625")), ("CA", Decimal("0.0725")), ("NY", Decimal("0.05"))]:
        found = 0
        for cents in range(2600, 900000, 7):
            tax3 = (Decimal(cents) / 100 * rate) * 1000
            if tax3 == tax3.to_integral_value() and int(tax3) % 10 == 5:
                out.append({**base, "state": state, "cust_type": "R", "qty": 1,
                            "unit_price": Decimal(cents) / 100})
                found += 1
                if found == 15:
                    break
    # 4. credit limit exactly equal to open balance plus total
    for _ in range(15):
        o = {**base, "cust_type": rng.choice("RWG"), "qty": rng.randint(1, 300),
             "unit_price": Decimal(rng.randint(100, 20000)) / 100,
             "open_balance": Decimal(rng.randint(0, 100000)) / 100}
        total, _ = oracle_price(o)          # used only to place the input on the line
        o["credit_limit"] = o["open_balance"] + total
        out.append(o)
    return out


def cobol_answers(orders):
    with tempfile.TemporaryDirectory() as wd:
        binary = compile_cobol(wd)
        stdin = f"{len(orders):06d}\n" + "\n".join(to_record(o) for o in orders) + "\n"
        lines = subprocess.run([str(binary)], input=stdin, capture_output=True, text=True,
                               check=True).stdout.splitlines()
    return [(Decimal(l[:10]), l[10]) for l in lines]


def main():
    if shutil.which("cobc") is None:
        sys.exit("cobc not found. Install GnuCOBOL (apt install gnucobol, brew install gnucobol).")
    rng = Random(7)
    randoms = [random_order(rng) for _ in range(3000)]
    randoms = [o for o in randoms if oracle_price(o)[0] < Decimal("9999999.99")]
    bounds = boundary_orders()
    sets = {"random": randoms, "boundary": bounds}
    gold = {name: cobol_answers(orders) for name, orders in sets.items()}

    print(f"random set {len(randoms)} orders, boundary set {len(bounds)} orders; expected values from compiled ORDPRICE.cbl\n")
    print(f"{'variant':34} {'random fails':>14} {'boundary fails':>15}")
    for vname, fn in VARIANTS.items():
        row = []
        for sname, orders in sets.items():
            fails = sum(1 for o, g in zip(orders, gold[sname]) if fn(o) != g)
            row.append(f"{fails}/{len(orders)}")
        print(f"{vname:34} {row[0]:>14} {row[1]:>15}")

    # show one failing example per defect, from whichever set catches it first
    print("\nfirst failing case per defect:")
    for vname, fn in list(VARIANTS.items())[1:-1]:
        for sname in ("random", "boundary"):
            hit = next(((o, g, fn(o)) for o, g in zip(sets[sname], gold[sname]) if fn(o) != g), None)
            if hit:
                o, g, v = hit
                print(f"  {vname}: [{sname}] {o['cust_type']} qty {o['qty']} @ {o['unit_price']} {o['state']}"
                      f" -> COBOL {g[0]} {g[1]}, translation {v[0]} {v[1]}")
                break


if __name__ == "__main__":
    main()
