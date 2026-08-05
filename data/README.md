# 📁 Data Directory — FreshFlow AI

This directory holds all data at every stage of the medallion architecture pipeline.

## Directory Layout

```
data/
├── raw/            # Original dataset downloads (CSV, JSON)
├── bronze/         # Raw ingested data (append-only, Parquet/Delta)
├── silver/         # Cleaned, validated, deduplicated data
├── gold/           # Business-ready aggregates & feature tables
├── sample/         # Small subsets for dev/test (10% of raw)
└── quarantine/     # Records that failed data quality checks
```

## Medallion Architecture

| Layer | Purpose | Format | Retention |
|-------|---------|--------|-----------|
| **Raw** | Exact copy of source data | CSV / JSON | Permanent |
| **Bronze** | Append-only ingestion, schema-on-read | Parquet / Delta | Permanent |
| **Silver** | Cleaned, typed, deduplicated | Parquet / Delta | Permanent |
| **Gold** | Aggregated, feature-engineered, ML-ready | Parquet / Delta | Versioned |
| **Sample** | Subset for fast dev iteration | Parquet | Regenerated |
| **Quarantine** | Failed quality / validation checks | Parquet + JSON logs | 90 days |

## How to Download the Dataset

```bash
# Using Make
make download-data

# Or directly
python ingestion/download_dataset.py
```

The download script will place files into `data/raw/`.

## ⚠️ Important Notes

- **This directory is gitignored.** Data files are NOT committed to version control.
- **Do not manually modify** files in `bronze/`, `silver/`, or `gold/` — they are pipeline-managed.
- **Quarantine** data should be reviewed periodically and either fixed or archived.
- **Sample** data is auto-generated during bootstrap for local development.

## Dataset Attribution

- **Source**: Supermarket Sales & Waste Dataset — Dingdong-Inc
- **License**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
