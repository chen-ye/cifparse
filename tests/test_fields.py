"""Field-level decoder and record partitioning tests for cifparse.

Assertions and edge cases adapted from:
- mitre-public/boogie (Apache-2.0, Copyright MITRE)
- RISCfuture/SwiftCIFP (MIT, Copyright 2026 Tim Morgan)
- birdhalfbaked/arinc424-rs (MIT, Copyright 2026 Clifford Richardson)
- AeronauticalMaps/libefb (Apache-2.0)
"""

import unittest

from cifparse.functions.field import extract_field
from cifparse.functions.record import (
    field_5103,
    field_516,
    field_517,
    field_524,
    field_525,
    field_526,
    field_527,
    field_528,
    field_530,
    field_532,
    field_534,
    field_536,
    field_537,
    field_539,
    field_540,
    field_547,
    field_552,
    field_555,
    field_558,
    field_562,
    field_566,
    field_568,
    field_570,
    field_574,
    field_592,
    field_597,
    field_5204,
    field_5211,
    field_5212,
    field_5225,
    field_5226,
    field_5227,
    field_5248,
    field_5267,
    field_5268,
    field_5275,
    field_5276,
)
from cifparse.functions.records import partition, split_lines_by_char


class TestCoordinates(unittest.TestCase):
    def test_latitude_standard_and_edge_cases(self) -> None:
        self.assertAlmostEqual(field_536("N39513881"), 39.86078055, places=6)
        self.assertAlmostEqual(field_536("S39513881"), -39.86078055, places=6)
        self.assertAlmostEqual(field_536("S33563000"), -33.94166667, places=6)
        self.assertEqual(field_536("S00000000"), 0.0)
        self.assertIsNone(field_536("         "))
        self.assertIsNone(field_536("SA9513881"))
        self.assertIsNone(field_536("X39513881"))

    def test_longitude_standard_and_edge_cases(self) -> None:
        self.assertAlmostEqual(field_537("E104450794"), 104.7522055, places=6)
        self.assertAlmostEqual(field_537("W104450794"), -104.7522055, places=6)
        self.assertAlmostEqual(field_537("W118244500"), -118.4125, places=6)
        self.assertAlmostEqual(field_537("E000274500"), 0.4625, places=6)
        self.assertEqual(field_537("W000000000"), 0.0)
        self.assertIsNone(field_537("          "))
        self.assertIsNone(field_537("WA04450794"))
        self.assertIsNone(field_537("X104450794"))

    def test_high_precision_lat_lon(self) -> None:
        self.assertAlmostEqual(field_5267("N6135419550"), 61 + 35 / 60 + 41.9550 / 3600, places=9)
        self.assertAlmostEqual(
            field_5268("W14906023005"), -(149 + 6 / 60 + 2.3005 / 3600), places=9
        )
        self.assertAlmostEqual(
            field_5268("W03951388112"), -(39 + 51 / 60 + 38.8112 / 3600), places=9
        )
        self.assertIsNone(field_5267("           "))
        self.assertIsNone(field_5268("            "))
        self.assertIsNone(field_5267("X6135419550"))


class TestBearingsAndVariation(unittest.TestCase):
    def test_magnetic_and_true_bearings(self) -> None:
        for fn in (field_526, field_528, field_547, field_558, field_562):
            self.assertEqual(fn("2937"), (False, 293.7))
            self.assertEqual(fn("0001"), (False, 0.1))
            self.assertEqual(fn("194T"), (True, 194))
            self.assertEqual(fn("347T"), (True, 347))
            self.assertEqual(fn("    "), (None, None))
            self.assertEqual(fn("19T4"), (None, None))
            self.assertEqual(fn("29 7"), (None, None))
            self.assertEqual(fn("T194"), (None, None))
            self.assertEqual(fn("ACB1"), (None, None))

    def test_magnetic_variation(self) -> None:
        self.assertEqual(field_539("E0130"), 13.0)
        self.assertEqual(field_539("W0145"), -14.5)
        self.assertEqual(field_539("T0140"), 0.0)
        self.assertIsNone(field_539("     "))
        self.assertIsNone(field_539("E013A"))
        self.assertIsNone(field_539("A0140"))

    def test_station_declination(self) -> None:
        self.assertEqual(field_566("E0140"), 14.0)
        self.assertEqual(field_566("W0010"), -1.0)
        self.assertEqual(field_566("T0010"), 0.0)
        self.assertEqual(field_566("G0010"), 0.0)
        self.assertIsNone(field_566("     "))
        self.assertIsNone(field_566("A0140"))


class TestAltitudesAndElevations(unittest.TestCase):
    def test_altitude_flight_level_and_sentinels(self) -> None:
        self.assertEqual(field_530("05000"), (False, 5000))
        self.assertEqual(field_530("FL050"), (True, 50))
        self.assertEqual(field_530("FL350"), (True, 350))
        self.assertEqual(field_530("-0012"), (False, -12))
        self.assertEqual(field_530("+0012"), (False, 12))
        self.assertEqual(field_530("-0000"), (False, 0))
        for invalid in (
            "     ",
            "1234A",
            "FLAVA",
            "FL+12",
            "UNLTD",
            "UNKNN",
            "NESTB",
            "NOTSP",
            " GND ",
            " MSL ",
            "NOTAM",
            "\u0661\u0662\u0663\u0664\u0665",
        ):
            self.assertEqual(field_530(invalid), (None, None), msg=f"input={invalid!r}")

    def test_signed_elevations(self) -> None:
        for fn in (
            field_540,
            field_555,
            field_568,
            field_574,
            field_592,
            field_597,
            field_5248,
        ):
            self.assertEqual(fn("-0114"), -114)
            self.assertEqual(fn("-0210"), -210)
            self.assertEqual(fn("+0252"), 252)
            self.assertEqual(fn("02183"), 2183)
            self.assertEqual(fn(" 0070"), 70)
            self.assertIsNone(fn("     "))
            self.assertIsNone(fn("-12AB"))


class TestAnglesRnpDistanceAndMisc(unittest.TestCase):
    def test_rnp_mantissa_and_exponent(self) -> None:
        self.assertEqual(field_5211("100"), 10.0)
        self.assertEqual(field_5211("013"), 0.001)
        self.assertEqual(field_5211("010"), 1.0)
        self.assertEqual(field_5211("101"), 1.0)
        self.assertEqual(field_5211("302"), 0.3)
        self.assertEqual(field_5211("031"), 0.3)
        self.assertEqual(field_5211("152"), 0.15)
        self.assertEqual(field_5211("151"), 1.5)
        self.assertEqual(field_5211("990"), 99.0)
        for bad in ("", "   ", "0  ", "A01", "0A1", "0 1", "31", "1.3", "-013", "\u0660\u0661\u0663"):
            self.assertIsNone(field_5211(bad), msg=f"input={bad!r}")

    def test_vertical_angle_glide_slope_and_gradient(self) -> None:
        self.assertEqual(field_570("-969"), -9.69)
        self.assertEqual(field_570(" 000"), 0.0)
        self.assertEqual(field_570("0999"), 9.99)
        self.assertEqual(field_570("-999"), -9.99)
        self.assertIsNone(field_570("    "))
        self.assertIsNone(field_570("-12A"))

        self.assertEqual(field_552("912"), 9.12)
        self.assertEqual(field_552("051"), 0.51)
        self.assertEqual(field_552("600"), 6.0)
        self.assertIsNone(field_552("   "))
        self.assertIsNone(field_552("AC1"))

        self.assertEqual(field_5212("+0450"), 0.45)
        self.assertEqual(field_5212("-0300"), -0.3)
        self.assertEqual(field_5212("+8999"), 8.999)
        self.assertIsNone(field_5212("110AB"))

        self.assertEqual(field_5225("+07871"), 787.1)
        self.assertEqual(field_5225("-00731"), -73.1)
        self.assertEqual(field_5226("0300"), 3.0)
        self.assertEqual(field_5227("+08188"), 818.8)
        self.assertEqual(field_5227("-00398"), -39.8)

    def test_dist_time_arc_radius_and_theta_rho(self) -> None:
        self.assertEqual(field_527("1076"), (False, 107.6))
        self.assertEqual(field_527("0061"), (False, 6.1))
        self.assertEqual(field_527("T103"), (True, 10.3))
        self.assertEqual(field_527("T010"), (True, 1.0))
        self.assertEqual(field_527("T01 "), (None, None))
        self.assertEqual(field_527("X010"), (None, None))
        self.assertEqual(field_527("-076"), (None, None))
        self.assertEqual(field_527("T"), (None, None))

        self.assertEqual(field_5204("002500"), 2.5)
        self.assertEqual(field_5204("002070"), 2.07)
        self.assertEqual(field_524("1908"), 190.8)
        self.assertEqual(field_525("0032"), 3.2)

    def test_continuation_number_comm_freq_and_sbas_fields(self) -> None:
        self.assertEqual(field_516("0"), 0)
        self.assertEqual(field_516("1"), 1)
        self.assertEqual(field_516("9"), 9)
        self.assertEqual(field_516("A"), 10)
        self.assertEqual(field_516("Z"), 35)
        self.assertIsNone(field_516("a"))
        self.assertIsNone(field_516(" "))
        self.assertIsNone(field_516(""))
        self.assertIsNone(field_516("@"))

        self.assertEqual(field_5103("1234500", "V"), 1234.5)
        self.assertEqual(field_5103("0118400", "V"), 118.4)
        self.assertEqual(field_5103("0121500", "C"), 121.5)
        self.assertEqual(field_5103("0025430", "U"), 254.3)
        self.assertEqual(field_5103("0005615", "H"), 56.15)
        self.assertIsNone(field_5103("0118400", "X"))

        self.assertEqual(field_534("11400", "VOR"), 114.0)
        self.assertEqual(field_534("02770", "NDB"), 277.0)
        self.assertEqual(field_517("EY  "), "EY  ")
        self.assertEqual(field_532("2101"), "2101")
        self.assertEqual(field_5275("LPV       "), "LPV")
        self.assertTrue(field_5276("A"))
        self.assertFalse(field_5276("N"))
        self.assertIsNone(field_5276(" "))

    def test_partition_split_and_extract_field(self) -> None:
        self.assertEqual(extract_field("ABCDEF", (1, 4, lambda s: s.lower())), "bcd")
        self.assertEqual(
            split_lines_by_char(["0000A1", "0000p1", "0000A2"], (4, 5)),
            {"A": ["0000A1", "0000A2"], "P": ["0000p1"]},
        )
        groups = partition(["AAA1", "AAA2", "BBB1"], 0, 3)
        self.assertEqual(groups, [["AAA1", "AAA2"], ["BBB1"]])


if __name__ == "__main__":
    unittest.main()
