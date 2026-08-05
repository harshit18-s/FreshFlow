"""
FreshFlow AI — Source Data Profiler
====================================
Profiles the FreshRetailNet-50K raw dataset to understand structure,
distributions, data quality issues, and validate assumptions from the
dataset documentation.

This profiler must run BEFORE building the ETL pipeline to confirm:
- Column names and types match expectations
- Array lengths are consistently 24
- sale_amount distribution and relationship with hours_sale
- hours_stock_status domain values
- discount distribution (1.0 = no discount, 0.9 = 10% off, etc.)
- Missing dates, duplicate keys, null patterns
- Weather field distributions

Usage:
    python ingestion/source_profiler.py
    python ingestion/source_profiler.py --input data/sample/sample_dataset.parquet
    python ingestion/source_profiler.py --output-dir reports/profiling

Output:
    Generates a comprehensive profiling report in JSON and markdown formats.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_DIR = Path(__file__).resolve().parent.parent / "reports" / "profiling"

# Expected columns from the dataset documentation
EXPECTED_COLUMNS = {
    "city_id": "integer",
    "store_id": "integer",
    "management_group_id": "integer",
    "first_category_id": "integer",
    "second_category_id": "integer",
    "third_category_id": "integer",
    "product_id": "integer",
    "dt": "date/string",
    "sale_amount": "numeric",
    "hours_sale": "array",
    "stock_hour6_22_cnt": "integer",
    "hours_stock_status": "array",
    "discount": "numeric",
    "holiday_flag": "integer/boolean",
    "activity_flag": "integer/boolean",
    "precpt": "numeric",
    "avg_temperature": "numeric",
    "avg_humidity": "numeric",
    "avg_wind_level": "numeric",
}


def profile_column_basic(series) -> dict:
    """Generate basic profile stats for a single column."""
    import numpy as np

    profile = {
        "dtype": str(series.dtype),
        "count": int(series.count()),
        "null_count": int(series.isnull().sum()),
        "null_pct": round(float(series.isnull().mean()) * 100, 4),
        "n_unique": int(series.nunique()),
    }

    if series.dtype in ("int64", "float64", "int32", "float32"):
        profile.update({
            "min": float(series.min()) if not series.empty else None,
            "max": float(series.max()) if not series.empty else None,
            "mean": round(float(series.mean()), 4) if not series.empty else None,
            "median": round(float(series.median()), 4) if not series.empty else None,
            "std": round(float(series.std()), 4) if not series.empty else None,
            "q25": round(float(series.quantile(0.25)), 4) if not series.empty else None,
            "q75": round(float(series.quantile(0.75)), 4) if not series.empty else None,
            "n_zeros": int((series == 0).sum()),
            "n_negative": int((series < 0).sum()),
        })

    return profile


def profile_array_column(series) -> dict:
    """Profile an array/list column (hours_sale, hours_stock_status)."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return {"status": "all_null"}

    lengths = non_null.apply(lambda x: len(x) if isinstance(x, (list, tuple)) else 0)

    profile = {
        "count": int(len(non_null)),
        "null_count": int(series.isnull().sum()),
        "length_min": int(lengths.min()),
        "length_max": int(lengths.max()),
        "length_mean": round(float(lengths.mean()), 2),
        "length_mode": int(lengths.mode().iloc[0]) if not lengths.empty else None,
        "all_length_24": bool((lengths == 24).all()),
        "pct_length_24": round(float((lengths == 24).mean()) * 100, 4),
        "non_24_count": int((lengths != 24).sum()),
        "length_distribution": lengths.value_counts().head(10).to_dict(),
    }

    # Flatten a sample to check value distributions
    try:
        import numpy as np
        flat_values = []
        for arr in non_null.head(10000):
            if isinstance(arr, (list, tuple)):
                flat_values.extend(arr)
        if flat_values:
            flat_arr = np.array(flat_values, dtype=float)
            profile["flat_sample_stats"] = {
                "min": float(np.nanmin(flat_arr)),
                "max": float(np.nanmax(flat_arr)),
                "mean": round(float(np.nanmean(flat_arr)), 4),
                "n_zeros": int((flat_arr == 0).sum()),
                "n_negative": int((flat_arr < 0).sum()),
                "pct_zeros": round(float((flat_arr == 0).mean()) * 100, 2),
                "unique_values_sample": sorted(set(flat_arr))[:20],
            }
    except Exception as e:
        profile["flat_sample_error"] = str(e)

    return profile


def check_primary_key(df, keys: list[str]) -> dict:
    """Check primary key uniqueness and completeness."""
    pk_check = {
        "key_columns": keys,
        "total_rows": len(df),
    }

    # Check for nulls in key columns
    null_in_keys = df[keys].isnull().any(axis=1).sum()
    pk_check["null_in_keys"] = int(null_in_keys)

    # Check for duplicates
    duplicates = df.duplicated(subset=keys, keep=False)
    pk_check["duplicate_rows"] = int(duplicates.sum())
    pk_check["unique_combinations"] = int(df[keys].drop_duplicates().shape[0])
    pk_check["is_unique"] = bool(pk_check["duplicate_rows"] == 0)

    if pk_check["duplicate_rows"] > 0:
        dup_sample = (
            df[duplicates]
            .groupby(keys)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(10)
        )
        pk_check["top_duplicate_keys"] = dup_sample.to_dict("records")

    return pk_check


def check_date_coverage(df, date_col: str, store_col: str, product_col: str) -> dict:
    """Check date coverage and identify gaps."""
    import pandas as pd

    date_check = {}

    try:
        dates = pd.to_datetime(df[date_col])
        date_check["min_date"] = str(dates.min())
        date_check["max_date"] = str(dates.max())
        date_check["n_unique_dates"] = int(dates.nunique())
        date_check["date_range_days"] = int((dates.max() - dates.min()).days + 1)

        # Full date range
        full_range = pd.date_range(dates.min(), dates.max(), freq="D")
        actual_dates = set(dates.dt.date.unique())
        expected_dates = set(d.date() for d in full_range)
        missing_dates = sorted(expected_dates - actual_dates)
        date_check["missing_dates"] = [str(d) for d in missing_dates[:20]]
        date_check["n_missing_dates"] = len(missing_dates)

        # Series completeness
        series_counts = df.groupby([store_col, product_col])[date_col].nunique()
        date_check["series_stats"] = {
            "total_series": int(len(series_counts)),
            "min_days_per_series": int(series_counts.min()),
            "max_days_per_series": int(series_counts.max()),
            "mean_days_per_series": round(float(series_counts.mean()), 1),
            "median_days_per_series": round(float(series_counts.median()), 1),
        }
    except Exception as e:
        date_check["error"] = str(e)

    return date_check


def check_sale_vs_hourly_consistency(df) -> dict:
    """Compare sale_amount against sum of hours_sale array."""
    import numpy as np

    consistency = {}
    try:
        non_null = df.dropna(subset=["sale_amount", "hours_sale"])
        hourly_sums = non_null["hours_sale"].apply(
            lambda x: sum(x) if isinstance(x, (list, tuple)) else np.nan
        )

        diff = non_null["sale_amount"] - hourly_sums
        abs_diff = diff.abs()

        consistency["n_compared"] = int(len(non_null))
        consistency["exact_match"] = int((abs_diff < 1e-6).sum())
        consistency["close_match_1pct"] = int(
            (abs_diff / (non_null["sale_amount"].abs() + 1e-9) < 0.01).sum()
        )
        consistency["max_abs_diff"] = round(float(abs_diff.max()), 6)
        consistency["mean_abs_diff"] = round(float(abs_diff.mean()), 6)
        consistency["median_abs_diff"] = round(float(abs_diff.median()), 6)
        consistency["pct_exact_match"] = round(
            float((abs_diff < 1e-6).mean()) * 100, 2
        )
    except Exception as e:
        consistency["error"] = str(e)

    return consistency


def generate_profile_report(input_path: Path, output_dir: Path) -> dict:
    """Generate a comprehensive profiling report."""
    import pandas as pd

    logger.info("starting_profiling", input_path=str(input_path))

    # Load data
    if input_path.suffix == ".parquet":
        df = pd.read_parquet(input_path)
    elif input_path.is_dir():
        parquet_files = list(input_path.rglob("*.parquet"))
        if not parquet_files:
            logger.error("no_parquet_files", path=str(input_path))
            sys.exit(1)
        dfs = [pd.read_parquet(f) for f in parquet_files]
        df = pd.concat(dfs, ignore_index=True)
        logger.info("loaded_files", n_files=len(parquet_files))
    else:
        logger.error("unsupported_format", path=str(input_path))
        sys.exit(1)

    logger.info("data_loaded", rows=len(df), columns=len(df.columns))

    report: dict[str, Any] = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_path": str(input_path),
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "column_names": list(df.columns),
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
        },
    }

    # ── Schema check ──
    logger.info("checking_schema")
    expected_found = {
        col: col in df.columns for col in EXPECTED_COLUMNS
    }
    unexpected = [c for c in df.columns if c not in EXPECTED_COLUMNS and not c.startswith("_")]
    report["schema"] = {
        "expected_columns_found": expected_found,
        "all_expected_present": all(expected_found.values()),
        "missing_expected": [c for c, v in expected_found.items() if not v],
        "unexpected_columns": unexpected,
    }

    # ── Column profiles ──
    logger.info("profiling_columns")
    column_profiles = {}
    for col in df.columns:
        if col.startswith("_"):
            continue
        if col in ("hours_sale", "hours_stock_status"):
            column_profiles[col] = profile_array_column(df[col])
        else:
            column_profiles[col] = profile_column_basic(df[col])
    report["column_profiles"] = column_profiles

    # ── Primary key check ──
    logger.info("checking_primary_key")
    if all(c in df.columns for c in ["store_id", "product_id", "dt"]):
        report["primary_key"] = check_primary_key(
            df, ["store_id", "product_id", "dt"]
        )

    # ── Date coverage ──
    logger.info("checking_date_coverage")
    if all(c in df.columns for c in ["dt", "store_id", "product_id"]):
        report["date_coverage"] = check_date_coverage(
            df, "dt", "store_id", "product_id"
        )

    # ── Sale vs hourly consistency ──
    logger.info("checking_sale_hourly_consistency")
    if all(c in df.columns for c in ["sale_amount", "hours_sale"]):
        report["sale_hourly_consistency"] = check_sale_vs_hourly_consistency(df)

    # ── Discount distribution ──
    logger.info("profiling_discount")
    if "discount" in df.columns:
        discount_dist = df["discount"].value_counts().head(20)
        report["discount_distribution"] = {
            "top_values": discount_dist.to_dict(),
            "n_unique": int(df["discount"].nunique()),
            "has_values_above_1": bool((df["discount"] > 1.0).any()),
            "pct_no_discount_eq_1": round(
                float((df["discount"] == 1.0).mean()) * 100, 2
            ),
        }

    # ── Stock status domain ──
    logger.info("profiling_stock_status")
    if "hours_stock_status" in df.columns:
        try:
            flat_status = []
            for arr in df["hours_stock_status"].dropna().head(50000):
                if isinstance(arr, (list, tuple)):
                    flat_status.extend(arr)
            from collections import Counter
            status_counts = Counter(flat_status)
            report["stock_status_domain"] = {
                "unique_values": sorted(status_counts.keys()),
                "value_counts": dict(status_counts.most_common(20)),
                "total_sampled": len(flat_status),
            }
        except Exception as e:
            report["stock_status_domain"] = {"error": str(e)}

    # ── Hierarchy stats ──
    logger.info("profiling_hierarchy")
    hierarchy_cols = [
        "city_id", "store_id", "management_group_id",
        "first_category_id", "second_category_id", "third_category_id",
        "product_id",
    ]
    hierarchy = {}
    for col in hierarchy_cols:
        if col in df.columns:
            hierarchy[col] = {
                "n_unique": int(df[col].nunique()),
                "sample_values": sorted(df[col].dropna().unique()[:10].tolist()),
            }
    report["hierarchy"] = hierarchy

    # ── Stockout summary ──
    logger.info("computing_stockout_summary")
    if "stock_hour6_22_cnt" in df.columns:
        soh = df["stock_hour6_22_cnt"]
        report["stockout_summary"] = {
            "mean_stockout_hours_6_22": round(float(soh.mean()), 2),
            "pct_zero_stockout": round(float((soh == 0).mean()) * 100, 2),
            "pct_any_stockout": round(float((soh > 0).mean()) * 100, 2),
            "pct_full_stockout_16h": round(float((soh >= 16).mean()) * 100, 2),
            "distribution": soh.value_counts().sort_index().head(20).to_dict(),
        }

    # ── Derived scale estimates ──
    report["scale_estimates"] = {
        "source_daily_rows": len(df),
        "exploded_hourly_rows_est": len(df) * 24,
        "operational_hour_rows_est": len(df) * 16,  # 06:00-22:00
    }

    # ── Save report ──
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "source_profile.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("json_report_saved", path=str(json_path))

    # Generate markdown summary
    md_path = output_dir / "source_profile.md"
    write_markdown_report(report, md_path)
    logger.info("markdown_report_saved", path=str(md_path))

    return report


def write_markdown_report(report: dict, output_path: Path) -> None:
    """Write a human-readable markdown profiling report."""
    lines = [
        "# FreshFlow AI — Source Data Profile Report",
        "",
        f"**Generated:** {report['meta']['generated_at']}",
        f"**Input:** `{report['meta']['input_path']}`",
        f"**Rows:** {report['meta']['total_rows']:,}",
        f"**Columns:** {report['meta']['total_columns']}",
        f"**Memory:** {report['meta']['memory_usage_mb']} MB",
        "",
        "---",
        "",
        "## Schema Validation",
        "",
    ]

    schema = report.get("schema", {})
    if schema.get("all_expected_present"):
        lines.append("✅ All expected columns present.")
    else:
        lines.append("❌ Missing columns: " + ", ".join(schema.get("missing_expected", [])))

    if schema.get("unexpected_columns"):
        lines.append(f"⚠️  Unexpected columns: {', '.join(schema['unexpected_columns'])}")

    # Primary key
    pk = report.get("primary_key", {})
    if pk:
        lines.extend([
            "",
            "## Primary Key Check",
            "",
            f"- Key: `{pk.get('key_columns')}`",
            f"- Unique: **{'✅ Yes' if pk.get('is_unique') else '❌ No'}**",
            f"- Duplicate rows: {pk.get('duplicate_rows', 0):,}",
            f"- Null in keys: {pk.get('null_in_keys', 0):,}",
        ])

    # Date coverage
    dc = report.get("date_coverage", {})
    if dc:
        lines.extend([
            "",
            "## Date Coverage",
            "",
            f"- Range: {dc.get('min_date')} → {dc.get('max_date')}",
            f"- Unique dates: {dc.get('n_unique_dates')}",
            f"- Expected days: {dc.get('date_range_days')}",
            f"- Missing dates: {dc.get('n_missing_dates')}",
        ])
        ss = dc.get("series_stats", {})
        if ss:
            lines.extend([
                f"- Total series: {ss.get('total_series', 0):,}",
                f"- Days per series: {ss.get('min_days_per_series')}–{ss.get('max_days_per_series')} "
                f"(mean {ss.get('mean_days_per_series')})",
            ])

    # Array columns
    for arr_col in ("hours_sale", "hours_stock_status"):
        ap = report.get("column_profiles", {}).get(arr_col, {})
        if ap:
            lines.extend([
                "",
                f"## Array Column: `{arr_col}`",
                "",
                f"- All length 24: **{'✅ Yes' if ap.get('all_length_24') else '❌ No'}**",
                f"- % length 24: {ap.get('pct_length_24')}%",
                f"- Non-24 count: {ap.get('non_24_count', 0):,}",
            ])
            flat = ap.get("flat_sample_stats", {})
            if flat:
                lines.extend([
                    f"- Value range: [{flat.get('min')}, {flat.get('max')}]",
                    f"- Mean: {flat.get('mean')}",
                    f"- % zeros: {flat.get('pct_zeros')}%",
                    f"- Negative values: {flat.get('n_negative')}",
                ])

    # Sale vs hourly consistency
    shc = report.get("sale_hourly_consistency", {})
    if shc:
        lines.extend([
            "",
            "## Sale Amount vs Hourly Sum Consistency",
            "",
            f"- Compared: {shc.get('n_compared', 0):,} rows",
            f"- Exact match: {shc.get('pct_exact_match', 0)}%",
            f"- Max absolute diff: {shc.get('max_abs_diff')}",
            f"- Mean absolute diff: {shc.get('mean_abs_diff')}",
        ])

    # Discount
    dd = report.get("discount_distribution", {})
    if dd:
        lines.extend([
            "",
            "## Discount Distribution",
            "",
            f"- Unique values: {dd.get('n_unique')}",
            f"- % no discount (==1.0): {dd.get('pct_no_discount_eq_1')}%",
            f"- Values above 1.0: **{'⚠️ Yes' if dd.get('has_values_above_1') else '✅ No'}**",
        ])

    # Stock status domain
    ssd = report.get("stock_status_domain", {})
    if ssd and "unique_values" in ssd:
        lines.extend([
            "",
            "## Stock Status Domain Values",
            "",
            f"- Unique values: `{ssd.get('unique_values')}`",
            f"- Total sampled: {ssd.get('total_sampled', 0):,}",
        ])

    # Stockout summary
    so = report.get("stockout_summary", {})
    if so:
        lines.extend([
            "",
            "## Stockout Summary (stock_hour6_22_cnt)",
            "",
            f"- Mean stockout hours (6–22): {so.get('mean_stockout_hours_6_22')}",
            f"- % zero stockout days: {so.get('pct_zero_stockout')}%",
            f"- % any stockout: {so.get('pct_any_stockout')}%",
            f"- % full day stockout (≥16h): {so.get('pct_full_stockout_16h')}%",
        ])

    # Scale estimates
    se = report.get("scale_estimates", {})
    if se:
        lines.extend([
            "",
            "## Scale Estimates",
            "",
            f"- Source daily rows: {se.get('source_daily_rows', 0):,}",
            f"- Exploded hourly (×24): {se.get('exploded_hourly_rows_est', 0):,}",
            f"- Operational hours (×16): {se.get('operational_hour_rows_est', 0):,}",
        ])

    # Hierarchy
    hier = report.get("hierarchy", {})
    if hier:
        lines.extend([
            "",
            "## Hierarchy Summary",
            "",
            "| Column | Unique Values |",
            "|--------|--------------|",
        ])
        for col, info in hier.items():
            lines.append(f"| `{col}` | {info.get('n_unique', 0):,} |")

    lines.extend(["", "---", "", "*Report generated by FreshFlow AI Source Profiler*"])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Profile FreshRetailNet-50K source data"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to input file or directory (default: data/raw)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for reports (default: reports/profiling)",
    )
    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    input_path = Path(args.input) if args.input else DATA_DIR / "raw"
    output_dir = Path(args.output_dir) if args.output_dir else REPORT_DIR

    report = generate_profile_report(input_path, output_dir)

    # Print key findings
    print("\n" + "=" * 60)
    print("KEY FINDINGS")
    print("=" * 60)
    print(f"Total rows:       {report['meta']['total_rows']:,}")
    print(f"Total columns:    {report['meta']['total_columns']}")

    schema = report.get("schema", {})
    print(f"Schema valid:     {'✅' if schema.get('all_expected_present') else '❌'}")

    pk = report.get("primary_key", {})
    if pk:
        print(f"PK unique:        {'✅' if pk.get('is_unique') else '❌'}")

    for arr_col in ("hours_sale", "hours_stock_status"):
        ap = report.get("column_profiles", {}).get(arr_col, {})
        if ap:
            print(f"{arr_col} all-24: {'✅' if ap.get('all_length_24') else '❌'}")

    se = report.get("scale_estimates", {})
    if se:
        print(f"Hourly estimate:  {se.get('exploded_hourly_rows_est', 0):,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
