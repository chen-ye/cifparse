"""End-to-end record and SQLite tests across all 18 active FAACIFP18 families.

Fixtures are 132-byte public-domain FAA CIFP lines. Test cases and edge-case
assertions adapted from:
- mitre-public/boogie (Apache-2.0, Copyright MITRE)
- RISCfuture/SwiftCIFP (MIT, Copyright 2026 Tim Morgan)
- AeronauticalMaps/libefb (Apache-2.0)
- mploscos/arinc424-toolkit (MIT, Copyright 2026 Marcos Perez Loscos)
"""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from cifparse import CIFP

HEADER_LINES = [
    "HDR01FAACIFP18      001P013203769782101  07-JAN-202113:45:45  U.S.A. DOT FAA                                                BF9354BE",
    "HDR02                                 FEDERAL AVIATION ADMINISTRATION                                                               ",
    "HDR03                                 AERONAUTICAL INFORMATION SERVICES                                                             ",
    "HDR04                                 CODED INSTRUMENT FLIGHT PROCEDURES VOLUME 2101  EFFECTIVE 28 JAN 2021                         ",
    "HDR05                                 REPORT DATA ERRORS TO FAA                 TEL 800 638 8972                                    ",
]

ACTIVE_FAMILY_LINES = [
    # 1. MORAs (AS)
    "S   AS       N24W090          UNKUNKUNKUNKUNKUNKUNKUNK152017035035036035UNKUNKUNKUNKUNKUNKUNKUNKUNKUNKUNKUNKUNKUNKUNKUNK   000551703",
    # 2. VHF Navaids (D) — including negative DME elevation
    "SCAND        ADK   PA011400 DUW                    ADK N51521587W176402739E0070003291     NARMOUNT MOFFETT                 002361703",
    "SUSAD        IPL   K2011590VTH  N32445592W115303090    N32445592W115303090E0140-00182     NARIMPERIAL                      253211605",
    # 3. NDB Navaids (DB + PN Terminal NDB) including IL K4/K5 regional collision
    "SCANDB       ACE   PA002770H  W N59382880W151300099                       E0170           NARKACHEMAK                      003602002",
    "SUSADB       IL    K4002780HOLW N31012674W097422925                       E0050           NARIRESH                         249641811",
    "SUSADB       IL    K5004070HOMW N39293492W083441745                       W0040           NARAIRBO                         249651708",
    "SLAMPNTISXTI ST    TI002410HO W N17413092W064530474                       W0130           NARPESTE                         176941605",
    # 4. Enroute Waypoints (EA)
    "SCANEAENRT   AAMYY PA0    R   H N51301880E171091170                       W0012     NAR           AAMYY                    004512008",
    # 5. Airway Points (ER)
    "SCANER       A1          0150BBGVPPAEA0E    O                         309904802984 05200                                   025162010",
    # 6. Heliports (HA)
    "SCANH 01AKPAA   H1   0     NARN N60062086W149264652E023000120         1800018000P    040040M PROVIDENCE SEWARD MEDICAL CENT040821703",
    # 7. Heli Terminal Waypoints (HC)
    "SUSAH 87N K6CCRANN K60    W     N40514240W072275511                       W0135     NAR           CRANN                    718542008",
    # 8. Heli Procedures (HF + W SBAS LOS continuation)
    "SUSAH 87N K6FR190  ACCC   010CCC  K6D 0V       IF                                             18000                 B PS   718572010",
    "SUSAH 87N K6FR190  R      020STAYSK6HC1E  F 010TF                                 + 01700                 CRANN K6HCB PS   753542010",
    "SUSAH 87N K6FR190  R      020STAYSK6HC2WN          N          ALNAV                                                   PS   753552010",
    # 9. Heli MSAs (HS)
    "SUSAH 87N K6SCRANNK6HC                0   18018001925                                                                  M   718701505",
    # 10. Airports (PA) — including negative elevation (-114) and ignored E extension
    "SCANP 00AKPAA        0     025NSN59565600W151413200E015000252         1800018000P    MNAR    LOWELL FLD                    041442014",
    "SUSAP KTRMK2ATRM     0     085YHN33373601W116093476E0130-0114         1800018000C    MNAR    JACQUELINE COCHRAN RGNL       324931913",
    "SUSAP K1A0K7A        0     022NHN35443400W088332400W004000419         1800018000P    MNAR    CARROLL COUNTY                007122003",
    "SUSAP K1A0K7A        3E1A0                                                                                                 007132003",
    # 11. Terminal Waypoints (PC)
    "SCANP PAAKPACBILNE PA0    W     N52155864W174310737                       E0052     NAR           BILNE                    048902008",
    # 12. Procedures (PD, PE, PF incl. W LOS, RF arc_radius, RNP 152, vert_angle ' 000', neg alt_1)
    "SCANP CYQGCYDBARII25ALL   010HUUTZK5EA0E       IF                                 + 04000     18000                        046421909",
    "SCANP CYQGCYEFOREY24BOBCT 010BOBCTK5EA0E       IF                                             18000                        047331911",
    "SCANP PAAQPAFR10   R      020FAPUNPAPC1E  F 010TF                     06710061    + 02300                 RW10  PAPGA JS   049391812",
    "SCANP PAAQPAFR10   R      020FAPUNPAPC2WALP        N          ALNAV                                                   JS   049401812",
    "SCANP PAFAPAFH02LZ AGLDHL 040OKXACPAPC0E   L010RF       0025001908    11730032    + 03200          210    CFNRF PAPCA-FS   068811707",
    "SPACP PHNLPHFH26L  H      021IBICUPHPC0E S  152TF                                                     -300          A FS   230761711",
    "SCANP PAAKPAFRNV-A R      030MACSUPAPC0EY M 031TF                                   00055              000          B PC   055092204",
    "SUSAP KBWCK2FVOR-B S      030CUSAMK2PC0EY M    CF IPL K2      3445014616450050D     -0128              000          0 DC   422582204",
    # 13. Runways (PG) — including negative threshold elevation (-115)
    "SCANP 01A PAGRW05    0011760463 N62562477W152162256               02034000050050D                                          041461703",
    "SUSAP KTRMK2GRW12    0049951220 N33374862W116101551         -00683-0115000025100V                                          326552506",
    # 14. LOC/GS (PI)
    "SCANP PABEPAIIBET1   011150RW19RN60460657W1615047081925N60470649W1614945101306 08980510300E01105200106                     051701707",
    # 15. Path Points (PP)
    "SCANP PAAQPAPR10   RW10 001 0000W10A0N6135419550W14906023005+008180300N6135067710W14903110925106751648000400F400000FDCE99BD049611812",
    "SCANP PAAQPAPR10   RW10 002E      +00794+00794LPV       58734                                                              049621812",
    # 16. Airport MSAs (PS)
    "SCANP PAAKPASMACSUPAPC                0   18018006325                                                                  M   049151310",
    # 17. Controlled Airspace (UC) — multiple volumes (A & B) with arc segment
    "SCANUCPAAPANC PAC  A00100     G N61103600W149585900                              GND  A04100MANCHORAGE                     134671703",
    "SCANUCPAAPANC PAC  A00200     G N61103600W149512800                                                                        134681703",
    "SCANUCPAAPANC PAC  A00400     R N61082800W150084600N61103600W14958590000522458                                             134701703",
    "SCANUCPAAPANC PAC  B00600     R N61065400W149512800N61103600W14958590000521355   00600M04100MANCHORAGE                     144542205",
    # 18. Restrictive Airspace (UR + C controlling agency continuation)
    "SCANURPAMBIRCH     A00101L    G N64311700W146093100                              00500A04999MBIRCH MOA                     137051703",
    "SCANURPAMBIRCH     A00102C                                                                         FAA ANCHORAGE ARTCC     137061703",
]


class TestActiveCifpFamilies(unittest.TestCase):
    def test_all_fixture_lines_are_132_bytes(self) -> None:
        for line in [*HEADER_LINES, *ACTIVE_FAMILY_LINES]:
            self.assertEqual(len(line), 132, msg=f"bad line length: {line!r}")

    def test_parse_all_18_families_and_export_to_sqlite(self) -> None:
        cifp_text = "\n".join([*HEADER_LINES, *ACTIVE_FAMILY_LINES]) + "\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cifp_path = tmp / "FAACIFP18"
            db_path = tmp / "cifp.sqlite"
            cifp_path.write_text(cifp_text)

            c = CIFP(str(cifp_path))
            c.parse()

            self.assertEqual(len(c.get_moras()), 1)
            self.assertEqual(len(c.get_vhf_navaids()), 2)
            # 3 DB enroute NDBs + 1 PN terminal NDB
            self.assertEqual(len(c.get_ndb_navaids()), 4)
            self.assertEqual(len(c.get_enroute_waypoints()), 1)
            self.assertEqual(len(c.get_airway_points()), 1)
            self.assertEqual(len(c.get_heliports()), 1)
            self.assertEqual(len(c.get_heli_terminal_waypoints()), 1)
            self.assertEqual(len(c.get_heli_procedures()), 2)
            self.assertEqual(len(c.get_heli_msas()), 1)
            self.assertEqual(len(c.get_airports()), 3)
            self.assertEqual(len(c.get_terminal_waypoints()), 1)
            self.assertEqual(len(c.get_procedures()), 7)
            self.assertEqual(len(c.get_runways()), 2)
            self.assertEqual(len(c.get_loc_gss()), 1)
            self.assertEqual(len(c.get_path_points()), 1)
            self.assertEqual(len(c.get_msas()), 1)
            self.assertEqual(len(c.get_controlled()), 4)
            self.assertEqual(len(c.get_restrictive()), 1)
            # Regression check: parse_gates/parse_enroute_comms executed (empty lists, not None)
            self.assertEqual(c.get_gates(), [])
            self.assertEqual(c.get_enroute_comms(), [])

            # Specific assertions across records
            ndbs = [(n.primary.ndb_id, n.primary.ndb_region, n.primary.airport_id) for n in c.get_ndb_navaids()]
            self.assertIn(("IL", "K4", None), ndbs)
            self.assertIn(("IL", "K5", None), ndbs)
            self.assertIn(("ST", "TI", "TISX"), ndbs)

            apts = {a.primary.airport_id: a.primary.to_dict() for a in c.get_airports()}
            self.assertEqual(apts["KTRM"]["elevation"], -114)
            self.assertTrue(apts["KTRM"]["is_ifr"])
            self.assertEqual(apts["K1A0"]["longest"], 2200)

            vhfs = {v.primary.vhf_id: v.primary.to_dict() for v in c.get_vhf_navaids()}
            self.assertEqual(vhfs["IPL"]["dme_elevation"], -18)
            self.assertAlmostEqual(vhfs["ADK"]["frequency"], 114.0, places=2)

            rws = {r.primary.airport_id: r.primary.to_dict() for r in c.get_runways()}
            self.assertEqual(rws["KTRM"]["threshold_elevation"], -115)
            self.assertAlmostEqual(rws["KTRM"]["ellipsoidal_height"], -68.3, places=1)

            procs = {
                (p.primary.fac_id, p.primary.procedure_id, p.primary.seq_no): p
                for p in c.get_procedures()
            }
            self.assertEqual(len(procs[("PAAQ", "R10", 20)].simulation), 1)
            sim = procs[("PAAQ", "R10", 20)].simulation[0].to_dict()
            self.assertEqual(sim["application"], "W")
            self.assertTrue(sim["fas_block"])
            self.assertEqual(sim["fas_service"], "LP")
            self.assertFalse(sim["l_vnav_block"])
            self.assertTrue(sim["lnav_block"])
            self.assertEqual(sim["lnav_service"], "LNAV")

            self.assertAlmostEqual(procs[("PAFA", "H02LZ", 40)].primary.arc_radius, 2.5, places=3)
            self.assertAlmostEqual(procs[("PHNL", "H26L", 21)].primary.rnp, 0.15, places=4)
            self.assertEqual(procs[("PAAK", "RNV-A", 30)].primary.vert_angle, 0.0)
            self.assertEqual(procs[("KBWC", "VOR-B", 30)].primary.alt_1, -128)

            hprocs = {
                (p.primary.fac_id, p.primary.procedure_id, p.primary.seq_no): p
                for p in c.get_heli_procedures()
            }
            self.assertEqual(len(hprocs[("87N", "R190", 20)].simulation), 1)
            self.assertEqual(hprocs[("87N", "R190", 20)].simulation[0].lnav_service, "LNAV")

            restr = c.get_restrictive()[0]
            self.assertEqual(restr.primary.restrictive_id, "BIRCH")
            self.assertEqual(len(restr.time), 1)
            self.assertEqual(restr.time[0].application, "C")
            self.assertEqual(restr.time[0].controlling_agency, "FAA ANCHORAGE ARTCC")

            # Export to SQLite and verify schemas & counts
            c.to_db(str(db_path))
            with sqlite3.connect(db_path) as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertIn("validity", tables)
                self.assertIn("procedure_point_simulations", tables)
                self.assertIn("heli_procedure_point_simulations", tables)
                self.assertIn("restrictive_point_times", tables)
                self.assertIn("path_points", tables)
                self.assertIn("path_point_continuations", tables)

                val = conn.execute(
                    "SELECT cycle_id, valid_from, valid_to FROM validity"
                ).fetchone()
                self.assertEqual(val, ("2101", "2021-01-28", "2021-02-25"))

                mora_cols = {
                    row[1]: row[2]
                    for row in conn.execute("PRAGMA table_info(moras)")
                }
                self.assertEqual(mora_cols["start_lat"], "TEXT")
                self.assertEqual(mora_cols["start_lon"], "TEXT")

                msa_cols = {
                    row[1]: row[2]
                    for row in conn.execute("PRAGMA table_info(msas)")
                }
                self.assertEqual(msa_cols["min_alt_1"], "INTEGER")
                self.assertEqual(msa_cols["radius_1"], "INTEGER")

                rwy_cols = {
                    row[1]: row[2]
                    for row in conn.execute("PRAGMA table_info(runways)")
                }
                self.assertEqual(rwy_cols["ellipsoidal_height"], "REAL")

    def test_special_hdr_and_truncated_line_do_not_crash(self) -> None:
        special_hdr = (
            "HDR GUNNISON                 COUSKGUCRNAV  SIAPRNAV (RNP) Z RWY 24                               ORIG               20210107V18A    "
        )
        truncated = "SUSAP KLAXK2A"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cifp_path = tmp / "SPECIAL"
            db_path = tmp / "special.sqlite"
            cifp_path.write_text(f"{special_hdr}\n{truncated}\n")

            c = CIFP(str(cifp_path))
            c.parse()
            airports = c.get_airports()
            self.assertEqual(len(airports), 1)
            self.assertIsNone(airports[0].primary)
            self.assertEqual(airports[0].to_dict()["primary"], None)
            c.to_db(str(db_path))


if __name__ == "__main__":
    unittest.main()
