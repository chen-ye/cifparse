"""Reproducible runner for the mitre-public/boogie differential oracle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ORACLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = ORACLE_DIR.parents[1]
SRC_DIR = REPO_ROOT / "src"

for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cifparse import CIFP  # noqa: E402
from tests.oracle.diff_oracle import DiffResult, compare_cifp_to_boogie, print_diff_result  # noqa: E402

DEPS_MANIFEST = ORACLE_DIR / "deps.json"
BOOGIE_JAVA = ORACLE_DIR / "BoogieDump.java"
DEFAULT_CACHE_DIR = Path(os.environ.get("CIFPARSE_ORACLE_CACHE") or (REPO_ROOT / ".cache" / "boogie-oracle"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_jars(cache_dir: Path) -> list[Path]:
    lib_dir = cache_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    deps = json.loads(DEPS_MANIFEST.read_text(encoding="utf-8"))
    jar_paths: list[Path] = []

    for dep in deps:
        dest = lib_dir / dep["filename"]
        expected_sha = dep["sha256"]
        if dest.exists() and _sha256_file(dest) == expected_sha:
            jar_paths.append(dest)
            continue

        tmp_dest = lib_dir / f".{dep['filename']}.tmp"
        print(f"Downloading {dep['url']} -> {dest}")
        with urllib.request.urlopen(dep["url"], timeout=60) as resp, tmp_dest.open("wb") as out:
            shutil.copyfileobj(resp, out)

        actual_sha = _sha256_file(tmp_dest)
        if actual_sha != expected_sha:
            tmp_dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"SHA-256 mismatch for {dep['filename']}: expected {expected_sha}, got {actual_sha}"
            )
        tmp_dest.replace(dest)
        jar_paths.append(dest)

    return jar_paths


def ensure_compiled(cache_dir: Path, jar_paths: list[Path]) -> Path:
    classes_dir = cache_dir / "classes"
    classes_dir.mkdir(parents=True, exist_ok=True)
    stamp_file = classes_dir / "BoogieDump.sha256"
    class_file = classes_dir / "BoogieDump.class"
    src_sha = _sha256_file(BOOGIE_JAVA)

    if class_file.exists() and stamp_file.exists() and stamp_file.read_text(encoding="utf-8").strip() == src_sha:
        return classes_dir

    javac = shutil.which("javac")
    if not javac:
        raise RuntimeError("javac is required on PATH to compile BoogieDump.java")

    cp = os.pathsep.join(str(p) for p in jar_paths)
    subprocess.run(
        [javac, "-cp", cp, "-d", str(classes_dir), str(BOOGIE_JAVA)],
        check=True,
    )
    stamp_file.write_text(src_sha + "\n", encoding="utf-8")
    return classes_dir


def dump_boogie(
    cifp_path: Path,
    *,
    version: str = "V19",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
) -> Path:
    jar_paths = ensure_jars(cache_dir)
    classes_dir = ensure_compiled(cache_dir, jar_paths)
    out_dir = cache_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    input_sha = _sha256_file(cifp_path)[:16]
    java_sha = _sha256_file(BOOGIE_JAVA)[:8]
    out_jsonl = out_dir / f"boogie_{input_sha}_{version}_{java_sha}.jsonl"
    if use_cache and out_jsonl.exists():
        return out_jsonl

    java = shutil.which("java")
    if not java:
        raise RuntimeError("java is required on PATH to run BoogieDump")

    tmp_jsonl = out_dir / f".{out_jsonl.name}.tmp"
    cp = os.pathsep.join([str(classes_dir), *(str(p) for p in jar_paths)])
    subprocess.run(
        [java, "-cp", cp, "BoogieDump", str(cifp_path), str(tmp_jsonl), version],
        check=True,
    )
    tmp_jsonl.replace(out_jsonl)
    return out_jsonl


def _check_sqlite_export(cifp_path: Path, quiet: bool = False) -> None:
    raw_bytes = gzip.decompress(cifp_path.read_bytes()) if cifp_path.suffix == ".gz" else cifp_path.read_bytes()
    with tempfile.NamedTemporaryFile(suffix=".cifp") as tf, tempfile.NamedTemporaryFile(suffix=".db") as df:
        tf.write(raw_bytes)
        tf.flush()
        c = CIFP(tf.name)
        if quiet:
            with open(os.devnull, "w", encoding="utf-8") as devnull:
                old_stdout = sys.stdout
                sys.stdout = devnull
                try:
                    c.parse()
                    c.to_db(df.name)
                finally:
                    sys.stdout = old_stdout
        else:
            c.parse()
            c.to_db(df.name)


def run_cifp(
    cifp_path: Path,
    *,
    version: str = "V19",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    check_to_db: bool = False,
    quiet: bool = False,
) -> DiffResult:
    boogie_jsonl = dump_boogie(cifp_path, version=version, cache_dir=cache_dir, use_cache=use_cache)
    res = compare_cifp_to_boogie(cifp_path, boogie_jsonl, quiet=quiet)
    if check_to_db:
        _check_sqlite_export(cifp_path, quiet=quiet)
    return res


def build_smoke_cifp(dest: Path) -> Path:
    from tests.test_active_cifp_records import ACTIVE_FAMILY_LINES, HEADER_LINES

    gls_line = (
        "SSPAP YSSYYMTG07A1   022790RW07                    0620S33575258E151110525YSSY         300E0130  00021WGE     00034        464892003"
    )
    fir_line = (
        "SUSAUFKZAKZOZXF00010        21N H N49404188W180000000                           UNLTD          RR OAKLAND OCEANIC FIR      221902003"
    )
    ep_line = (
        "SEUREPENRT                 01AG   URDB00900R   10FL098FL200230                                                             000012210"
    )
    lines = [*HEADER_LINES, *ACTIVE_FAMILY_LINES, gls_line, fir_line, ep_line]
    for line in lines:
        if len(line) != 132:
            raise ValueError(f"Expected 132-byte line, got {len(line)}: {line!r}")
    dest.write_text("\n".join(lines) + "\n", encoding="latin1")
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cifp", type=Path, nargs="+", help="Path(s) to .cifp/.txt/.gz files to diff")
    parser.add_argument("--smoke", action="store_true", help="Run differential check on built-in 132-byte active fixtures")
    parser.add_argument("--fetch-only", action="store_true", help="Download/verify Boogie JARs and compile BoogieDump.java only")
    parser.add_argument("--version", default="V19", choices=["V18", "V19", "V20", "V21", "V22"])
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--no-cache", action="store_true", help="Re-run BoogieDump even if cached JSONL exists")
    parser.add_argument("--check-to-db", action="store_true", help="Also verify CIFP.to_db() SQLite export")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.fetch_only:
        jars = ensure_jars(args.cache_dir)
        classes = ensure_compiled(args.cache_dir, jars)
        print(f"Verified {len(jars)} JARs and compiled BoogieDump in {classes}")
        return 0

    targets: list[tuple[str, Path]] = []
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.smoke:
            temp_dir = tempfile.TemporaryDirectory()
            smoke_path = build_smoke_cifp(Path(temp_dir.name) / "SMOKE_CIFP")
            targets.append(("smoke-fixtures", smoke_path))
        if args.cifp:
            for p in args.cifp:
                targets.append((p.name, p))
        if not targets:
            parser.error("Provide --smoke, --cifp PATH ..., or --fetch-only")

        exit_code = 0
        for label, path in targets:
            print(f"=== {label} ({args.version}) ===")
            res = run_cifp(
                path,
                version=args.version,
                cache_dir=args.cache_dir,
                use_cache=not args.no_cache,
                check_to_db=args.check_to_db,
                quiet=args.quiet,
            )
            print_diff_result(res)
            if not res.ok:
                exit_code = 1
        return exit_code
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
