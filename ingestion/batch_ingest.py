"""
FreshFlow AI — Batch Ingestion
================================
Copies validated source data into the bronze layer with full metadata.

Bronze layer principles:
- Immutable source history
- Reproducible ingestion
- Auditability (every record traced to source)
- Idempotent (re-running same batch does not duplicate rows)

Bronze storage layout:
    bronze/freshretail/source_split=train/ingestion_date=YYYY-MM-DD/*.parquet
    bronze/freshretail/source_split=eval/ingestion_date=YYYY-MM-DD/*.parquet
    bronze/simulation/economics_version=v1/*.parquet

Added metadata columns:
    source_file         - Original filename
    source_file_hash    - SHA-256 of source file
    source_split        - train/eval
    ingestion_batch_id  - Unique batch identifier
    ingested_at         - UTC timestamp
    schema_version      - Data contract version
    record_hash         - Row-level hash for deduplication

Usage:
    python ingestion/batch_ingest.py
    python ingestion/batch_ingest.py --sample  # Use sample dataset
    python ingestion/batch_ingest.py --dry-run # Preview without writing
"""

import argparse
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
SAMPLE_DIR = DATA_DIR / "sample"
BRONZE_DIR = DATA_DIR / "bronze"


def generate_batch_id() -> str:
    """Generate a unique batch identifier."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"batch_{ts}_{short_uuid}"


def compute_row_hash(row_dict: dict) -> str:
    """Compute a deterministic hash for a row (for deduplication)."""
    # Use only the natural key columns for the hash
    key_cols = ["store_id", "product_id", "dt"]
    key_values = "|".join(str(row_dict.get(c, "")) for c in key_cols)
    return hashlib.md5(key_values.encode()).hexdigest()


def ingest_to_bronze(
    source_dir: Path,
    bronze_dir: Path,
    batch_id: str,
    dry_run: bool = False,
) -> dict:
    """
    Ingest source parquet files into the bronze layer.

    Adds metadata columns and partitions by source_split and ingestion_date.
    Idempotent: checks for existing batch_id to prevent duplicates.
    """
    import pandas as pd

    ingestion_stats = {
        "batch_id": batch_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_dir),
        "files_processed": 0,
        "total_source_rows": 0,
        "total_bronze_rows": 0,
        "errors": [],
    }

    # Find parquet files
    parquet_files = list(source_dir.rglob("*.parquet"))
    if not parquet_files:
        logger.error("no_parquet_files", source_dir=str(source_dir))
        ingestion_stats["errors"].append("No parquet files found")
        return ingestion_stats

    logger.info("found_source_files", count=len(parquet_files))

    ingestion_timestamp = datetime.now(timezone.utc).isoformat()
    ingestion_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for pf in parquet_files:
        try:
            logger.info("processing_file", file=pf.name)
            df = pd.read_parquet(pf)
            ingestion_stats["total_source_rows"] += len(df)

            # Determine source split from filename or path
            path_str = str(pf).lower()
            if "train" in path_str:
                source_split = "train"
            elif "eval" in path_str or "test" in path_str:
                source_split = "eval"
            else:
                source_split = "unknown"

            # Compute source file hash
            file_hash = hashlib.sha256(pf.read_bytes()).hexdigest()

            # Add metadata columns
            df["source_file"] = pf.name
            df["source_file_hash"] = file_hash
            df["source_split"] = source_split
            df["ingestion_batch_id"] = batch_id
            df["ingested_at"] = ingestion_timestamp
            df["schema_version"] = "1.0"

            # Compute row-level hashes for deduplication
            df["record_hash"] = df.apply(
                lambda row: compute_row_hash(row.to_dict()), axis=1
            )

            if dry_run:
                logger.info(
                    "dry_run_skip_write",
                    file=pf.name,
                    rows=len(df),
                    split=source_split,
                )
                continue

            # Write to bronze with partitioning
            output_dir = (
                bronze_dir
                / "freshretail"
                / f"source_split={source_split}"
                / f"ingestion_date={ingestion_date}"
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / f"{batch_id}_{pf.stem}.parquet"

            # Idempotent check: skip if this batch already exists
            if output_file.exists():
                logger.warning(
                    "batch_already_exists",
                    file=str(output_file),
                    message="Skipping to maintain idempotency",
                )
                continue

            df.to_parquet(output_file, index=False, engine="pyarrow")
            ingestion_stats["total_bronze_rows"] += len(df)
            ingestion_stats["files_processed"] += 1

            logger.info(
                "file_ingested",
                file=pf.name,
                rows=len(df),
                split=source_split,
                output=str(output_file),
            )

        except Exception as e:
            logger.error("ingestion_error", file=pf.name, error=str(e))
            ingestion_stats["errors"].append({
                "file": pf.name,
                "error": str(e),
            })

    ingestion_stats["ended_at"] = datetime.now(timezone.utc).isoformat()
    ingestion_stats["success"] = len(ingestion_stats["errors"]) == 0

    # Save ingestion log
    if not dry_run:
        log_dir = bronze_dir / "_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        import json
        log_path = log_dir / f"{batch_id}_ingestion.json"
        with open(log_path, "w") as f:
            json.dump(ingestion_stats, f, indent=2, default=str)
        logger.info("ingestion_log_saved", path=str(log_path))

    return ingestion_stats


def run_bronze_quality_checks(bronze_dir: Path, batch_id: str) -> dict:
    """
    Run basic quality checks on the bronze layer after ingestion.

    Checks:
    - Files exist for the batch
    - Row counts are non-zero
    - Required columns present
    - No completely null required columns
    """
    import pandas as pd

    checks = {
        "batch_id": batch_id,
        "checks": [],
        "passed": True,
    }

    REQUIRED_COLUMNS = [
        "city_id", "store_id", "product_id", "dt",
        "sale_amount", "hours_sale", "hours_stock_status",
    ]

    # Find files for this batch
    batch_files = list(bronze_dir.rglob(f"{batch_id}_*.parquet"))
    checks["checks"].append({
        "name": "batch_files_exist",
        "passed": len(batch_files) > 0,
        "detail": f"Found {len(batch_files)} files",
    })

    if not batch_files:
        checks["passed"] = False
        return checks

    total_rows = 0
    for bf in batch_files:
        df = pd.read_parquet(bf)
        total_rows += len(df)

        # Check required columns
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        checks["checks"].append({
            "name": f"required_columns_{bf.name}",
            "passed": len(missing_cols) == 0,
            "detail": f"Missing: {missing_cols}" if missing_cols else "All present",
        })

        # Check for completely null columns
        null_cols = [
            c for c in REQUIRED_COLUMNS
            if c in df.columns and df[c].isnull().all()
        ]
        checks["checks"].append({
            "name": f"no_fully_null_keys_{bf.name}",
            "passed": len(null_cols) == 0,
            "detail": f"Fully null: {null_cols}" if null_cols else "OK",
        })

        if missing_cols or null_cols:
            checks["passed"] = False

    checks["checks"].append({
        "name": "total_rows_nonzero",
        "passed": total_rows > 0,
        "detail": f"Total rows: {total_rows:,}",
    })

    logger.info(
        "bronze_quality_checks",
        batch_id=batch_id,
        passed=checks["passed"],
        n_checks=len(checks["checks"]),
    )
    return checks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Ingest source data into bronze layer"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use sample dataset instead of full dataset",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview ingestion without writing files",
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        default=None,
        help="Custom source directory",
    )
    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    # Determine source directory
    if args.source_dir:
        source_dir = Path(args.source_dir)
    elif args.sample:
        source_dir = SAMPLE_DIR
    else:
        source_dir = RAW_DIR

    batch_id = generate_batch_id()
    logger.info("starting_ingestion", batch_id=batch_id, source=str(source_dir))

    # Run ingestion
    stats = ingest_to_bronze(
        source_dir=source_dir,
        bronze_dir=BRONZE_DIR,
        batch_id=batch_id,
        dry_run=args.dry_run,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Batch ID:         {stats['batch_id']}")
    print(f"Source rows:      {stats['total_source_rows']:,}")
    print(f"Bronze rows:      {stats['total_bronze_rows']:,}")
    print(f"Files processed:  {stats['files_processed']}")
    print(f"Errors:           {len(stats['errors'])}")
    print(f"Success:          {'✅' if stats.get('success') else '❌'}")
    print("=" * 60)

    if not args.dry_run and stats.get("success"):
        # Run quality checks
        logger.info("running_bronze_quality_checks")
        qc = run_bronze_quality_checks(BRONZE_DIR, batch_id)
        print(f"\nQuality checks:   {'✅ PASSED' if qc['passed'] else '❌ FAILED'}")
        for check in qc["checks"]:
            status = "✅" if check["passed"] else "❌"
            print(f"  {status} {check['name']}: {check['detail']}")


if __name__ == "__main__":
    main()
