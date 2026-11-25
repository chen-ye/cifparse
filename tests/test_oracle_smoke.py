"""Optional unittest wrapper for the Boogie differential oracle.

Skipped during normal offline unittest runs unless CIFPARSE_RUN_ORACLE=1 is set.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from tests.oracle.run import build_smoke_cifp, run_cifp


@unittest.skipUnless(
    os.environ.get("CIFPARSE_RUN_ORACLE") == "1",
    "Set CIFPARSE_RUN_ORACLE=1 (requires javac, java, and Maven Central cache) to run live Boogie oracle.",
)
class TestBoogieOracleSmoke(unittest.TestCase):
    def test_smoke_active_fixtures_match_boogie(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = build_smoke_cifp(Path(tmpdir) / "SMOKE_CIFP")
            res = run_cifp(smoke_path, version="V19", check_to_db=True, quiet=True)
            self.assertEqual(res.missing_in_cifparse, {})
            self.assertEqual(res.diff_counts, {})
            self.assertGreater(res.indexed, 0)

    def test_external_cifp_if_configured(self) -> None:
        ext = os.environ.get("CIFPARSE_ORACLE_CIFP")
        if not ext:
            self.skipTest("CIFPARSE_ORACLE_CIFP not set")
        version = os.environ.get("CIFPARSE_ORACLE_VERSION", "V19")
        res = run_cifp(Path(ext), version=version, check_to_db=True, quiet=True)
        self.assertEqual(res.missing_in_cifparse, {})
        self.assertEqual(res.diff_counts, {})
