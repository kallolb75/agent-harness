"""Check the oracle against the real COBOL. Needs GnuCOBOL (`cobc`) on the PATH.

    uv run python -m evals.verify_oracle            3,000 random orders
    uv run python -m evals.verify_oracle 500        a different count

It compiles legacy/ORDPRICE.cbl with a small test driver (legacy/PARITY.cbl), feeds
it random order lines, and compares every total and status with evals/oracle.py.
This is the golden-master idea from the evals: the legacy program is the authority,
and the Python oracle is only trusted because it agrees with it.
"""

import random
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from evals.oracle import price

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT / "legacy"


def random_order(rng):
    """One order inside the field sizes ORDPRICE declares."""
    return {
        "cust_type": rng.choice("RWG"),
        "qty": rng.choice([rng.randint(1, 99), rng.randint(100, 2000), 99, 100, 1]),
        "unit_price": Decimal(rng.randint(1, 50000)) / 100,
        "state": rng.choice(["TX", "CA", "NY", "FL", "WA"]),
        "credit_limit": Decimal(rng.randint(0, 500000000)) / 100,
        "open_balance": Decimal(rng.randint(0, 500000000)) / 100,
    }


def to_record(o):
    """The 33-character LK-ORDER-LINE: implied decimals, zero padded."""
    cents = lambda value, width: f"{int(value * 100):0{width}d}"
    return (o["cust_type"] + f"{o['qty']:05d}" + cents(o["unit_price"], 7) + o["state"]
            + cents(o["credit_limit"], 9) + cents(o["open_balance"], 9))


def compile_cobol(workdir):
    binary = Path(workdir) / "parity"
    subprocess.run(["cobc", "-x", "-o", str(binary), str(LEGACY / "PARITY.cbl"),
                    str(LEGACY / "ORDPRICE.cbl")], check=True, capture_output=True)
    return binary


def run(count=3000, seed=7):
    if shutil.which("cobc") is None:
        sys.exit("cobc not found. Install GnuCOBOL (apt install gnucobol, brew install gnucobol).")
    rng = random.Random(seed)
    orders = [random_order(rng) for _ in range(count)]
    # Keep the totals inside PIC 9(7)V99, as the real caller would.
    orders = [o for o in orders if price(o)[0] < Decimal("9999999.99")]
    with tempfile.TemporaryDirectory() as workdir:
        binary = compile_cobol(workdir)
        stdin = f"{len(orders):06d}\n" + "\n".join(to_record(o) for o in orders) + "\n"
        out = subprocess.run([str(binary)], input=stdin, capture_output=True, text=True,
                             check=True).stdout.splitlines()

    mismatches = []
    for order, line in zip(orders, out):
        cobol_total, cobol_status = Decimal(line[:10]), line[10]   # DISPLAY prints 9999999.99 then the status
        total, status = price(order)
        if cobol_total != total or cobol_status != status:
            mismatches.append((order, (cobol_total, cobol_status), (total, status)))

    print(f"{len(orders)} orders, {len(mismatches)} mismatches between ORDPRICE.cbl and oracle.py")
    for order, cobol, oracle in mismatches[:5]:
        print(f"  {order}\n    COBOL {cobol}   oracle {oracle}")
    return len(orders), mismatches


if __name__ == "__main__":
    n, mismatches = run(int(sys.argv[1]) if len(sys.argv) > 1 else 3000)
    sys.exit(1 if mismatches else 0)
