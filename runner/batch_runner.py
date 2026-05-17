#!/usr/bin/env python3
"""batch_runner.py — Drive SAGE merger tree conversions from a TOML config file.

Usage (single job):
    $PYTHON_BIN runner/batch_runner.py runner/conversion_config.toml --job my_dataset

Usage (all jobs):
    $PYTHON_BIN runner/batch_runner.py runner/conversion_config.toml

Usage (parallel):
    $PYTHON_BIN runner/batch_runner.py runner/conversion_config.toml --workers 4

After `pip install -e .` the installed entry point is also available:
    sage-convert runner/conversion_config.toml
"""

from __future__ import annotations

import argparse
import logging
import sys
import tomllib
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Make conversion-engine importable regardless of working directory.
# ---------------------------------------------------------------------------
_ENGINE_DIR = str(Path(__file__).parent.parent / "conversion-engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

from main_driver import FORMAT_REGISTRY, _setup_logging, convert_one  # noqa: E402

_DEFAULT_OUTPUT_FORMAT = "lhalo_hdf5"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ConversionJob:
    name: str
    format_id: str
    input: Path
    output: Path
    output_format: str = _DEFAULT_OUTPUT_FORMAT
    n_trees: int | None = None
    sim_params: dict = field(default_factory=dict)


@dataclass
class JobResult:
    name: str
    status: str  # "success" | "failed"
    output: Path | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(config_path: Path) -> list[ConversionJob]:
    """Parse a TOML config file and return one ConversionJob per [job.<name>] section."""
    with open(config_path, "rb") as fh:
        raw = tomllib.load(fh)

    global_fmt = raw.get("global", {}).get("output_format", _DEFAULT_OUTPUT_FORMAT)

    jobs: list[ConversionJob] = []
    for name, spec in raw.get("job", {}).items():
        missing = [k for k in ("format_id", "input", "output") if k not in spec]
        if missing:
            raise ValueError(f"Job {name!r} is missing required keys: {missing}")
        jobs.append(
            ConversionJob(
                name=name,
                format_id=spec["format_id"],
                input=Path(spec["input"]),
                output=Path(spec["output"]),
                output_format=spec.get("output_format", global_fmt),
                n_trees=spec.get("n_trees"),
                sim_params=spec.get("sim_params", {}),
            )
        )

    if not jobs:
        raise ValueError("No [job.*] sections found in the config file.")

    return jobs


# ---------------------------------------------------------------------------
# Job execution (top-level so ProcessPoolExecutor can pickle it)
# ---------------------------------------------------------------------------


def run_job(job: ConversionJob) -> JobResult:
    """Execute one conversion job. Returns a JobResult; never raises."""
    # Each worker process needs sys.path set up independently.
    if _ENGINE_DIR not in sys.path:
        sys.path.insert(0, _ENGINE_DIR)

    _setup_logging()
    try:
        convert_one(
            input_path=str(job.input),
            output_path=str(job.output),
            format_id=job.format_id,
            n_trees=job.n_trees,
            sim_params=job.sim_params or None,
            output_format=job.output_format,
        )
        return JobResult(name=job.name, status="success", output=job.output)
    except RuntimeError as exc:
        return JobResult(name=job.name, status="failed", error=str(exc))
    except Exception as exc:
        return JobResult(name=job.name, status="failed", error=f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Batch orchestration
# ---------------------------------------------------------------------------


def batch_run(jobs: list[ConversionJob], workers: int = 1) -> list[JobResult]:
    """Run all jobs, sequentially or in parallel. Returns results in completion order."""
    log = logging.getLogger(__name__)
    results: list[JobResult] = []

    if workers <= 1:
        for job in jobs:
            log.info("[%s] Starting: %s → %s", job.name, job.input, job.output)
            result = run_job(job)
            results.append(result)
            if result.status == "success":
                log.info("[%s] Done.", job.name)
            else:
                log.error("[%s] Failed: %s", job.name, result.error)
    else:
        log.info("Running %d jobs with %d workers.", len(jobs), workers)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            future_to_job = {pool.submit(run_job, job): job for job in jobs}
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = JobResult(name=job.name, status="failed", error=str(exc))
                results.append(result)
                if result.status == "success":
                    log.info("[%s] Done.", result.name)
                else:
                    log.error("[%s] Failed: %s", result.name, result.error)

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    _setup_logging()

    parser = argparse.ArgumentParser(
        prog="sage-convert",
        description="Run SAGE merger tree conversions declared in a TOML config file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  %(prog)s runner/conversion_config.toml\n"
            "  %(prog)s runner/conversion_config.toml --job my_dataset\n"
            "  %(prog)s runner/conversion_config.toml --workers 4\n"
        ),
    )
    parser.add_argument("config", type=Path, help="Path to the TOML config file.")
    parser.add_argument(
        "--job",
        metavar="NAME",
        default=None,
        help="Run only this named job (skips all others).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of parallel worker processes (default: 1 = sequential).",
    )
    args = parser.parse_args()

    log = logging.getLogger(__name__)

    try:
        jobs = load_config(args.config)
    except (OSError, ValueError) as exc:
        log.error("Failed to load config %s: %s", args.config, exc)
        return 1

    if args.job is not None:
        jobs = [j for j in jobs if j.name == args.job]
        if not jobs:
            log.error("No job named %r found in %s.", args.job, args.config)
            return 1

    # Validate format IDs before launching any work.
    unknown = [j for j in jobs if j.format_id not in FORMAT_REGISTRY]
    if unknown:
        for j in unknown:
            log.error(
                "[%s] Unknown format_id %r. Registered formats: %s",
                j.name,
                j.format_id,
                sorted(FORMAT_REGISTRY.keys()),
            )
        return 1

    log.info("Running %d job(s) from %s.", len(jobs), args.config)
    results = batch_run(jobs, workers=args.workers)

    passed = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    log.info("Summary: %d/%d jobs succeeded.", passed, len(results))

    if failed:
        for r in results:
            if r.status == "failed":
                log.error("  FAIL  %s — %s", r.name, r.error)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
