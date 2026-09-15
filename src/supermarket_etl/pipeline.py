from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

LOGGER = logging.getLogger("supermarket_etl")

COLUMN_NAMES = {
    "Invoice ID": "invoice_id",
    "Branch": "branch",
    "City": "city",
    "Customer type": "customer_type",
    "Gender": "gender",
    "Product line": "product_line",
    "Unit price": "unit_price",
    "Quantity": "quantity",
    "Tax 5%": "tax",
    "Sales": "sales",
    "Date": "date",
    "Time": "time",
    "Payment": "payment_method",
    "cogs": "cost_of_goods_sold",
    "gross margin percentage": "gross_margin_percentage",
    "gross income": "gross_income",
    "Rating": "rating",
}

REQUIRED_COLUMNS = frozenset(COLUMN_NAMES)
NUMERIC_COLUMNS = (
    "unit_price",
    "quantity",
    "tax",
    "sales",
    "cost_of_goods_sold",
    "gross_margin_percentage",
    "gross_income",
    "rating",
)
CRITICAL_COLUMNS = (
    "invoice_id",
    "branch",
    "city",
    "product_line",
    "date",
    "time",
    "payment_method",
    *NUMERIC_COLUMNS,
)


class DataQualityError(ValueError):
    """Raised when an input cannot safely enter the transformation stage."""


@dataclass(frozen=True)
class PipelineResult:
    input_rows: int
    clean_rows: int
    rejected_rows: int
    duplicate_rows_removed: int
    revenue_reconciliation_failures: int
    output_path: str
    reject_path: str


def _snake_case(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return value.strip("_").lower()


def validate_schema(frame: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise DataQualityError(f"Missing required columns: {', '.join(missing)}")


def transform(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Clean a raw supermarket frame and return clean rows, rejects, and metrics."""
    validate_schema(frame)
    working = frame.rename(columns=COLUMN_NAMES).copy()
    working.columns = [_snake_case(column) for column in working.columns]
    input_rows = len(working)

    for column in working.select_dtypes(include=["object", "string"]):
        working[column] = working[column].astype("string").str.strip()
        working[column] = working[column].replace({"": pd.NA})

    for column in ("branch", "city", "customer_type", "gender"):
        working[column] = working[column].str.title()

    working["payment_method"] = working["payment_method"].replace(
        {"E-wallet": "Ewallet", "e-wallet": "Ewallet", "Credit Card": "Credit card"}
    )

    for column in NUMERIC_COLUMNS:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    working["date"] = pd.to_datetime(working["date"], errors="coerce")

    unit_price_missing = working["unit_price"].isna()
    recoverable_unit_price = (
        unit_price_missing & working["cost_of_goods_sold"].notna() & working["quantity"].gt(0)
    )
    working.loc[recoverable_unit_price, "unit_price"] = (
        working.loc[recoverable_unit_price, "cost_of_goods_sold"]
        / working.loc[recoverable_unit_price, "quantity"]
    )

    duplicate_mask = working.duplicated(subset=["invoice_id"], keep="first")
    duplicate_rows_removed = int(duplicate_mask.sum())
    duplicate_rejects = working.loc[duplicate_mask].assign(rejection_reason="duplicate_invoice_id")
    working = working.loc[~duplicate_mask].copy()

    invalid_reason = pd.Series("", index=working.index, dtype="string")
    for column in CRITICAL_COLUMNS:
        missing = working[column].isna()
        invalid_reason = invalid_reason.mask(
            missing & invalid_reason.eq(""), f"missing_or_invalid_{column}"
        )

    invalid_ranges = (
        working["sales"].lt(0)
        | working["unit_price"].lt(0)
        | working["quantity"].lt(1)
        | ~working["rating"].between(0, 10, inclusive="both")
    )
    invalid_reason = invalid_reason.mask(
        invalid_ranges & invalid_reason.eq(""), "numeric_value_out_of_range"
    )

    invalid_mask = invalid_reason.ne("")
    invalid_rejects = working.loc[invalid_mask].assign(
        rejection_reason=invalid_reason.loc[invalid_mask]
    )
    clean = working.loc[~invalid_mask].copy()

    clean["day"] = clean["date"].dt.day.astype("int64")
    clean["month"] = clean["date"].dt.month.astype("int64")
    clean["year"] = clean["date"].dt.year.astype("int64")
    clean["satisfaction"] = clean["rating"].ge(7).map({True: "Satisfied", False: "Not Satisfied"})
    clean = clean.sort_values(["date", "time", "invoice_id"], kind="stable").reset_index(drop=True)

    rejects = pd.concat([duplicate_rejects, invalid_rejects], ignore_index=True, sort=False)
    reconciled = (
        (clean["cost_of_goods_sold"] + clean["gross_income"]).round(4).eq(clean["sales"].round(4))
    )
    reconciliation_failures = int((~reconciled).sum())

    quality = {
        "input_rows": input_rows,
        "clean_rows": len(clean),
        "rejected_rows": len(rejects),
        "duplicate_rows_removed": duplicate_rows_removed,
        "unit_price_values_imputed": int(recoverable_unit_price.sum()),
        "null_counts_after_cleaning": {
            key: int(value) for key, value in clean.isna().sum().items()
        },
        "unique_invoice_ids": int(clean["invoice_id"].nunique()),
        "revenue_reconciliation_failures": reconciliation_failures,
    }
    return clean, rejects, quality


def build_summary(clean: pd.DataFrame) -> dict[str, Any]:
    revenue_by_city = (
        clean.groupby("city", observed=True)["sales"].sum().sort_values(ascending=False)
    )
    profit_by_branch = (
        clean.groupby("branch", observed=True)["gross_income"].sum().sort_values(ascending=False)
    )
    category = (
        clean.groupby("product_line", observed=True)
        .agg(revenue=("sales", "sum"), profit=("gross_income", "sum"))
        .sort_values("revenue", ascending=False)
    )
    customer_spend = (
        clean.groupby("customer_type", observed=True)["sales"].sum().sort_values(ascending=False)
    )
    payment_counts = clean["payment_method"].value_counts()
    satisfaction_by_branch = (
        clean.assign(is_satisfied=clean["satisfaction"].eq("Satisfied"))
        .groupby("branch", observed=True)["is_satisfied"]
        .mean()
        .mul(100)
        .sort_values(ascending=False)
    )
    revenue_by_day = (
        clean.groupby(clean["date"].dt.strftime("%Y-%m-%d"))["sales"]
        .sum()
        .sort_values(ascending=False)
    )
    revenue_by_month = (
        clean.groupby(clean["date"].dt.strftime("%Y-%m"))["sales"]
        .sum()
        .sort_values(ascending=False)
    )

    return {
        "total_revenue": round(float(clean["sales"].sum()), 2),
        "average_transaction_value": round(float(clean["sales"].mean()), 2),
        "overall_satisfaction_percent": round(float(clean["rating"].ge(7).mean() * 100), 2),
        "highest_revenue_city": revenue_by_city.index[0],
        "most_profitable_branch": profit_by_branch.index[0],
        "top_product_category": category.index[0],
        "highest_spending_customer_type": customer_spend.index[0],
        "most_popular_payment_method": payment_counts.index[0],
        "highest_satisfaction_branch": satisfaction_by_branch.index[0],
        "highest_sales_day": revenue_by_day.index[0],
        "highest_sales_month": revenue_by_month.index[0],
        "revenue_by_city": {k: round(float(v), 2) for k, v in revenue_by_city.items()},
        "profit_by_branch": {k: round(float(v), 2) for k, v in profit_by_branch.items()},
        "category_performance": {
            k: {"revenue": round(float(v["revenue"]), 2), "profit": round(float(v["profit"]), 2)}
            for k, v in category.to_dict(orient="index").items()
        },
    }


def run_pipeline(input_path: Path, output_dir: Path) -> PipelineResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_path = output_dir / "supermarket_clean.csv"
    reject_path = output_dir / "supermarket_rejects.csv"
    quality_path = output_dir / "data_quality.json"
    summary_path = output_dir / "business_summary.json"

    LOGGER.info("reading input", extra={"input_path": str(input_path)})
    raw = pd.read_csv(input_path)
    clean, rejects, quality = transform(raw)
    summary = build_summary(clean)

    clean.to_csv(clean_path, index=False, date_format="%Y-%m-%d")
    rejects.to_csv(reject_path, index=False, date_format="%Y-%m-%d")
    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    result = PipelineResult(
        input_rows=quality["input_rows"],
        clean_rows=quality["clean_rows"],
        rejected_rows=quality["rejected_rows"],
        duplicate_rows_removed=quality["duplicate_rows_removed"],
        revenue_reconciliation_failures=quality["revenue_reconciliation_failures"],
        output_path=str(clean_path),
        reject_path=str(reject_path),
    )
    LOGGER.info("pipeline complete", extra=asdict(result))
    return result
