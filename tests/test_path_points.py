from pathlib import Path
import sqlite3
import tempfile
import unittest

from cifparse import CIFP
from cifparse.functions.record import field_5227
from cifparse.records.path_point.continuation import Continuation
from cifparse.records.path_point.primary import Primary
from cifparse.records.path_points import PathPoint

HEADER_LINES = [
    "HDR01FAACIFP18      001P01320000062312  09-NOV-202311:51:24  U.S.A. DOT FAA                                                B08C81BE",
    "HDR02                                 FEDERAL AVIATION ADMINISTRATION                                                               ",
    "HDR03                                 AERONAUTICAL INFORMATION SERVICES                                                             ",
    "HDR04                                 CODED INSTRUMENT FLIGHT PROCEDURES VOLUME 2312  EFFECTIVE 30 NOV 2023                         ",
    "HDR05                                 REPORT DATA ERRORS TO FAA                 TEL 800 638 8972                                    ",
]

KMHV_R30_LINES = [
    "SUSAP KMHVK2PR30   RW30 001 0000W30A0N3502475890W11807591195+078710300N3504089415W11809375580106750000000600F400500068F4C61560972207",
    "SUSAP KMHVK2PR30   RW30 002E      +08188+08188LPV       52823                                                              560982207",
]

KTRM_R30_LINES = [
    "SUSAP KTRMK2PR30   RW30 001 0000W30A0N3337136650W11609337440-007310300N3338168000W11610491790106751232000450F400500C20365FD326591808",
    "SUSAP KTRMK2PR30   RW30 002E      -00398-00398LPV       77941                                                              326601808",
]

KMHV_R04_LINES = [
    "SUSAP KMHVK2PR04   RW04 001 0000W04A0N3503383080W11809551150+081580350N3504433420W11808407815106750000000500F4000000B85172B560952004",
    "SUSAP KMHVK2PR04   RW04 002E      +08473+08473LP        77743                                                              560962004",
]


class TestPathPoints(unittest.TestCase):
    def test_field_5227_signed_orthometric_heights(self) -> None:
        self.assertEqual(field_5227("+08188"), 818.8)
        self.assertEqual(field_5227("-00398"), -39.8)
        self.assertEqual(field_5227("+00000"), 0.0)
        self.assertEqual(field_5227("-00000"), 0.0)
        self.assertEqual(field_5227("08188"), 818.8)
        self.assertIsNone(field_5227("      "))

    def test_path_point_parses_primary_and_extension_continuation(self) -> None:
        pp = PathPoint(KMHV_R30_LINES)
        self.assertIsInstance(pp.primary, Primary)
        self.assertEqual(len(pp.continuation), 1)
        self.assertIsInstance(pp.continuation[0], Continuation)

        data = pp.to_dict()
        pri = data["primary"]
        self.assertEqual(pri["airport_id"], "KMHV")
        self.assertEqual(pri["approach_id"], "R30")
        self.assertEqual(pri["surface_id"], "RW30")
        self.assertEqual(pri["ltp_ellipsoid_height"], 787.1)
        self.assertEqual(pri["gpa"], 3.0)
        self.assertEqual(pri["course_width"], 106.75)
        self.assertEqual(pri["path_point_tch"], 60.0)
        self.assertEqual(pri["tch_ind"], "F")
        self.assertEqual(pri["hal"], 40.0)
        self.assertEqual(pri["val"], 50.0)
        self.assertEqual(pri["crc"], "068F4C61")

        con = data["continuation"][0]
        self.assertEqual(con["application"], "E")
        self.assertIsNone(con["fpap_ell_hgt"])
        self.assertEqual(con["fpap_ort_hgt"], 818.8)
        self.assertEqual(con["ltp_ort_hgt"], 818.8)
        self.assertEqual(con["app_type_id"], "LPV")
        self.assertEqual(con["gnss_ch_no"], "52823")

    def test_path_point_negative_heights_and_lp_zero_val(self) -> None:
        ktrm = PathPoint(KTRM_R30_LINES).to_dict()
        self.assertEqual(ktrm["primary"]["ltp_ellipsoid_height"], -73.1)
        self.assertEqual(ktrm["continuation"][0]["fpap_ort_hgt"], -39.8)
        self.assertEqual(ktrm["continuation"][0]["ltp_ort_hgt"], -39.8)

        kmhv_lp = PathPoint(KMHV_R04_LINES).to_dict()
        self.assertEqual(kmhv_lp["primary"]["val"], 0.0)
        self.assertEqual(kmhv_lp["continuation"][0]["app_type_id"], "LP")

    def test_non_extension_continuation_is_ignored(self) -> None:
        standard_note_line = (
            "SUSAP KMHVK2PR30   RW30 002A      NOTE CONTINUATION TEXT                                                                   560992207"
        )
        pp = PathPoint([KMHV_R30_LINES[0], standard_note_line])
        self.assertIsNotNone(pp.primary)
        self.assertEqual(pp.continuation, [])

    def test_create_statements_use_matching_sql_types(self) -> None:
        pri_sql = Primary().to_create_statement()
        self.assertIn("ltp_ellipsoid_height REAL", pri_sql)
        self.assertIn("path_point_tch REAL", pri_sql)
        self.assertIn("hal REAL", pri_sql)
        self.assertIn("val REAL", pri_sql)

        con_sql = Continuation().to_create_statement()
        self.assertIn("fpap_ell_hgt REAL", con_sql)
        self.assertIn("fpap_ort_hgt REAL", con_sql)
        self.assertIn("ltp_ort_hgt REAL", con_sql)
        self.assertIn("hpc INTEGER", con_sql)

    def test_cifp_parse_path_points_and_to_db(self) -> None:
        synthetic_ext = (
            "SUSAP EDDFEDPR07C  RW07C002E-00125+01100+01100LPV       41234          090                                                 900000002"
        )
        synthetic_pri = (
            "SUSAP EDDFEDPR07C  RW07C001 0000W07A0N5002000000E00834000000+015500300N5002300000E00836000000106750000001500M40035012345678900000001"
        )
        cifp_text = "\n".join(
            [
                *HEADER_LINES,
                *KMHV_R30_LINES,
                *KTRM_R30_LINES,
                synthetic_pri,
                synthetic_ext,
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cifp_path = tmp / "FAACIFP18"
            db_path = tmp / "cifp.sqlite"
            cifp_path.write_text(cifp_text + "\n")

            c = CIFP(str(cifp_path))
            c.parse_path_points()
            points = c.get_path_points()
            self.assertEqual(len(points), 3)
            self.assertTrue(all(p.primary is not None for p in points))
            self.assertTrue(all(len(p.continuation) == 1 for p in points))

            c.to_db(str(db_path))

            with sqlite3.connect(db_path) as conn:
                pri_cols = {
                    row[1]: row[2]
                    for row in conn.execute("PRAGMA table_info(path_points)")
                }
                self.assertEqual(pri_cols["ltp_ellipsoid_height"], "REAL")
                self.assertEqual(pri_cols["path_point_tch"], "REAL")
                self.assertEqual(pri_cols["hal"], "REAL")
                self.assertEqual(pri_cols["val"], "REAL")

                con_cols = {
                    row[1]: row[2]
                    for row in conn.execute(
                        "PRAGMA table_info(path_point_continuations)"
                    )
                }
                self.assertEqual(con_cols["fpap_ell_hgt"], "REAL")
                self.assertEqual(con_cols["fpap_ort_hgt"], "REAL")
                self.assertEqual(con_cols["ltp_ort_hgt"], "REAL")
                self.assertEqual(con_cols["hpc"], "INTEGER")

                pri_rows = conn.execute(
                    "SELECT airport_id, ltp_ellipsoid_height, path_point_tch, hal, val "
                    "FROM path_points ORDER BY airport_id"
                ).fetchall()
                self.assertEqual(
                    pri_rows,
                    [
                        ("EDDF", 155.0, 15.0, 40.0, 35.0),
                        ("KMHV", 787.1, 60.0, 40.0, 50.0),
                        ("KTRM", -73.1, 45.0, 40.0, 50.0),
                    ],
                )

                con_rows = conn.execute(
                    "SELECT airport_id, fpap_ell_hgt, fpap_ort_hgt, ltp_ort_hgt, hpc "
                    "FROM path_point_continuations ORDER BY airport_id"
                ).fetchall()
                self.assertEqual(
                    con_rows,
                    [
                        ("EDDF", -12.5, 110.0, 110.0, 90),
                        ("KMHV", None, 818.8, 818.8, None),
                        ("KTRM", None, -39.8, -39.8, None),
                    ],
                )


if __name__ == "__main__":
    unittest.main()
