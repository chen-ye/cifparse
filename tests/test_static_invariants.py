"""Static structural invariants across record widths, decoders, and serializers."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
import unittest

from cifparse.functions import record as rec_funcs

RECORDS_ROOT = Path(__file__).resolve().parents[1] / "src" / "cifparse" / "records"

TUPLE_DECODERS = {
    name
    for name, fn in inspect.getmembers(rec_funcs, inspect.isfunction)
    if "tuple" in str(inspect.signature(fn).return_annotation)
}

ALLOWED_ATTR_RENAMES = {
    ("heli_procedure/primary.py", "vert_angle"): "vertical_angle",
    ("heli_procedure/primary.py", "mult_code"): "multiple_code",
}

WIDTH_CLASS_TO_VAR = {
    "BaseIndices": "w_bas",
    "PrimaryIndices": "w_pri",
    "ContinuationIndices": "w_con",
    "PlanningIndices": "w_pla",
    "PlanningContinuationIndices": "w_plc",
    "PlanningContinuation": "w_plc",
    "SimulationIndices": "w_sim",
    "TimeIndices": "w_tim",
    "CombinedIndices": "w_com",
    "LimitationIndices": "w_lim",
    "AltExcPrimaryIndices": "w_aex",
    "AltExcContinuationIndices": "w_aec",
    "CruisePrimaryIndices": "w_cru",
    "CruiseContinuationIndices": "w_crc",
    "ClosurePrimaryIndices": "w_clo",
    "NotePrimaryIndices": "w_not",
    "NoteContinuationIndices": "w_noc",
    "Header01Indices": "w_h1",
    "Header02Indices": "w_h2",
}


class TestStaticInvariants(unittest.TestCase):
    def test_widths_have_valid_non_overlapping_slices(self) -> None:
        for wpy in sorted(RECORDS_ROOT.rglob("widths.py")):
            rel = wpy.relative_to(RECORDS_ROOT)
            tree = ast.parse(wpy.read_text(encoding="utf-8"))
            for cls in tree.body:
                if not isinstance(cls, ast.ClassDef):
                    continue
                ranges: list[tuple[int, int, str]] = []
                for stmt in ast.walk(cls):
                    if (
                        isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Attribute)
                        and isinstance(stmt.value, ast.Tuple)
                        and len(stmt.value.elts) == 3
                    ):
                        s = ast.literal_eval(stmt.value.elts[0])
                        e = ast.literal_eval(stmt.value.elts[1])
                        attr = stmt.targets[0].attr
                        self.assertGreaterEqual(s, 0, f"{rel} {cls.name}.{attr}")
                        self.assertLessEqual(e, 132, f"{rel} {cls.name}.{attr}")
                        self.assertLess(s, e, f"{rel} {cls.name}.{attr}")
                        ranges.append((s, e, attr))

                ranges.sort()
                for i in range(len(ranges) - 1):
                    s1, e1, a1 = ranges[i]
                    s2, e2, a2 = ranges[i + 1]
                    self.assertLessEqual(
                        e1,
                        s2,
                        f"Overlapping slices in {rel} {cls.name}: {a1}({s1},{e1}) vs {a2}({s2},{e2})",
                    )

    def test_record_classes_reference_valid_widths_and_unpack_tuples(self) -> None:
        for py in sorted(RECORDS_ROOT.rglob("*.py")):
            rel = py.relative_to(RECORDS_ROOT)
            if py.name in ("__init__.py", "widths.py", "table_base.py", "record_base.py"):
                continue

            mod_name = "cifparse.records." + ".".join(rel.parts).removesuffix(".py")
            mod = importlib.import_module(mod_name)
            tree = ast.parse(py.read_text(encoding="utf-8"))

            w_cls_decoders: dict[str, dict[str, str]] = {}
            wpy = py.parent / "widths.py"
            if len(rel.parts) > 1 and wpy.exists():
                wtree = ast.parse(wpy.read_text(encoding="utf-8"))
                for cls in wtree.body:
                    if isinstance(cls, ast.ClassDef):
                        decs: dict[str, str] = {}
                        for stmt in ast.walk(cls):
                            if (
                                isinstance(stmt, ast.Assign)
                                and len(stmt.targets) == 1
                                and isinstance(stmt.targets[0], ast.Attribute)
                                and isinstance(stmt.value, ast.Tuple)
                                and len(stmt.value.elts) == 3
                                and isinstance(stmt.value.elts[2], ast.Name)
                            ):
                                decs[stmt.targets[0].attr] = stmt.value.elts[2].id
                        w_cls_decoders[cls.name] = decs

            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    vname = node.value.id
                    if vname.startswith("w_") and hasattr(mod, vname):
                        w_obj = getattr(mod, vname)
                        self.assertTrue(
                            hasattr(w_obj, node.attr),
                            f"{rel}:{node.lineno}: missing attribute {vname}.{node.attr}",
                        )

                if (
                    isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "extract_field"
                    and len(node.value.args) >= 2
                ):
                    arg2 = node.value.args[1]
                    if not (isinstance(arg2, ast.Attribute) and isinstance(arg2.value, ast.Name)):
                        continue
                    wvar, wattr = arg2.value.id, arg2.attr
                    targets = []
                    for tg in node.targets:
                        if isinstance(tg, ast.Attribute):
                            targets.append(tg.attr)
                        elif isinstance(tg, ast.Tuple):
                            targets.extend(
                                elt.attr for elt in tg.elts if isinstance(elt, ast.Attribute)
                            )
                    if targets:
                        allowed = ALLOWED_ATTR_RENAMES.get((str(rel), targets[0]))
                        self.assertTrue(
                            wattr in targets or allowed == wattr,
                            f"{rel}:{node.lineno}: targets={targets} vs {wvar}.{wattr}",
                        )

                    for cls_name, dec_map in w_cls_decoders.items():
                        if WIDTH_CLASS_TO_VAR.get(cls_name) == wvar and wattr in dec_map:
                            dec = dec_map[wattr]
                            is_tuple_target = isinstance(node.targets[0], ast.Tuple)
                            self.assertEqual(
                                dec in TUPLE_DECODERS,
                                is_tuple_target,
                                f"{rel}:{node.lineno}: {wvar}.{wattr} ({dec}) tuple unpacking mismatch",
                            )

    def test_ordered_fields_match_to_dict_and_widths_are_extracted(self) -> None:
        for rec_dir in sorted(p for p in RECORDS_ROOT.iterdir() if p.is_dir()):
            w_file = rec_dir / "widths.py"
            if not w_file.exists():
                continue

            w_tree = ast.parse(w_file.read_text(encoding="utf-8"))
            w_attrs: dict[str, set[str]] = {}
            for cls in w_tree.body:
                if isinstance(cls, ast.ClassDef):
                    own: set[str] = set()
                    for m in cls.body:
                        if isinstance(m, ast.FunctionDef) and m.name == "__init__":
                            for stmt in ast.walk(m):
                                if (
                                    isinstance(stmt, ast.Assign)
                                    and len(stmt.targets) == 1
                                    and isinstance(stmt.targets[0], ast.Attribute)
                                    and isinstance(stmt.value, ast.Tuple)
                                    and len(stmt.value.elts) == 3
                                ):
                                    own.add(stmt.targets[0].attr)
                    w_attrs[cls.name] = own

            used: set[tuple[str, str]] = set()
            for py in list(rec_dir.glob("*.py")) + list(RECORDS_ROOT.glob("*.py")):
                if py.name == "widths.py":
                    continue
                t = ast.parse(py.read_text(encoding="utf-8"))
                for node in ast.walk(t):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "extract_field"
                        and len(node.args) >= 2
                    ):
                        arg2 = node.args[1]
                        if isinstance(arg2, ast.Attribute) and isinstance(arg2.value, ast.Name):
                            used.add((arg2.value.id, arg2.attr))

                if py.parent != rec_dir or py.name in ("__init__.py",):
                    continue
                for cls in t.body:
                    if not isinstance(cls, ast.ClassDef):
                        continue
                    ord_fields: list[str] = []
                    dict_keys: list[str] = []
                    for m in cls.body:
                        if isinstance(m, ast.FunctionDef) and m.name in (
                            "ordered_fields",
                            "ordered_leading",
                            "ordered_trailing",
                        ):
                            for node in ast.walk(m):
                                if isinstance(node, ast.List):
                                    ord_fields.extend(
                                        e.value
                                        for e in node.elts
                                        if isinstance(e, ast.Constant)
                                        and isinstance(e.value, str)
                                    )
                        elif isinstance(m, ast.FunctionDef) and m.name in (
                            "to_dict",
                            "get_leading_dict",
                            "get_trailing_dict",
                        ):
                            for node in ast.walk(m):
                                if isinstance(node, ast.Dict):
                                    dict_keys.extend(
                                        k.value
                                        for k in node.keys
                                        if isinstance(k, ast.Constant)
                                        and isinstance(k.value, str)
                                    )
                    if ord_fields or dict_keys:
                        self.assertEqual(
                            ord_fields,
                            dict_keys,
                            f"{py.relative_to(RECORDS_ROOT)} {cls.name} ordered_fields != to_dict",
                        )

            for cls_name, attrs in w_attrs.items():
                wvar = WIDTH_CLASS_TO_VAR[cls_name]
                missing = {a for a in attrs if (wvar, a) not in used}
                self.assertEqual(
                    missing,
                    set(),
                    f"Unused fields in {rec_dir.name}/widths.py {cls_name} ({wvar})",
                )


if __name__ == "__main__":
    unittest.main()
