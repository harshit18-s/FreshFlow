"""
FreshFlow AI — Source Manifest Manager
=======================================
Tracks source files, versions, and hashes for reproducible ingestion.

The manifest is the single source of truth for:
- What files were downloaded
- When they were downloaded
- Their integrity hashes
- Their processing status

Usage:
    from ingestion.source_manifest import SourceManifest
    manifest = SourceManifest.load()
    manifest.verify_integrity()
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MANIFEST_PATH = DATA_DIR / "source_manifest.json"


@dataclass
class SourceFile:
    """Represents a single source file in the manifest."""
    filename: str
    relative_path: str
    size_bytes: int
    sha256: str
    source_split: str = "unknown"
    ingested: bool = False
    ingested_at: Optional[str] = None
    ingestion_batch_id: Optional[str] = None


@dataclass
class SourceManifest:
    """
    Source manifest tracking all downloaded files.

    Supports:
    - Integrity verification via SHA-256 hashes
    - Idempotent re-download detection
    - Ingestion tracking per file
    """
    dataset: str = "Dingdong-Inc/FreshRetailNet-50K"
    downloaded_at: str = ""
    download_tool: str = "huggingface_hub"
    schema_version: str = "1.0"
    total_files: int = 0
    total_bytes: int = 0
    files: list[SourceFile] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = MANIFEST_PATH) -> "SourceManifest":
        """Load manifest from JSON file."""
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found: {path}")

        with open(path) as f:
            data = json.load(f)

        files = [SourceFile(**fd) for fd in data.get("files", [])]
        return cls(
            dataset=data.get("dataset", cls.dataset),
            downloaded_at=data.get("downloaded_at", ""),
            download_tool=data.get("download_tool", ""),
            schema_version=data.get("schema_version", "1.0"),
            total_files=data.get("total_files", len(files)),
            total_bytes=data.get("total_bytes", 0),
            files=files,
        )

    def save(self, path: Path = MANIFEST_PATH) -> None:
        """Save manifest to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "dataset": self.dataset,
            "downloaded_at": self.downloaded_at,
            "download_tool": self.download_tool,
            "schema_version": self.schema_version,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "files": [asdict(f) for f in self.files],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("manifest_saved", path=str(path))

    def verify_integrity(self, raw_dir: Path = DATA_DIR / "raw") -> dict:
        """
        Verify all files against stored hashes.

        Returns a dict with verification results.
        """
        results = {
            "total": len(self.files),
            "verified": 0,
            "missing": 0,
            "corrupted": 0,
            "details": [],
        }

        for sf in self.files:
            filepath = raw_dir / sf.relative_path
            if not filepath.exists():
                results["missing"] += 1
                results["details"].append({
                    "file": sf.relative_path,
                    "status": "MISSING",
                })
                continue

            actual_hash = self._compute_hash(filepath)
            if actual_hash == sf.sha256:
                results["verified"] += 1
                results["details"].append({
                    "file": sf.relative_path,
                    "status": "OK",
                })
            else:
                results["corrupted"] += 1
                results["details"].append({
                    "file": sf.relative_path,
                    "status": "CORRUPTED",
                    "expected_hash": sf.sha256,
                    "actual_hash": actual_hash,
                })

        logger.info(
            "integrity_check_complete",
            verified=results["verified"],
            missing=results["missing"],
            corrupted=results["corrupted"],
        )
        return results

    def mark_ingested(
        self, filename: str, batch_id: str
    ) -> None:
        """Mark a file as ingested."""
        for sf in self.files:
            if sf.filename == filename:
                sf.ingested = True
                sf.ingested_at = datetime.now(timezone.utc).isoformat()
                sf.ingestion_batch_id = batch_id
                logger.info(
                    "file_marked_ingested",
                    filename=filename,
                    batch_id=batch_id,
                )
                return
        logger.warning("file_not_in_manifest", filename=filename)

    def get_pending_files(self) -> list[SourceFile]:
        """Get files that haven't been ingested yet."""
        return [f for f in self.files if not f.ingested]

    def get_parquet_files(self) -> list[SourceFile]:
        """Get only parquet data files."""
        return [
            f for f in self.files
            if f.filename.endswith(".parquet")
        ]

    @staticmethod
    def _compute_hash(filepath: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
