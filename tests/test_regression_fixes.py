"""Regression tests for cifparse bug fixes across sections, fields, and records.

Includes real 132-byte fixtures and regression scenarios adapted from:
- mitre-public/boogie (Apache-2.0, Copyright MITRE)
- mploscos/arinc424-toolkit (MIT, Copyright 2026 Marcos Perez Loscos)
"""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from cifparse import CIFP
from cifparse.functions.record import field_534, field_5103, field_5265
from cifparse.records.airway_marker.primary import Primary as AirwayMarkerPrimary
from cifparse.records.airway_points import AirwayPoint
from cifparse.records.airway_restriction.alt_exc_primary import (
    AltExcPrimary as RestrictionAltExcPrimary,
)
from cifparse.records.airway_restriction.closure_primary import (
    ClosurePrimary as RestrictionClosurePrimary,
)
from cifparse.records.airway_restriction.cruise_primary import (
    CruisePrimary as RestrictionCruisePrimary,
)
from cifparse.records.airway_restriction.note_continuation import (
    NoteContinuation as RestrictionNoteContinuation,
)
from cifparse.records.airway_restriction.note_primary import (
    NotePrimary as RestrictionNotePrimary,
)
from cifparse.records.airway_restrictions import AirwayRestriction
from cifparse.records.alternate_record.base import Base as AlternateRecordBase
from cifparse.records.airport.planning_continuation import (
    PlanningContinuation as AirportPlanningContinuation,
)
from cifparse.records.airway_point.planning_continuation import (
    PlanningContinuation as AirwayPointPlanningContinuation,
)
from cifparse.records.company_route.base import Base as CompanyRouteBase
from cifparse.records.company_route.primary import Primary as CompanyRoutePrimary
from cifparse.records.controlleds import Controlleds
from cifparse.records.cruise_table.primary import Primary as CruiseTablePrimary
from cifparse.records.enroute_comm.primary import Primary as EnrouteCommPrimary
from cifparse.records.enroute_comms import EnrouteComm
from cifparse.records.gls.primary import Primary as GLSPrimary
from cifparse.records.heli_procedure.base import Base as HeliProcedureBase
from cifparse.records.heli_procedure.planning import (
    Planning as HeliProcedurePlanning,
)
from cifparse.records.heli_procedure.planning_continuation import (
    PlanningContinuation as HeliProcedurePlanningContinuation,
)
from cifparse.records.heli_terminal_comm.primary import (
    Primary as HeliTerminalCommPrimary,
)
from cifparse.records.heli_waypoint.planning_continuation import (
    PlanningContinuation as HeliWaypointPlanningContinuation,
)
from cifparse.records.heliport.planning_continuation import (
    PlanningContinuation as HeliportPlanningContinuation,
)
from cifparse.records.holds import Holds
from cifparse.records.loc_gss import LOC_GS
from cifparse.records.mls.continuation import Continuation as MLSContinuation
from cifparse.records.ndb_navaid.planning_continuation import (
    PlanningContinuation as NDBPlanningContinuation,
)
from cifparse.records.path_point.primary import Primary as PathPointPrimary
from cifparse.records.procedure.base import Base as ProcedureBase
from cifparse.records.procedure.continuation import Continuation as ProcedureContinuation
from cifparse.records.procedure.planning_continuation import (
    PlanningContinuation as ProcedurePlanningContinuation,
)
from cifparse.records.reference_table.base import Base as ReferenceTableBase
from cifparse.records.reference_table.primary import Primary as ReferenceTablePrimary
from cifparse.records.terminal_comm.primary import Primary as TerminalCommPrimary
from cifparse.records.terminal_marker.primary import Primary as TerminalMarkerPrimary
from cifparse.records.vhf_navaid.planning_continuation import (
    PlanningContinuation as VHFPlanningContinuation,
)
from cifparse.records.waypoint.planning_continuation import (
    PlanningContinuation as WaypointPlanningContinuation,
)
from cifparse.section.section_p import SectionP
from cifparse.section.section_r import SectionR

HEADER_LINES = [
    "HDR01FAACIFP18      001P01320000012210  07-JAN-202113:45:45  U.S.A. DOT FAA                                                BF9354BE",
    "HDR02                                 FEDERAL AVIATION ADMINISTRATION                                                               ",
    "HDR03                                 AERONAUTICAL INFORMATION SERVICES                                                             ",
    "HDR04                                 CODED INSTRUMENT FLIGHT PROCEDURES VOLUME 2210  EFFECTIVE 06 OCT 2022                         ",
    "HDR05                                 REPORT DATA ERRORS TO FAA                 TEL 800 638 8972                                    ",
]


def _build_132(slices: dict[tuple[int, int], str]) -> str:
    buf = [" "] * 132
    for (start, end), value in slices.items():
        padded = value.ljust(end - start)[: end - start]
        buf[start:end] = list(padded)
    return "".join(buf)


class TestSectionAndCifpEntrypoints(unittest.TestCase):
    def test_parse_gates_and_parse_enroute_comms_execute(self) -> None:
        pb_line = (
            "SUSAP KBOSK6B11      0          N42220635W071005817                                                                        976262210"
        )
        ev_line = _build_132(
            {
                (0, 6): "SUSAEV",
                (6, 10): "KZNY",
                (10, 14): "ZNY ",
                (14, 15): "F",
                (18, 43): "NEW YORK CENTER",
                (43, 46): "CTR",
                (46, 53): "0124700",
                (53, 54): " ",
                (54, 55): "V",
                (55, 56): "1",
                (62, 71): "N40450000",
                (71, 81): "W073590000",
                (81, 86): "W0130",
                (86, 91): "00100",
                (91, 92): "Y",
                (103, 107): "JFK ",
                (107, 109): "K6",
                (109, 110): "P",
                (110, 111): "A",
                (123, 128): "12345",
                (128, 132): "2210",
            }
        )
        ev_comb = _build_132(
            {
                (0, 6): "SUSAEV",
                (6, 10): "KZNY",
                (10, 14): "ZNY ",
                (14, 15): "F",
                (18, 43): "NEW YORK CENTER",
                (43, 46): "CTR",
                (46, 53): "0124700",
                (54, 55): "V",
                (55, 56): "2",
                (56, 57): "B",
                (57, 58): "Z",
                (58, 59): "N",
                (59, 60): "Y",
                (60, 70): "CONT      ",
                (93, 123): "NEW YORK CENTER",
                (123, 128): "12346",
                (128, 132): "2210",
            }
        )
        self.assertEqual(len(pb_line), 132)
        self.assertEqual(len(ev_line), 132)
        self.assertEqual(len(ev_comb), 132)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cifp_path = tmp / "FAACIFP18"
            db_path = tmp / "comms.sqlite"
            cifp_path.write_text("\n".join([*HEADER_LINES, pb_line, ev_line, ev_comb]) + "\n")

            c = CIFP(str(cifp_path))
            c.parse_gates()
            c.parse_enroute_comms()

            gates = c.get_gates()
            self.assertEqual(len(gates), 1)
            self.assertEqual(gates[0].primary.airport_id, "KBOS")
            self.assertEqual(gates[0].primary.gate_id, "11")

            comms = c.get_enroute_comms()
            self.assertEqual(len(comms), 1)
            self.assertEqual(comms[0].primary.comm_type, "CTR")
            self.assertEqual(comms[0].primary.freq_unit, "V")
            self.assertAlmostEqual(comms[0].primary.comm_freq, 124.7, places=3)
            self.assertEqual(comms[0].primary.remote_sub_code, "A")
            self.assertEqual(len(comms[0].combined), 1)
            self.assertEqual(comms[0].combined[0].application, "B")
            self.assertEqual(comms[0].combined[0].callsign, "NEW YORK CENTER")

            c.to_db(str(db_path))
            with sqlite3.connect(db_path) as conn:
                tables = {
                    r[0]
                    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                self.assertIn("airport_gates", tables)
                self.assertIn("enroute_comms", tables)
                self.assertIn("enroute_comm_combineds", tables)

    def test_section_r_routes_company_routes_and_to_db(self) -> None:
        company_route_line = _build_132(
            {
                (0, 6): "SUSAR ",
                (6, 11): "KJFK ",
                (12, 14): "K6",
                (14, 15): "P",
                (15, 16): "A",
                (16, 21): "KLAX ",
                (22, 24): "K2",
                (24, 25): "P",
                (25, 26): "A",
                (26, 36): "JFKLAX0001",
                (36, 39): "001",
                (39, 42): "J80",
                (42, 48): "J80   ",
                (72, 77): "FL350",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        self.assertEqual(len(company_route_line), 132)
        sec_r = SectionR([company_route_line])
        self.assertEqual(sec_r.get_company_routes(), [company_route_line])
        self.assertEqual(sec_r.get_alternate_records(), [])

        cr = CompanyRoutePrimary().from_line(company_route_line)
        self.assertEqual(cr.from_1, "KJFK")
        self.assertEqual(cr.from_region_1, "K6")
        self.assertEqual(cr.seq_no, 1)
        self.assertEqual(cr.via, "J80")
        self.assertEqual(cr.cruise_fl, True)
        self.assertEqual(cr.cruise_altitude, 350)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cifp_path = tmp / "FAACIFP18"
            db_path = tmp / "croute.sqlite"
            cifp_path.write_text("\n".join([*HEADER_LINES, company_route_line]) + "\n")
            c = CIFP(str(cifp_path))
            c.parse_company_routes()
            self.assertEqual(len(c.get_company_routes()), 1)
            c.to_db(str(db_path))
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT company_route_id, cruise_fl, cruise_altitude FROM company_routes"
                ).fetchone()
                self.assertEqual(row, ("JFKLAX0001", 1, 350))

    def test_section_p_routes_terminal_ndbs(self) -> None:
        pn_line = (
            "SLAMPNTISXTI ST    TI002410HO W N17413092W064530474                       W0130           NARPESTE                         176941605"
        )
        sec_p = SectionP([pn_line])
        self.assertEqual(sec_p.get_terminal_ndbs(), [pn_line])


class TestCommFrequenciesBlankTypeAndReturnSelf(unittest.TestCase):
    def test_supplemental_type_functions_handle_none_without_type_error(self) -> None:
        self.assertIsNone(field_534("01140", None))
        self.assertIsNone(field_5103("0118400", None))
        self.assertIsNone(field_5265("000600", None))

        blank_comm_pv = _build_132(
            {
                (0, 5): "SUSAP",
                (6, 10): "KJFK",
                (10, 12): "K6",
                (12, 13): "V",
                (13, 16): "TWR",
                (16, 23): "0118400",
                (24, 25): " ",
                (25, 26): "0",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        self.assertIsNone(TerminalCommPrimary().from_line(blank_comm_pv).comm_freq)

        blank_marker = _build_132(
            {
                (0, 5): "SUSAP",
                (6, 10): "KJFK",
                (10, 12): "K6",
                (12, 13): "M",
                (13, 17): "IJFK",
                (17, 18): " ",
                (21, 22): "0",
                (22, 27): "00350",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        self.assertIsNone(TerminalMarkerPrimary().from_line(blank_marker).frequency)

        blank_tch_pp = _build_132(
            {
                (0, 5): "SUSAP",
                (6, 10): "KMHV",
                (10, 12): "K2",
                (12, 13): "P",
                (13, 19): "R30   ",
                (19, 24): "RW30 ",
                (26, 27): "1",
                (102, 108): "000600",
                (108, 109): " ",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        self.assertIsNone(PathPointPrimary().from_line(blank_tch_pp).path_point_tch)

    def test_comm_frequency_extracts_freq_unit_before_comm_freq(self) -> None:
        ev_line = _build_132(
            {
                (0, 6): "SUSAEV",
                (6, 10): "KZNY",
                (43, 46): "TWR",
                (46, 53): "0118400",
                (54, 55): "V",
                (55, 56): "0",
                (123, 128): "12345",
                (128, 132): "2210",
            }
        )
        pv_line = _build_132(
            {
                (0, 5): "SUSAP",
                (6, 10): "KJFK",
                (12, 13): "V",
                (13, 16): "TWR",
                (16, 23): "0118400",
                (24, 25): "V",
                (25, 26): "0",
                (123, 128): "12345",
                (128, 132): "2210",
            }
        )
        hv_line = _build_132(
            {
                (0, 5): "SUSAH",
                (6, 10): "87N ",
                (12, 13): "V",
                (13, 16): "TWR",
                (16, 23): "0121500",
                (24, 25): "C",
                (25, 26): "0",
                (123, 128): "12345",
                (128, 132): "2210",
            }
        )

        ec = EnrouteCommPrimary().from_line(ev_line)
        tc = TerminalCommPrimary().from_line(pv_line)
        hc = HeliTerminalCommPrimary().from_line(hv_line)
        self.assertAlmostEqual(ec.comm_freq, 118.4, places=3)
        self.assertAlmostEqual(tc.comm_freq, 118.4, places=3)
        self.assertAlmostEqual(hc.comm_freq, 121.5, places=3)

    def test_from_line_returns_self_for_marker_cruise_and_loc_gs_simulation(self) -> None:
        marker_line = _build_132(
            {
                (0, 6): "SUSAEM",
                (13, 17): "LOM ",
                (19, 21): "K6",
                (21, 22): "0",
                (22, 26): "OM  ",
                (27, 28): "C",
                (28, 29): "H",
                (32, 41): "N40380000",
                (41, 51): "W073460000",
                (51, 55): "0450",
                (74, 79): "W0130",
                (79, 84): "00013",
                (84, 87): "NAR",
                (93, 123): "JFK OUTER MARKER",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        cruise_line = _build_132(
            {
                (0, 1): "S",
                (4, 6): "TC",
                (6, 8): "AA",
                (8, 9): "1",
                (28, 32): "0000",
                (32, 36): "1800",
                (36, 37): "M",
                (39, 44): "18000",
                (44, 49): "02000",
                (49, 54): "35000",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        ibos_pri = (
            "SUSAP KBOSK6IIBOS3   111030RW04RN42225597W0705948190350N42212182W0710024552058 10160327300W0150  00010IBOSK6D 051          990392211"
        )
        ibos_sim = (
            "SUSAP KBOSK6IIBOS3   2S    S  N                    02090N                                                                  990402402"
        )
        self.assertEqual(len(marker_line), 132)
        self.assertEqual(len(cruise_line), 132)
        self.assertEqual(len(ibos_pri), 132)
        self.assertEqual(len(ibos_sim), 132)

        marker = AirwayMarkerPrimary().from_line(marker_line)
        self.assertIsNotNone(marker)
        self.assertEqual(marker.marker_id, "LOM ")
        self.assertEqual(marker.marker_name, "JFK OUTER MARKER")

        cruise = CruiseTablePrimary().from_line(cruise_line)
        self.assertIsNotNone(cruise)
        self.assertEqual(cruise.to_dict()["cruise_id"], "AA")

        loc = LOC_GS([ibos_pri, ibos_sim])
        self.assertIsNotNone(loc.primary)
        self.assertEqual(len(loc.simulation), 1)
        loc_dict = loc.to_dict()
        self.assertEqual(loc_dict["simulation"][0]["application"], "S")
        self.assertAlmostEqual(loc_dict["simulation"][0]["true_bearing"], 2.09, places=2)
        self.assertFalse(loc_dict["simulation"][0]["source"])


class TestInheritanceListAppendsAndTrailingCalls(unittest.TestCase):
    def test_all_planning_continuation_and_closure_classes_instantiate(self) -> None:
        expected = [
            (AirportPlanningContinuation(), "airport_planning_continuations"),
            (HeliportPlanningContinuation(), "heliport_planning_continuations"),
            (VHFPlanningContinuation(), "vhf_planning_continuations"),
            (NDBPlanningContinuation(), "ndb_planning_continuations"),
            (ProcedurePlanningContinuation(), "procedure_point_planning_continuations"),
            (AirwayPointPlanningContinuation(), "airway_planning_continuations"),
            (HeliProcedurePlanningContinuation(), "heli_procedure_point_planning_continuations"),
            (HeliWaypointPlanningContinuation(), "heli_terminal_waypoint_planning_continuations"),
            (WaypointPlanningContinuation(False), "waypoint_planning_continuations"),
            (WaypointPlanningContinuation(True), "terminal_waypoint_planning_continuations"),
            (RestrictionClosurePrimary(), "restriction_seasonals"),
        ]
        for instance, table_name in expected:
            self.assertEqual(instance.table_name, table_name)

    def test_airway_point_planning_continuation_appends_multiple_items(self) -> None:
        pri = (
            "SCANER       A1          0150BBGVPPAEA0E    O                         309904802984 05200                                   025162010"
        )
        pla = (
            "SCANER       A1          0150BBGVPPAEA2PAZANAZAN                                                                           025172010"
        )
        plc = (
            "SCANER       A1          0150BBGVPPAEA3Q    O                         309904802984 05200                                   025182010"
        )
        ap = AirwayPoint([pri, pla, plc, pla, plc])
        self.assertIsInstance(ap.planning_continuation, list)
        self.assertEqual(len(ap.planning_continuation), 2)
        self.assertEqual(len(ap.to_dict()["planning_continuation"]), 2)

    def test_airway_restriction_appends_lists_and_to_dict_handles_none_primaries(self) -> None:
        note_pri = _build_132(
            {
                (0, 1): "S",
                (1, 4): "USA",
                (4, 6): "EU",
                (6, 11): "V1   ",
                (12, 15): "001",
                (15, 17): "NR",
                (17, 18): "1",
                (123, 132): "000012210",
            }
        )
        note_con1 = _build_132(
            {
                (0, 1): "S",
                (1, 4): "USA",
                (4, 6): "EU",
                (6, 11): "V1   ",
                (12, 15): "001",
                (15, 17): "NR",
                (17, 18): "2",
                (18, 19): "A",
                (123, 132): "000022210",
            }
        )
        note_con2 = _build_132(
            {
                (0, 1): "S",
                (1, 4): "USA",
                (4, 6): "EU",
                (6, 11): "V1   ",
                (12, 15): "001",
                (15, 17): "NR",
                (17, 18): "3",
                (18, 19): "A",
                (123, 132): "000032210",
            }
        )

        ar = AirwayRestriction([note_pri, note_con1, note_con2])
        self.assertIsInstance(ar.note_continuation, list)
        self.assertEqual(len(ar.note_continuation), 2)
        d = ar.to_dict()
        self.assertIsNone(d["alt_exc_primary"])
        self.assertIsNone(d["cruise_primary"])
        self.assertIsNone(d["closure_primary"])
        self.assertIsNotNone(d["note_primary"])
        self.assertEqual(len(d["note_continuation"]), 2)

        self.assertIsNotNone(RestrictionAltExcPrimary())
        self.assertIsNotNone(RestrictionCruisePrimary())
        self.assertIsNotNone(RestrictionNotePrimary())

    def test_procedure_continuation_unpacks_loc_alt_tuple(self) -> None:
        proc_con_line = _build_132(
            {
                (0, 5): "SUSAP",
                (6, 10): "KOAK",
                (10, 12): "K2",
                (12, 13): "F",
                (13, 19): "I12   ",
                (19, 20): "I",
                (26, 29): "050",
                (29, 34): "RW12 ",
                (38, 39): "2",
                (39, 40): "A",
                (76, 81): "01500",
                (89, 92): "031",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        con = ProcedureContinuation().from_line(proc_con_line)
        self.assertFalse(con.loc_fl)
        self.assertEqual(con.loc_alt, 1500)
        self.assertEqual(con.rnp, 0.3)

    def test_base_to_dict_calls_get_trailing_dict(self) -> None:
        blank = " " * 132
        for cls, tbl in (
            (AlternateRecordBase, "alt"),
            (CompanyRouteBase, "cmp"),
            (HeliProcedureBase, "hpr"),
            (ProcedureBase, "prc"),
            (ReferenceTableBase, "ref"),
        ):
            d = cls(tbl).from_line(blank).to_dict()
            self.assertIn("record_number", d)
            self.assertIn("cycle_data", d)
            self.assertIsNone(d["record_number"])

    def test_enroute_comm_truncated_primary_to_dict_returns_none(self) -> None:
        c = EnrouteComm(["SUSAEVKZNY"])
        self.assertIsNone(c.primary)
        self.assertEqual(c.to_dict()["primary"], None)


class TestCrossIcaoHoldCollisionAndAirspacePartitioning(unittest.TestCase):
    def test_holding_patterns_keep_colliding_fix_id_distinct_across_icao_regions(self) -> None:
        hold_ur = _build_132(
            {
                (0, 6): "SEUREP",
                (6, 10): "ENRT",
                (27, 29): "01",
                (29, 34): "AG   ",
                (34, 36): "UR",
                (36, 38): "DB",
                (38, 39): "0",
                (39, 43): "0900",
                (43, 44): "R",
                (47, 49): "10",
                (49, 54): "FL098",
                (54, 59): "FL200",
                (59, 62): "230",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        hold_lf = _build_132(
            {
                (0, 6): "SEUREP",
                (6, 10): "ENRT",
                (27, 29): "01",
                (29, 34): "AG   ",
                (34, 36): "LF",
                (36, 38): "DB",
                (38, 39): "0",
                (39, 43): "1800",
                (43, 44): "L",
                (44, 47): "054",
                (49, 54): "02500",
                (59, 62): "210",
                (123, 128): "00002",
                (128, 132): "2210",
            }
        )

        holds = Holds([hold_ur, hold_lf])
        self.assertEqual(len(holds.records), 2)
        h_ur, h_lf = holds.records[0].primary, holds.records[1].primary
        self.assertEqual((h_ur.point_id, h_ur.point_region, h_ur.min_fl, h_ur.min_alt), ("AG", "UR", True, 98))
        self.assertEqual((h_lf.point_id, h_lf.point_region, h_lf.min_fl, h_lf.min_alt), ("AG", "LF", False, 2500))
        self.assertEqual(h_ur.leg_time, 1.0)
        self.assertAlmostEqual(h_lf.leg_length, 5.4, places=2)

    def test_controlled_airspace_partitions_volumes_by_mult_code_and_seq_no(self) -> None:
        uc_a1 = "SCANUCPAAPANC PAC  A00100     G N61103600W149585900                              GND  A04100MANCHORAGE                     144492205"
        uc_a2 = "SCANUCPAAPANC PAC  A00200     G N61103600W149512800                                                                        144502205"
        uc_b1 = "SCANUCPAAPANC PAC  B00100     G N61065400W149512800                              00600M04100MANCHORAGE                     144542205"
        controlled = Controlleds([uc_a1, uc_a2, uc_b1])
        self.assertEqual(len(controlled.records), 3)
        self.assertEqual([(c.primary.mult_code, c.primary.seq_no) for c in controlled.records], [("A", 10), ("A", 20), ("B", 10)])


class TestDifferentialAndStaticAuditFixes(unittest.TestCase):
    def test_gls_channel_extracts_channel_string_and_exports_to_sqlite(self) -> None:
        gls_line = (
            "SSPAP YSSYYMTG07A1   022790RW07                    0620S33575258E151110525YSSY         300E0130  00021WGE     00034        464892003"
        )
        self.assertEqual(len(gls_line), 132)
        gls = GLSPrimary().from_line(gls_line)
        self.assertEqual(gls.gls_channel, "22790")
        self.assertFalse(gls.true)
        self.assertAlmostEqual(gls.gls_bearing, 62.0, places=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cifp_path = tmp / "FAACIFP18"
            db_path = tmp / "gls.sqlite"
            cifp_path.write_text("\n".join([*HEADER_LINES, gls_line]) + "\n")
            c = CIFP(str(cifp_path))
            c.parse_glss()
            c.to_db(str(db_path))
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT fac_id, gls_ref_id, gls_channel, gls_bearing FROM glss"
                ).fetchone()
                self.assertEqual(row, ("YSSY", "G07A", "22790", 62.0))

    def test_mls_continuation_reads_cov_right(self) -> None:
        mls_con_line = _build_132(
            {
                (0, 5): "SUSAP",
                (6, 10): "KJFK",
                (10, 12): "K6",
                (12, 13): "L",
                (13, 17): "IJFK",
                (17, 18): "1",
                (21, 22): "2",
                (22, 23): "A",
                (51, 55): "0440",
                (83, 86): "040",
                (86, 89): "040",
                (89, 92): "060",
                (92, 95): "065",
                (95, 100): "04400",
                (100, 101): "Y",
                (101, 106): "04410",
                (106, 107): "Y",
                (107, 109): "50",
                (123, 128): "00002",
                (128, 132): "2210",
            }
        )
        con = MLSContinuation().from_line(mls_con_line)
        self.assertEqual(con.cov_right, 60)
        self.assertEqual(con.cov_left, 65)

    def test_airway_restriction_start_point_fields_and_note_continuation_slice(self) -> None:
        alt_exc_line = _build_132(
            {
                (0, 6): "SUSAEU",
                (6, 11): "J80  ",
                (12, 15): "001",
                (15, 17): "AE",
                (17, 18): "1",
                (18, 23): "START",
                (23, 25): "K2",
                (25, 26): "E",
                (26, 27): "A",
                (27, 32): "ENDFX",
                (32, 34): "K6",
                (34, 35): "D",
                (35, 36): " ",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        aex = RestrictionAltExcPrimary().from_line(alt_exc_line)
        self.assertEqual(
            (aex.start_point_id, aex.start_point_region, aex.start_point_sec_code, aex.start_point_sub_code),
            ("START", "K2", "E", "A"),
        )
        self.assertEqual(
            (aex.end_point_id, aex.end_point_region, aex.end_point_sec_code, aex.end_point_sub_code),
            ("ENDFX", "K6", "D", None),
        )

        note_pri_line = _build_132(
            {
                (0, 6): "SUSAEU",
                (6, 11): "J80  ",
                (12, 15): "001",
                (15, 17): "NR",
                (17, 18): "1",
                (18, 23): "BEGFX",
                (23, 25): "K1",
                (25, 26): "E",
                (26, 27): "A",
                (27, 32): "FINFX",
                (32, 34): "K7",
                (34, 35): "P",
                (35, 36): "C",
                (51, 120): "PRIMARY RESTRICTION NOTE",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        npri = RestrictionNotePrimary().from_line(note_pri_line)
        self.assertEqual(
            (npri.start_point_id, npri.start_point_region, npri.start_point_sec_code, npri.start_point_sub_code),
            ("BEGFX", "K1", "E", "A"),
        )
        self.assertEqual(
            (npri.end_point_id, npri.end_point_region, npri.end_point_sec_code, npri.end_point_sub_code),
            ("FINFX", "K7", "P", "C"),
        )

        note_con_line = _build_132(
            {
                (0, 6): "SUSAEU",
                (6, 11): "J80  ",
                (12, 15): "001",
                (15, 17): "NR",
                (17, 18): "2",
                (18, 19): "A",
                (51, 120): "CONTINUATION RESTRICTION NOTE TEXT BEYOND COL 44",
                (123, 128): "00002",
                (128, 132): "2210",
            }
        )
        ncon = RestrictionNoteContinuation().from_line(note_con_line)
        self.assertEqual(ncon.notes, "CONTINUATION RESTRICTION NOTE TEXT BEYOND COL 44")

    def test_cruise_table_extracts_all_four_level_bands(self) -> None:
        cruise_line = _build_132(
            {
                (0, 1): "S",
                (4, 6): "TC",
                (6, 8): "AA",
                (8, 9): "1",
                (28, 32): "0000",
                (32, 36): "1799",
                (36, 37): "M",
                (39, 44): "03000",
                (44, 49): "02000",
                (49, 54): "27000",
                (54, 59): "29000",
                (59, 64): "04000",
                (64, 69): "41000",
                (69, 74): "43000",
                (74, 79): "04000",
                (79, 84): "51000",
                (84, 89): "53000",
                (89, 94): "04000",
                (94, 99): "61000",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        ct = CruiseTablePrimary().from_line(cruise_line)
        self.assertEqual((ct.level_from_1, ct.vert_sep_1, ct.level_to_1), ("03000", "02000", "27000"))
        self.assertEqual((ct.level_from_2, ct.vert_sep_2, ct.level_to_2), ("29000", "04000", "41000"))
        self.assertEqual((ct.level_from_3, ct.vert_sep_3, ct.level_to_3), ("43000", "04000", "51000"))
        self.assertEqual((ct.level_from_4, ct.vert_sep_4, ct.level_to_4), ("53000", "04000", "61000"))

    def test_reference_table_sixth_route_and_et_indicator_do_not_overlap(self) -> None:
        ref_line = _build_132(
            {
                (0, 6): "SUSATR",
                (6, 8): "A1",
                (8, 9): "1",
                (9, 38): "NORTH ATLANTIC",
                (38, 39): "0",
                (100, 110): "PREFROUTE6",
                (110, 112): "E2",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        ref = ReferenceTablePrimary().from_line(ref_line)
        self.assertEqual(ref.pref_route_id_6, "PREFROUTE6")
        self.assertEqual(ref.et_ind_6, "E2")

    def test_heli_procedure_planning_leg_dist_is_scalar_float(self) -> None:
        hp_plan_line = _build_132(
            {
                (0, 5): "SUSAH",
                (6, 10): "87N ",
                (10, 12): "K6",
                (12, 13): "F",
                (13, 19): "R190  ",
                (26, 29): "010",
                (38, 39): "2",
                (39, 40): "P",
                (40, 41): "S",
                (41, 52): "20210128   ",
                (74, 78): "0125",
                (123, 128): "00001",
                (128, 132): "2210",
            }
        )
        hp_plan = HeliProcedurePlanning().from_line(hp_plan_line)
        self.assertIsInstance(hp_plan.leg_dist, float)
        self.assertAlmostEqual(hp_plan.leg_dist, 12.5, places=1)


if __name__ == "__main__":
    unittest.main()
