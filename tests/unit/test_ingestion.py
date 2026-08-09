"""
Unit tests for FreshFlow AI Ingestion Manifest system.
"""

import tempfile
from pathlib import Path

from ingestion.source_manifest import SourceFile, SourceManifest


def test_source_file_dataclass():
    sf = SourceFile(
        filename="sales.csv",
        relative_path="raw/sales.csv",
        size_bytes=1024,
        sha256="dummyhash123",
        source_split="train"
    )
    assert sf.filename == "sales.csv"
    assert sf.ingested is False
    assert sf.ingestion_batch_id is None


def test_source_manifest_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_file = Path(tmpdir) / "source_manifest.json"

        file1 = SourceFile(
            filename="data1.parquet",
            relative_path="data1.parquet",
            size_bytes=500,
            sha256="hash1",
            source_split="train"
        )

        manifest = SourceManifest(
            dataset="test-dataset",
            downloaded_at="2026-01-01T00:00:00Z",
            total_files=1,
            total_bytes=500,
            files=[file1]
        )

        manifest.save(path=manifest_file)
        assert manifest_file.exists()

        loaded = SourceManifest.load(path=manifest_file)
        assert loaded.dataset == "test-dataset"
        assert loaded.total_files == 1
        assert loaded.files[0].filename == "data1.parquet"


def test_manifest_pending_and_parquet_filters():
    f1 = SourceFile(filename="a.parquet", relative_path="a.parquet", size_bytes=100, sha256="h1", ingested=False)
    f2 = SourceFile(filename="b.csv", relative_path="b.csv", size_bytes=200, sha256="h2", ingested=True)

    manifest = SourceManifest(files=[f1, f2])

    pending = manifest.get_pending_files()
    assert len(pending) == 1
    assert pending[0].filename == "a.parquet"

    parquets = manifest.get_parquet_files()
    assert len(parquets) == 1
    assert parquets[0].filename == "a.parquet"
