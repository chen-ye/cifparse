"""Differential comparator between cifparse and mitre-public/boogie JSONL output."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import gzip
import json
from pathlib import Path
import sys
import tempfile

from cifparse import CIFP


def _norm_alt(is_fl: bool | None, val: int | float | None) -> float | None:
    if val is None:
        return None
    if is_fl:
        return float(val * 100)
    return float(val)


def _norm_str(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s != "" else None


def _values_match(a: object, b: object) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) is bool(b) if isinstance(a, bool) and isinstance(b, bool) else False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= 1e-4
    return str(a).strip() == str(b).strip()


def _make_cp_key(spec_name: str, d: dict) -> tuple:
    rn = d.get("record_number")
    st = d.get("st")
    area = d.get("area")
    if spec_name == "AirportSpec":
        return (spec_name, st, area, d.get("airport_id"), d.get("airport_region"), rn)
    if spec_name == "HeliportSpec":
        return (
            spec_name,
            st,
            area,
            d.get("heliport_id"),
            d.get("heliport_region"),
            d.get("pad_id"),
            rn,
        )
    if spec_name == "RunwaySpec":
        return (
            spec_name,
            st,
            area,
            d.get("airport_id"),
            d.get("airport_region"),
            d.get("runway_id"),
            rn,
        )
    if spec_name == "LocalizerGlideSlopeSpec":
        return (
            spec_name,
            st,
            area,
            d.get("airport_id"),
            d.get("airport_region"),
            d.get("loc_id"),
            rn,
        )
    if spec_name == "GnssLandingSystemSpec":
        return (
            spec_name,
            st,
            area,
            d.get("sec_code"),
            d.get("fac_id"),
            d.get("fac_region"),
            d.get("gls_ref_id"),
            rn,
        )
    if spec_name == "VhfNavaidSpec":
        return (
            spec_name,
            st,
            area,
            d.get("airport_id"),
            d.get("vhf_id"),
            d.get("vhf_region"),
            rn,
        )
    if spec_name == "NdbNavaidSpec":
        return (
            spec_name,
            st,
            area,
            d.get("sec_code"),
            d.get("sub_code"),
            d.get("airport_id"),
            d.get("ndb_id"),
            d.get("ndb_region"),
            rn,
        )
    if spec_name == "WaypointSpec":
        return (
            spec_name,
            st,
            area,
            d.get("sec_code"),
            d.get("environment_id") or d.get("heliport_id"),
            d.get("environment_sub_code") or d.get("heliport_sub_code") or d.get("sub_code"),
            d.get("waypoint_id"),
            d.get("waypoint_region"),
            rn,
        )
    if spec_name == "AirwayLegSpec":
        return (spec_name, st, area, d.get("airway_id"), d.get("seq_no"), d.get("point_id"), rn)
    if spec_name == "ProcedureLegSpec":
        return (
            spec_name,
            st,
            area,
            d.get("sec_code"),
            d.get("fac_id"),
            d.get("fac_sub_code"),
            d.get("procedure_id"),
            d.get("transition_id"),
            d.get("seq_no"),
            d.get("fix_id"),
            rn,
        )
    if spec_name == "HoldingPatternSpec":
        return (
            spec_name,
            st,
            area,
            d.get("environment_id"),
            d.get("dup_ind"),
            d.get("point_id"),
            d.get("point_region"),
            rn,
        )
    if spec_name == "ControlledAirspaceLegSpec":
        return (
            spec_name,
            st,
            area,
            d.get("center_region"),
            d.get("airspace_type"),
            d.get("center_id"),
            d.get("airspace_class"),
            d.get("mult_code"),
            d.get("seq_no"),
            rn,
        )
    if spec_name == "RestrictiveAirspaceLegSpec":
        return (
            spec_name,
            st,
            area,
            d.get("region"),
            d.get("restrictive_type"),
            d.get("restrictive_id"),
            d.get("mult_code"),
            d.get("seq_no"),
            rn,
        )
    if spec_name == "FirUirLegSpec":
        return (
            spec_name,
            st,
            area,
            d.get("fir_uir_id"),
            d.get("fir_uir_addr"),
            d.get("fir_uir_ind"),
            d.get("seq_no"),
            rn,
        )
    raise ValueError(f"Unsupported spec: {spec_name}")


def _make_boogie_key(spec_name: str, bf: dict) -> tuple:
    rn = bf.get("fileRecordNumber")
    st = bf.get("recordType")
    area = bf.get("customerAreaCode")
    if spec_name == "AirportSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("airportIdentifier")),
            _norm_str(bf.get("airportIcaoRegion")),
            rn,
        )
    if spec_name == "HeliportSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("heliportIdentifier")),
            _norm_str(bf.get("heliportIcaoRegion")),
            _norm_str(bf.get("helipadIdentifier")),
            rn,
        )
    if spec_name == "RunwaySpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("airportIdentifier")),
            _norm_str(bf.get("airportIcaoRegion")),
            _norm_str(bf.get("runwayIdentifier")),
            rn,
        )
    if spec_name == "LocalizerGlideSlopeSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("airportIdentifier")),
            _norm_str(bf.get("airportIcaoRegion")),
            _norm_str(bf.get("localizerIdentifier")),
            rn,
        )
    if spec_name == "GnssLandingSystemSpec":
        return (
            spec_name,
            st,
            area,
            bf.get("sectionCode"),
            _norm_str(bf.get("airportIdentifier")),
            _norm_str(bf.get("airportIcaoRegion")),
            _norm_str(bf.get("glsRefPathIdentifier")),
            rn,
        )
    if spec_name == "VhfNavaidSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("airportIdentifier")),
            _norm_str(bf.get("vhfIdentifier")),
            _norm_str(bf.get("vhfIcaoRegion")),
            rn,
        )
    if spec_name == "NdbNavaidSpec":
        return (
            spec_name,
            st,
            area,
            bf.get("sectionCode"),
            bf.get("subSectionCode"),
            _norm_str(bf.get("airportIdentifier")),
            _norm_str(bf.get("ndbIdentifier")),
            _norm_str(bf.get("ndbIcaoRegion")),
            rn,
        )
    if spec_name == "WaypointSpec":
        sec = bf.get("sectionCode")
        sub = bf.get("terminalSubSectionCode") or bf.get("enrouteSubSectionCode")
        env = _norm_str(bf.get("airportIdentifier"))
        return (
            spec_name,
            st,
            area,
            sec,
            env,
            sub,
            _norm_str(bf.get("waypointIdentifier")),
            _norm_str(bf.get("waypointIcaoRegion")),
            rn,
        )
    if spec_name == "AirwayLegSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("routeIdentifier")),
            bf.get("sequenceNumber"),
            _norm_str(bf.get("fixIdentifier")),
            rn,
        )
    if spec_name == "ProcedureLegSpec":
        return (
            spec_name,
            st,
            area,
            bf.get("sectionCode"),
            _norm_str(bf.get("airportIdentifier")),
            bf.get("subSectionCode"),
            _norm_str(bf.get("sidStarIdentifier")),
            _norm_str(bf.get("transitionIdentifier")),
            bf.get("sequenceNumber"),
            _norm_str(bf.get("fixIdentifier")),
            rn,
        )
    if spec_name == "HoldingPatternSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("regionCode")),
            _norm_str(bf.get("duplicateIdentifier")),
            _norm_str(bf.get("fixIdentifier")),
            _norm_str(bf.get("fixIcaoRegion")),
            rn,
        )
    if spec_name == "ControlledAirspaceLegSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("icaoRegion")),
            _norm_str(bf.get("airspaceType")),
            _norm_str(bf.get("airspaceCenter")),
            _norm_str(bf.get("airspaceClassification")),
            _norm_str(bf.get("multipleCode")),
            bf.get("sequenceNumber"),
            rn,
        )
    if spec_name == "RestrictiveAirspaceLegSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("icaoRegion")),
            _norm_str(bf.get("restrictiveType")),
            _norm_str(bf.get("restrictiveAirspaceDesignation")),
            _norm_str(bf.get("multipleCode")),
            bf.get("sequenceNumber"),
            rn,
        )
    if spec_name == "FirUirLegSpec":
        return (
            spec_name,
            st,
            area,
            _norm_str(bf.get("firUirIdentifier")),
            _norm_str(bf.get("firUirAddress")),
            _norm_str(bf.get("firUirIndicator")),
            bf.get("sequenceNumber"),
            rn,
        )
    raise ValueError(f"Unsupported spec: {spec_name}")


MAPPINGS = {
    "AirportSpec": [
        ("st", lambda b: b["recordType"], "str"),
        ("area", lambda b: b["customerAreaCode"], "str"),
        ("airport_id", lambda b: b["airportIdentifier"], "str"),
        ("airport_region", lambda b: b["airportIcaoRegion"], "str"),
        ("iata", lambda b: b["iataDesignator"], "str"),
        ("limit_alt", lambda b: b["speedLimitAltitude"], "alt_pair:fl"),
        ("longest", lambda b: b["longestRunway"], "num"),
        ("is_ifr", lambda b: b["ifrCapability"], "bool"),
        ("longest_surface", lambda b: b["longestRunwaySurfaceCode"], "str"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("mag_var", lambda b: b["magneticVariation"], "num"),
        ("elevation", lambda b: b["airportElevation"], "num"),
        ("speed_limit", lambda b: b["speedLimit"], "num"),
        ("rec_vhf", lambda b: b["recommendedNavaid"], "str"),
        ("rec_vhf_region", lambda b: b["recommendedNavaidIcaoRegion"], "str"),
        ("transition_alt", lambda b: b["transitionAltitude"], "num"),
        ("transition_level", lambda b: b["transitionLevel"], "num"),
        ("usage", lambda b: b["publicMilitaryIndicator"], "str"),
        ("daylight_ind", lambda b: b["daylightTimeIndicator"], "bool_blank_false"),
        ("mag_true", lambda b: b["magneticTrueIndicator"], "str"),
        ("datum_code", lambda b: b["datumCode"], "str"),
        ("airport_name", lambda b: b["airportFullName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "HeliportSpec": [
        ("heliport_id", lambda b: b["heliportIdentifier"], "str"),
        ("heliport_region", lambda b: b["heliportIcaoRegion"], "str"),
        ("iata", lambda b: b["iataDesignator"], "str"),
        ("pad_id", lambda b: b["helipadIdentifier"], "str"),
        ("limit_alt", lambda b: b["speedLimitAltitude"], "alt_pair:fl"),
        ("datum_code", lambda b: b["datumCode"], "str"),
        ("is_ifr", lambda b: b["ifrCapability"], "bool"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("mag_var", lambda b: b["magneticVariation"], "num"),
        ("elevation", lambda b: b["heliportElevation"], "num"),
        ("speed_limit", lambda b: b["speedLimit"], "num"),
        ("rec_vhf", lambda b: b["recommendedVhfNavaid"], "str"),
        ("rec_vhf_region", lambda b: b["recommendedVhfNavaidIcaoRegion"], "str"),
        ("transition_alt", lambda b: b["transitionAltitude"], "num"),
        ("transition_level", lambda b: b["transitionLevel"], "num"),
        ("usage", lambda b: b["publicMilitaryIndicator"], "str"),
        ("daylight_ind", lambda b: b["daylightTimeIndicator"], "bool_blank_false"),
        ("pad_dimensions", lambda b: b["padDimensions"], "str"),
        ("mag_true", lambda b: b["magneticTrueIndicator"], "str"),
        ("heliport_name", lambda b: b["heliportFullName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdatedCycle"], "str"),
    ],
    "RunwaySpec": [
        ("airport_id", lambda b: b["airportIdentifier"], "str"),
        ("airport_region", lambda b: b["airportIcaoRegion"], "str"),
        ("runway_id", lambda b: b["runwayIdentifier"], "str"),
        ("length", lambda b: b["runwayLength"], "num"),
        ("bearing", lambda b: b["runwayMagneticBearing"], "brg:true:27:31"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("gradient", lambda b: b["runwayGradient"], "num"),
        ("threshold_elevation", lambda b: b["landingThresholdElevation"], "num"),
        ("displaced_threshold", lambda b: b["thresholdDisplacementDistance"], "num"),
        ("tch", lambda b: b["thresholdCrossingHeight"], "num"),
        ("width", lambda b: b["runwayWidth"], "num"),
        ("ls_ident_1", lambda b: b["ilsMlsGlsIdentifier"], "str"),
        ("cat_1", lambda b: b["ilsMlsGlsCategory"], "str"),
        ("stopway", lambda b: b["stopway"], "num"),
        ("ls_ident_2", lambda b: b["secondaryIlsMlsGlsIdentifier"], "str"),
        ("cat_2", lambda b: b["secondaryIlsMlsGlsCategory"], "str"),
        ("description", lambda b: b["runwayDescription"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "LocalizerGlideSlopeSpec": [
        ("airport_id", lambda b: b["airportIdentifier"], "str"),
        ("airport_region", lambda b: b["airportIcaoRegion"], "str"),
        ("loc_id", lambda b: b["localizerIdentifier"], "str"),
        ("cat", lambda b: b["ilsMlsGlsCategory"], "str"),
        ("frequency", lambda b: b["localizerFrequency"], "num"),
        ("runway_id", lambda b: b["runwayIdentifier"], "str"),
        ("loc_lat", lambda b: b["localizerLatitude"], "num"),
        ("loc_lon", lambda b: b["localizerLongitude"], "num"),
        ("loc_bearing", lambda b: b["localizerBearing"], "brg:true:51:55"),
        ("gs_lat", lambda b: b["glideSlopeLatitude"], "num"),
        ("gs_lon", lambda b: b["glideSlopeLongitude"], "num"),
        ("loc_dist", lambda b: b["localizerPosition"], "num"),
        ("plus_minus", lambda b: b["localizerPositionReference"], "str"),
        ("gs_thr_dist", lambda b: b["glideSlopePosition"], "num"),
        ("loc_width", lambda b: b["localizerWidth"], "num"),
        ("gs_angle", lambda b: b["glideSlopeAngle"], "num"),
        ("mag_var", lambda b: b["stationDeclination"], "num"),
        ("tch", lambda b: b["glideSlopeHeightAtLandingThreshold"], "num"),
        ("gs_elevation", lambda b: b["glideSlopeElevation"], "num"),
        ("support_fac", lambda b: b["supportingFacilityIdentifier"], "str"),
        ("support_region", lambda b: b["supportingFacilityIcaoRegion"], "str"),
        ("support_sec_code", lambda b: b["supportingFacilitySectionCode"], "str"),
        ("support_sub_code", lambda b: b["supportingFacilitySubSectionCode"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "GnssLandingSystemSpec": [
        ("fac_id", lambda b: b["airportIdentifier"], "str"),
        ("fac_region", lambda b: b["airportIcaoRegion"], "str"),
        ("gls_ref_id", lambda b: b["glsRefPathIdentifier"], "str"),
        ("gls_cat", lambda b: b["glsCategory"], "str"),
        ("gls_channel", lambda b: b["glsChannel"], "str"),
        ("runway_id", lambda b: b["runwayIdentifier"], "str"),
        ("gls_bearing", lambda b: b["glsApproachBearing"], "brg:true:51:55"),
        ("station_lat", lambda b: b["latitude"], "num"),
        ("station_lon", lambda b: b["longitude"], "num"),
        ("gls_id", lambda b: b["glsStationIdentifier"], "str"),
        ("svc_vol", lambda b: b["serviceVolumeRadius"], "num"),
        ("tdma_slots", lambda b: b["tdmaSlots"], "str"),
        ("min_elev_angle", lambda b: b["glsApproachSlope"], "num"),
        ("mag_var", lambda b: b["magneticVariation"], "num"),
        ("station_elev", lambda b: b["stationElevation"], "num"),
        ("datum_code", lambda b: b["datumCode"], "str"),
        ("station_type", lambda b: b["stationType"], "str"),
        ("wgs84_elev", lambda b: b["stationElevationWgs84"], "num"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdatedCycle"], "str"),
    ],
    "VhfNavaidSpec": [
        ("airport_id", lambda b: b["airportIdentifier"], "str"),
        ("airport_region", lambda b: b["airportIcaoRegion"], "str"),
        ("vhf_id", lambda b: b["vhfIdentifier"], "str"),
        ("vhf_region", lambda b: b["vhfIcaoRegion"], "str"),
        ("frequency", lambda b: b["vhfFrequency"], "freq_vhf"),
        ("nav_class", lambda b: b["navaidClass"], "str"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("dme_id", lambda b: b["dmeIdentifier"], "str"),
        ("dme_lat", lambda b: b["dmeLatitude"], "num"),
        ("dme_lon", lambda b: b["dmeLongitude"], "num"),
        ("mag_var", lambda b: b["stationDeclination"], "num"),
        ("dme_elevation", lambda b: b["dmeElevation"], "num"),
        ("figure_of_merit", lambda b: b["figureOfMerit"], "str"),
        ("dme_bias", lambda b: b["ilsDmeBias"], "num"),
        ("frequency_protection", lambda b: b["frequencyProtectionDistance"], "num"),
        ("datum_code", lambda b: b["datumCode"], "str"),
        ("vhf_name", lambda b: b["vhfNavaidName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "NdbNavaidSpec": [
        ("airport_id", lambda b: b["airportIdentifier"], "str"),
        ("airport_region", lambda b: b["airportIcaoRegion"], "str"),
        ("ndb_id", lambda b: b["ndbIdentifier"], "str"),
        ("ndb_region", lambda b: b["ndbIcaoRegion"], "str"),
        ("frequency", lambda b: b["ndbFrequency"], "num"),
        ("nav_class", lambda b: b["navaidClass"], "str"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("mag_var", lambda b: b["magneticVariation"], "num"),
        ("datum_code", lambda b: b["datumCode"], "str"),
        ("ndb_name", lambda b: b["ndbNavaidName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "WaypointSpec": [
        ("environment_region", lambda b: b.get("airportIcaoRegion"), "str"),
        ("waypoint_id", lambda b: b["waypointIdentifier"], "str"),
        ("waypoint_region", lambda b: b["waypointIcaoRegion"], "str"),
        ("type", lambda b: b["waypointType"], "str"),
        ("usage", lambda b: b["waypointUsage"], "str"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("mag_var", lambda b: b["magneticVariation"], "num"),
        ("datum_code", lambda b: b["datumCode"], "str"),
        ("name_indicator", lambda b: b["nameFormat"], "str"),
        ("name_description", lambda b: b["waypointNameDescription"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "AirwayLegSpec": [
        ("airway_id", lambda b: b["routeIdentifier"], "str"),
        ("six_char", lambda b: b["sixthCharacter"], "str"),
        ("seq_no", lambda b: b["sequenceNumber"], "num"),
        ("point_id", lambda b: b["fixIdentifier"], "str"),
        ("point_region", lambda b: b["fixIcaoRegion"], "str"),
        ("point_sec_code", lambda b: b["fixSectionCode"], "str"),
        ("point_sub_code", lambda b: b["fixSubSectionCode"], "str"),
        ("desc_code", lambda b: b["waypointDescription"], "str"),
        ("bound_code", lambda b: b["boundaryCode"], "area_enum"),
        ("route_type", lambda b: b["routeType"], "str"),
        ("level", lambda b: b["level"], "str"),
        ("direct", lambda b: b["directionRestriction"], "str"),
        ("cruise_id", lambda b: b["cruiseTableIndicator"], "str"),
        ("eu_ind", lambda b: b["euIndicator"], "bool_blank_false"),
        ("rec_vhf", lambda b: b["recommendedNavaidIdentifier"], "str"),
        ("rec_vhf_region", lambda b: b["recommendedNavaidIcaoRegion"], "str"),
        ("rnp", lambda b: b["rnp"], "num"),
        ("theta", lambda b: b["theta"], "num"),
        ("rho", lambda b: b["rho"], "num"),
        ("out_mag_crs", lambda b: b["outboundMagneticCourse"], "brg:out_true:70:74"),
        ("from_dist", lambda b: b["routeHoldDistanceTime"], "dist_time:time"),
        ("in_mag_crs", lambda b: b["inboundMagneticCourse"], "brg:in_true:78:82"),
        ("min_alt_1", lambda b: b["minAltitude1"], "alt_pair:min_fl_1"),
        ("min_alt_2", lambda b: b["minAltitude2"], "alt_pair:min_fl_2"),
        ("max_alt", lambda b: b["maxAltitude"], "alt_pair:max_fl"),
        ("fix_radius", lambda b: b["fixedRadiusTransitionIndicator"], "num"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "ProcedureLegSpec": [
        ("fac_id", lambda b: b["airportIdentifier"], "str"),
        ("fac_region", lambda b: b["airportIcaoRegion"], "str"),
        ("fac_sub_code", lambda b: b["subSectionCode"], "str"),
        ("procedure_id", lambda b: b["sidStarIdentifier"], "str"),
        ("procedure_type", lambda b: b["routeType"], "str"),
        ("transition_id", lambda b: b["transitionIdentifier"], "str"),
        ("seq_no", lambda b: b["sequenceNumber"], "num"),
        ("fix_id", lambda b: b["fixIdentifier"], "str"),
        ("fix_region", lambda b: b["fixIcaoRegion"], "str"),
        ("fix_sec_code", lambda b: b["fixSectionCode"], "str"),
        ("fix_sub_code", lambda b: b["fixSubSectionCode"], "str"),
        ("desc_code", lambda b: b["waypointDescription"], "str"),
        ("turn_direction", lambda b: b["turnDirection"], "str"),
        ("rnp", lambda b: b["rnp"], "num"),
        ("path_term", lambda b: b["pathTerm"], "str"),
        ("tdv", lambda b: b["turnDirectionValid"], "tdv_blank_false"),
        ("rec_vhf", lambda b: b["recommendedNavaidIdentifier"], "str"),
        ("rec_vhf_region", lambda b: b["recommendedNavaidIcaoRegion"], "str"),
        ("rec_vhf_sec_code", lambda b: b["recommendedNavaidSectionCode"], "str"),
        ("rec_vhf_sub_code", lambda b: b["recommendedNavaidSubSectionCode"], "str"),
        ("arc_radius", lambda b: b["arcRadius"], "num"),
        ("theta", lambda b: b["theta"], "num"),
        ("rho", lambda b: b["rho"], "num"),
        ("course", lambda b: b["outboundMagneticCourse"], "brg:true:70:74"),
        ("dist_time", lambda b: b["routeHoldDistanceTime"], "dist_time:time"),
        ("alt_desc", lambda b: b["altitudeDescription"], "desc_blank_at"),
        ("alt_1", lambda b: b["minAltitude1"], "alt_pair:fl_1"),
        ("alt_2", lambda b: b["minAltitude2"], "alt_pair:fl_2"),
        ("trans_alt", lambda b: b["transitionAltitude"], "num"),
        ("speed_limit", lambda b: b["speedLimit"], "num"),
        ("vert_angle", lambda b: b["verticalAngle"], "num"),
        ("center_fix", lambda b: b["centerFixIdentifier"], "str"),
        ("center_fix_region", lambda b: b["centerFixIcaoRegion"], "str"),
        ("center_fix_sec_code", lambda b: b["centerFixSectionCode"], "str"),
        ("center_fix_sub_code", lambda b: b["centerFixSubSectionCode"], "str"),
        ("speed_desc", lambda b: b["speedLimitDescription"], "desc_blank_at"),
        ("rte_qual_1", lambda b: b["routeTypeQualifier1"], "str"),
        ("rte_qual_2", lambda b: b["routeTypeQualifier2"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdateCycle"], "str"),
    ],
    "HoldingPatternSpec": [
        ("environment_id", lambda b: b["regionCode"], "str"),
        ("environment_region", lambda b: b["icaoRegion"], "str"),
        ("dup_ind", lambda b: b["duplicateIdentifier"], "str"),
        ("point_id", lambda b: b["fixIdentifier"], "str"),
        ("point_region", lambda b: b["fixIcaoRegion"], "str"),
        ("point_sec_code", lambda b: b["fixSectionCode"], "str"),
        ("point_sub_code", lambda b: b["fixSubSectionCode"], "str"),
        ("in_course", lambda b: b["inboundHoldingCourse"], "brg:true:39:43"),
        ("turn_dir", lambda b: b["turnDirection"], "str"),
        ("leg_length", lambda b: b["legLength"], "num"),
        ("leg_time", lambda b: b["legTime"], "tenths_int"),
        ("min_alt", lambda b: b["minimumAltitude"], "alt_pair:min_fl"),
        ("max_alt", lambda b: b["maxAltitude"], "alt_pair:max_fl"),
        ("hold_speed", lambda b: b["holdingSpeed"], "num"),
        ("rnp", lambda b: b["rnp"], "num"),
        ("arc_radius", lambda b: b["arcRadius"], "num"),
        ("hold_name", lambda b: b["holdingName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["lastUpdatedCycle"], "str"),
    ],
    "ControlledAirspaceLegSpec": [
        ("center_region", lambda b: b["icaoRegion"], "str"),
        ("airspace_type", lambda b: b["airspaceType"], "str"),
        ("center_id", lambda b: b["airspaceCenter"], "str"),
        ("center_sec_code", lambda b: b["sectionCode2"], "str"),
        ("center_sub_code", lambda b: b["subSectionCode2"], "str"),
        ("airspace_class", lambda b: b["airspaceClassification"], "str"),
        ("mult_code", lambda b: b["multipleCode"], "str"),
        ("seq_no", lambda b: b["sequenceNumber"], "num"),
        ("level", lambda b: b["level"], "str"),
        ("time_zone", lambda b: b["timeCode"], "str"),
        ("notam", lambda b: b["notam"], "str"),
        ("boundary_via", lambda b: b["boundaryVia"], "str"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("arc_lat", lambda b: b["arcOriginLatitude"], "num"),
        ("arc_lon", lambda b: b["arcOriginLongitude"], "num"),
        ("arc_dist", lambda b: b["arcDistance"], "num"),
        ("arc_bearing", lambda b: b["arcBearing"], "num"),
        ("rnp", lambda b: b["rnp"], "num"),
        ("lower_limit", lambda b: b["lowerLimit"], "str"),
        ("lower_unit", lambda b: b["lowerIndicator"], "str"),
        ("upper_limit", lambda b: b["upperLimit"], "str"),
        ("upper_unit", lambda b: b["upperIndicator"], "str"),
        ("airspace_name", lambda b: b["controlledAirspaceName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["cycle"], "str"),
    ],
    "RestrictiveAirspaceLegSpec": [
        ("region", lambda b: b["icaoRegion"], "str"),
        ("restrictive_type", lambda b: b["restrictiveType"], "str"),
        ("restrictive_id", lambda b: b["restrictiveAirspaceDesignation"], "str"),
        ("mult_code", lambda b: b["multipleCode"], "str"),
        ("seq_no", lambda b: b["sequenceNumber"], "num"),
        ("level", lambda b: b["level"], "str"),
        ("time_zone", lambda b: b["timeCode"], "str"),
        ("notam", lambda b: b["notam"], "str"),
        ("boundary_via", lambda b: b["boundaryVia"], "str"),
        ("lat", lambda b: b["latitude"], "num"),
        ("lon", lambda b: b["longitude"], "num"),
        ("arc_lat", lambda b: b["arcOriginLatitude"], "num"),
        ("arc_lon", lambda b: b["arcOriginLongitude"], "num"),
        ("arc_dist", lambda b: b["arcDistance"], "num"),
        ("arc_bearing", lambda b: b["arcBearing"], "num"),
        ("lower_limit", lambda b: b["lowerLimit"], "str"),
        ("lower_unit", lambda b: b["lowerIndicator"], "str"),
        ("upper_limit", lambda b: b["upperLimit"], "str"),
        ("upper_unit", lambda b: b["upperIndicator"], "str"),
        ("restrictive_name", lambda b: b["restrictiveAirspaceName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["cycle"], "str"),
    ],
    "FirUirLegSpec": [
        ("fir_uir_id", lambda b: b["firUirIdentifier"], "str"),
        ("fir_uir_addr", lambda b: b["firUirAddress"], "str"),
        ("fir_uir_ind", lambda b: b["firUirIndicator"], "str"),
        ("seq_no", lambda b: b["sequenceNumber"], "num"),
        ("adj_fir_id", lambda b: b["adjacentFirIdentifier"], "str"),
        ("adj_uir_id", lambda b: b["adjacentUirIdentifier"], "str"),
        ("rus", lambda b: b["reportingUnitsSpeed"], "str"),
        ("rua", lambda b: b["reportingUnitsAltitude"], "str"),
        ("entry", lambda b: b["firUirEntryReport"], "bool"),
        ("boundary_via", lambda b: b["boundaryVia"], "str"),
        ("fir_uir_lat", lambda b: b["firUirLatitude"], "num"),
        ("fir_uir_lon", lambda b: b["firUirLongitude"], "num"),
        ("arc_lat", lambda b: b["arcOriginLatitude"], "num"),
        ("arc_lon", lambda b: b["arcOriginLongitude"], "num"),
        ("arc_dist", lambda b: b["arcDistance"], "num"),
        ("arc_bearing", lambda b: b["arcBearing"], "num"),
        ("fir_upper_limit", lambda b: b["firUpperLimit"], "str"),
        ("uir_lower_limit", lambda b: b["uirLowerLimit"], "str"),
        ("uir_upper_limit", lambda b: b["uirUpperLimit"], "str"),
        ("cruise_id", lambda b: b["cruiseTableIndicator"], "str"),
        ("fir_uir_name", lambda b: b["firUirName"], "str"),
        ("cont_rec_no", lambda b: b["continuationRecordNumber"], "cont_no"),
        ("cycle_data", lambda b: b["cycle"], "str"),
    ],
}

AREA_MAP = {
    "P": "PAC",
    "U": "USA",
    "C": "CAN",
    "E": "EUR",
    "A": "AFR",
    "S": "SAM",
    "L": "LAM",
    "M": "MES",
    "I": "IND",
    "N": "NAT",
}


@dataclass
class DiffResult:
    indexed: int
    collisions: dict[str, int] = field(default_factory=dict)
    missing_in_cifparse: dict[tuple, int] = field(default_factory=dict)
    checked: dict[str, int] = field(default_factory=dict)
    diff_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    diff_examples: dict[tuple[str, str], list[tuple[object, object, str]]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.missing_in_cifparse and not self.diff_counts


def compare_cifp_to_boogie(
    cifp_path: Path,
    boogie_jsonl: Path,
    *,
    max_examples: int = 3,
    quiet: bool = False,
) -> DiffResult:
    raw_bytes = gzip.decompress(cifp_path.read_bytes()) if cifp_path.suffix == ".gz" else cifp_path.read_bytes()
    raw_lines = raw_bytes.decode("latin1").splitlines()

    with tempfile.NamedTemporaryFile(suffix=".cifp") as tf:
        tf.write(raw_bytes)
        tf.flush()

        c = CIFP(tf.name)
        if quiet:
            with open("/dev/null", "w", encoding="utf-8") as devnull:
                old_stdout = sys.stdout
                sys.stdout = devnull
                try:
                    c.parse()
                finally:
                    sys.stdout = old_stdout
        else:
            c.parse()

        cp_by_key: dict[tuple, dict] = {}
        collisions: dict[str, int] = defaultdict(int)

        def index_group(spec_name: str, recs: list) -> None:
            for r in recs:
                if not r.has_primary():
                    continue
                d = r.primary.to_dict()
                k = _make_cp_key(spec_name, d)
                if k in cp_by_key:
                    collisions[spec_name] += 1
                cp_by_key[k] = d

        index_group("AirportSpec", c.get_airports())
        index_group("HeliportSpec", c.get_heliports())
        index_group("RunwaySpec", c.get_runways())
        index_group("LocalizerGlideSlopeSpec", c.get_loc_gss())
        index_group("GnssLandingSystemSpec", c.get_glss())
        index_group("VhfNavaidSpec", c.get_vhf_navaids())
        index_group("NdbNavaidSpec", c.get_ndb_navaids())

        wp_recs = (
            c.get_enroute_waypoints()
            + c.get_terminal_waypoints()
            + c.get_heli_terminal_waypoints()
        )
        for r in wp_recs:
            if not r.has_primary():
                continue
            d = r.primary.to_dict()
            if "environment_region" not in d and "heliport_region" in d:
                d["environment_region"] = d["heliport_region"]
            k = _make_cp_key("WaypointSpec", d)
            if k in cp_by_key:
                collisions["WaypointSpec"] += 1
            cp_by_key[k] = d

        index_group("AirwayLegSpec", c.get_airway_points())
        index_group("ProcedureLegSpec", c.get_procedures() + c.get_heli_procedures())
        index_group("HoldingPatternSpec", c.get_holds())
        index_group("ControlledAirspaceLegSpec", c.get_controlled())
        index_group("RestrictiveAirspaceLegSpec", c.get_restrictive())
        index_group("FirUirLegSpec", c.get_fir_uir())

    missing_in_cp: dict[tuple, int] = defaultdict(int)
    diff_counts: dict[tuple[str, str], int] = defaultdict(int)
    diff_examples: dict[tuple[str, str], list[tuple[object, object, str]]] = defaultdict(list)
    checked: dict[str, int] = defaultdict(int)

    def record_diff(spec: str, cp_key: str, c_val: object, b_val: object, raw: str) -> None:
        bucket = (spec, cp_key)
        diff_counts[bucket] += 1
        if len(diff_examples[bucket]) < max_examples:
            diff_examples[bucket].append((c_val, b_val, raw))

    with boogie_jsonl.open(encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            spec = obj["spec"]
            # Header01 is exposed via validity; PA 'E' primary extensions are not parsed by cifparse.
            if spec in ("Header01Spec", "AirportPrimaryExtensionSpec"):
                continue
            bf = obj["fields"]
            k = _make_boogie_key(spec, bf)
            cp = cp_by_key.get(k)
            if cp is None:
                sub = (
                    bf.get("subSectionCode")
                    or bf.get("terminalSubSectionCode")
                    or bf.get("enrouteSubSectionCode")
                )
                missing_in_cp[(spec, bf.get("sectionCode"), sub)] += 1
                continue

            checked[spec] += 1
            raw = raw_lines[obj["line_no"] - 1]
            for cp_key, b_fn, kind in MAPPINGS[spec]:
                b_val = b_fn(bf)
                c_val = cp.get(cp_key)

                if kind == "str":
                    if _norm_str(c_val) != _norm_str(b_val):
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind == "num":
                    if not _values_match(c_val, b_val):
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind in ("tenths_int", "freq_vhf"):
                    if (
                        c_val is not None
                        and b_val is not None
                        and abs(float(c_val) * 10.0 - float(b_val)) <= 1e-6
                    ):
                        continue
                    if not (c_val is None and b_val is None):
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind == "bool":
                    if c_val != b_val:
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind == "bool_blank_false":
                    c_norm = (
                        False
                        if c_val is None
                        else (c_val if isinstance(c_val, bool) else (c_val == "Y"))
                    )
                    if c_norm != b_val:
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind == "tdv_blank_false":
                    c_norm = c_val == "Y"
                    if c_norm != b_val:
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind == "desc_blank_at":
                    c_norm = "@" if c_val is None else _norm_str(c_val)
                    if c_norm != _norm_str(b_val):
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind == "area_enum":
                    c_norm = AREA_MAP.get(c_val, c_val)
                    if _norm_str(c_norm) != _norm_str(b_val):
                        record_diff(spec, cp_key, c_val, b_val, raw)
                elif kind == "cont_no":
                    b_norm = (
                        int(b_val)
                        if (b_val and str(b_val).isdigit())
                        else (10 + ord(str(b_val)) - ord("A") if b_val else None)
                    )
                    if c_val != b_norm:
                        record_diff(spec, cp_key, c_val, b_norm, raw)
                elif kind.startswith("alt_pair:"):
                    fl_key = kind.split(":", 1)[1]
                    c_norm = _norm_alt(cp.get(fl_key), c_val)
                    if not _values_match(c_norm, b_val):
                        record_diff(spec, cp_key, (cp.get(fl_key), c_val), b_val, raw)
                elif kind.startswith("brg:"):
                    _, t_key, s_idx, e_idx = kind.split(":")
                    is_t = cp.get(t_key)
                    raw_brg = raw[int(s_idx) : int(e_idx)]
                    if is_t is True and b_val is None and raw_brg.endswith("T"):
                        continue
                    if not _values_match(c_val, b_val):
                        record_diff(spec, cp_key, (is_t, c_val), b_val, raw)
                elif kind.startswith("dist_time:"):
                    t_key = kind.split(":", 1)[1]
                    is_time = cp.get(t_key)
                    if isinstance(b_val, str):
                        if is_time and b_val.startswith("T") and b_val[1:].isdigit():
                            if abs(int(b_val[1:]) * 0.1 - float(c_val)) <= 1e-6:
                                continue
                        elif not is_time and b_val.isdigit():
                            if abs(int(b_val) * 0.1 - float(c_val)) <= 1e-6:
                                continue
                    if not _values_match(c_val, b_val):
                        record_diff(spec, cp_key, (is_time, c_val), b_val, raw)

    return DiffResult(
        indexed=len(cp_by_key),
        collisions=dict(collisions),
        missing_in_cifparse=dict(missing_in_cp),
        checked=dict(checked),
        diff_counts=dict(diff_counts),
        diff_examples=dict(diff_examples),
    )


def print_diff_result(res: DiffResult) -> None:
    print(f"Indexed {res.indexed} cifparse records (key collisions={res.collisions}).")
    print("Missing in cifparse:", res.missing_in_cifparse)
    print("Checked counts:", res.checked)
    print(f"Field differences ({len(res.diff_counts)} field buckets):")
    for (spec, cp_key), count in sorted(res.diff_counts.items()):
        print(f"\n  [{spec}.{cp_key}] count={count}")
        for c_v, b_v, raw in res.diff_examples[(spec, cp_key)]:
            print(f"    cifparse={c_v!r} vs boogie={b_v!r}")
            print(f"    raw={raw!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cifp", type=Path, required=True)
    parser.add_argument("--boogie", type=Path, required=True)
    parser.add_argument("--fail-on-diff", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    res = compare_cifp_to_boogie(args.cifp, args.boogie, quiet=args.quiet)
    print_diff_result(res)
    if args.fail_on_diff and not res.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
