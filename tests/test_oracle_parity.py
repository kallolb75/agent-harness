"""The oracle agrees with the real COBOL. Skipped where GnuCOBOL is not installed."""

import shutil

import pytest

from evals.verify_oracle import run


@pytest.mark.skipif(shutil.which("cobc") is None, reason="GnuCOBOL (cobc) not installed")
def test_oracle_matches_compiled_cobol():
    count, mismatches = run(count=300)
    assert count > 250
    assert mismatches == []
