# Boogie Differential Oracle

This directory cross-checks `cifparse` against MITRE's `boogie-arinc` ARINC 424 parser (`org.mitre.boogie:boogie-arinc:8.0.0`).

## Prerequisites

- Python 3.10 or newer
- JDK 17 or newer with `javac` and `java` on `PATH`
- Network access on first run to fetch the 11 Maven Central JARs listed in [deps.json](./deps.json)

## Usage

Run the built-in smoke check against the repository's 132-byte test fixtures and verify SQLite export:

```bash
PYTHONPATH=src python3 -m tests.oracle.run --smoke --check-to-db
```

Run against an external CIFP archive such as `FAACIFP18.gz` or `cifp-2101.dat.gz`:

```bash
PYTHONPATH=src python3 -m tests.oracle.run --cifp /path/to/FAACIFP18.gz --check-to-db
```

Run the live differential check through `unittest`:

```bash
CIFPARSE_RUN_ORACLE=1 PYTHONPATH=src python3 -m unittest tests/test_oracle_smoke.py -v
CIFPARSE_RUN_ORACLE=1 CIFPARSE_ORACLE_CIFP=/path/to/FAACIFP18.gz PYTHONPATH=src python3 -m unittest tests/test_oracle_smoke.py -v
```

## Cache Layout

Downloaded JARs, compiled class files, and cached Boogie JSONL dumps live under `.cache/boogie-oracle/` by default, or under `CIFPARSE_ORACLE_CACHE` / `--cache-dir`:

- `lib/`: Maven Central JARs verified against SHA-256 checksums in [deps.json](./deps.json)
- `classes/`: compiled `BoogieDump.class` plus source hash stamp
- `out/`: cached `boogie_<hash>_<version>_<java_hash>.jsonl` dumps

Pass `--no-cache` to force re-running `BoogieDump`. Pass `--fetch-only` to populate `lib/` and `classes/` without parsing a CIFP file.

## Scope & Known Version Differences

- `BoogieDump.java` defaults to `ArincVersion.V19`. Passing `--version V22` switches Boogie specs to Supplement 22.
- `cifparse` targets ARINC 424 Supplement 18/19 layouts. Supplement 20/22 fixtures move `RunwaySpec.tch` to columns 95 through 98 and add Supplement 22 procedure qualifiers such as `'G'`.
- `diff_oracle.py` skips `Header01Spec` and `AirportPrimaryExtensionSpec` because `cifparse` exposes `HDR01` through `validity` and does not parse `PA` `E` extensions.
- Boogie `V19` does not emit records for `HDR02` through `HDR05`, `AS` Grid MORA, `PS`/`HS` MSA, `PP` Path Points, `PF`/`HF` `W` continuations, or `UR` `C` continuations. Those paths are covered by `tests/test_active_cifp_records.py`, `tests/test_path_points.py`, and `tests/test_static_invariants.py`.
