"""
FreshFlow AI — Dataset Downloader
=================================
Downloads the FreshRetailNet-50K dataset from Hugging Face.

Dataset: https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K
License: CC BY 4.0
Citation: Wang et al., "FreshRetailNet-50K: A Stockout-Annotated Censored Demand
          Dataset for Latent Demand Recovery and Forecasting in Fresh Retail", 2025.

Usage:
    python ingestion/download_dataset.py
    python ingestion/download_dataset.py --sample 1000
"""

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATASET_NAME = "Dingdong-Inc/FreshRetailNet-50K"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
SAMPLE_DIR = DATA_DIR / "sample"
MANIFEST_PATH = DATA_DIR / "source_manifest.json"

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def compute_file_hash(filepath: Path, algorithm: str = "sha256") -> str:
    """Compute hash of a file for integrity verification."""
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_manifest(raw_dir: Path, manifest_path: Path) -> dict:
    """Create a source manifest recording all downloaded files with hashes."""
    files = []
    for fp in sorted(raw_dir.rglob("*")):
        if fp.is_file():
            files.append({
                "filename": fp.name,
                "relative_path": str(fp.relative_to(raw_dir)),
                "size_bytes": fp.stat().st_size,
                "sha256": compute_file_hash(fp),
            })

    manifest = {
        "dataset": DATASET_NAME,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "download_tool": "huggingface_hub",
        "total_files": len(files),
        "total_bytes": sum(f["size_bytes"] for f in files),
        "files": files,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(
        "source_manifest_created",
        total_files=len(files),
        total_bytes=manifest["total_bytes"],
        manifest_path=str(manifest_path),
    )
    return manifest


def download_dataset(force: bool = False) -> Path:
    """
    Download FreshRetailNet-50K from Hugging Face Hub.

    Uses huggingface_hub library for reliable download with resume support.
    The dataset is downloaded as-is (Parquet files) into data/raw/.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        logger.error(
            "huggingface_hub not installed. Run: pip install huggingface_hub"
        )
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Check if already downloaded (idempotent)
    if not force and MANIFEST_PATH.exists():
        logger.info(
            "dataset_already_downloaded",
            manifest_path=str(MANIFEST_PATH),
            message="Use --force to re-download",
        )
        return RAW_DIR

    logger.info(
        "downloading_dataset",
        dataset=DATASET_NAME,
        destination=str(RAW_DIR),
    )

    try:
        local_path = snapshot_download(
            repo_id=DATASET_NAME,
            repo_type="dataset",
            local_dir=str(RAW_DIR),
            resume_download=True,
        )
        logger.info("download_complete", local_path=local_path)
    except Exception as e:
        logger.error("download_failed", error=str(e))
        raise

    # Create source manifest with file hashes
    manifest = create_manifest(RAW_DIR, MANIFEST_PATH)
    logger.info(
        "download_verified",
        total_files=manifest["total_files"],
        total_bytes=manifest["total_bytes"],
    )

    return Path(local_path)


def create_sample(n_series: int = 1000, seed: int = 42) -> None:
    """
    Create a small sample dataset for development.

    Selects n_series unique (store_id, product_id) combinations
    and extracts all their daily records.
    """
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas not installed. Run: pip install pandas")
        sys.exit(1)

    logger.info("creating_sample", n_series=n_series, seed=seed)

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    # Find all parquet files in raw directory
    parquet_files = list(RAW_DIR.rglob("*.parquet"))
    if not parquet_files:
        logger.error("no_parquet_files_found", raw_dir=str(RAW_DIR))
        sys.exit(1)

    # Read all parquet files
    dfs = []
    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf)
            df["_source_file"] = pf.name
            df["_source_split"] = (
                "train" if "train" in str(pf).lower() else "eval"
            )
            dfs.append(df)
            logger.info("loaded_file", file=pf.name, rows=len(df))
        except Exception as e:
            logger.warning("failed_to_load", file=pf.name, error=str(e))

    if not dfs:
        logger.error("no_data_loaded")
        sys.exit(1)

    full_df = pd.concat(dfs, ignore_index=True)
    logger.info("full_dataset_loaded", total_rows=len(full_df))

    # Sample unique series
    if "store_id" in full_df.columns and "product_id" in full_df.columns:
        series_keys = (
            full_df[["store_id", "product_id"]]
            .drop_duplicates()
            .sample(n=min(n_series, len(full_df[["store_id", "product_id"]].drop_duplicates())), random_state=seed)
        )
        sample_df = full_df.merge(series_keys, on=["store_id", "product_id"])
    else:
        # Fallback: just take first n rows
        sample_df = full_df.head(n_series * 90)

    sample_path = SAMPLE_DIR / "sample_dataset.parquet"
    sample_df.to_parquet(sample_path, index=False)

    logger.info(
        "sample_created",
        n_series=len(series_keys) if "store_id" in full_df.columns else "N/A",
        total_rows=len(sample_df),
        path=str(sample_path),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Download FreshRetailNet-50K dataset"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if manifest exists",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Number of series to sample for development (0 = skip)",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Random seed for sample selection",
    )
    args = parser.parse_args()

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    # Download
    download_dataset(force=args.force)

    # Optionally create sample
    if args.sample > 0:
        create_sample(n_series=args.sample, seed=args.sample_seed)

    logger.info("done")


if __name__ == "__main__":
    main()
