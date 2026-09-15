from __future__ import annotations

import pandas as pd
import pytest

from supermarket_etl.pipeline import DataQualityError, build_summary, transform


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Invoice ID": "A-1",
                "Branch": "A",
                "City": "Cairo",
                "Customer type": "Member",
                "Gender": "Female",
                "Product line": "Food",
                "Unit price": 10,
                "Quantity": 2,
                "Tax 5%": 1,
                "Sales": 21,
                "Date": "2026-01-02",
                "Time": "10:00",
                "Payment": "E-wallet",
                "cogs": 20,
                "gross margin percentage": 4.76,
                "gross income": 1,
                "Rating": 8,
            },
            {
                "Invoice ID": "A-2",
                "Branch": "B",
                "City": "Giza",
                "Customer type": "Normal",
                "Gender": "Male",
                "Product line": "Sports",
                "Unit price": 5,
                "Quantity": 2,
                "Tax 5%": 0.5,
                "Sales": 10.5,
                "Date": None,
                "Time": "11:00",
                "Payment": "Cash",
                "cogs": 10,
                "gross margin percentage": 4.76,
                "gross income": 0.5,
                "Rating": 6,
            },
            {
                "Invoice ID": "A-1",
                "Branch": "A",
                "City": "Cairo",
                "Customer type": "Member",
                "Gender": "Female",
                "Product line": "Food",
                "Unit price": 10,
                "Quantity": 2,
                "Tax 5%": 1,
                "Sales": 21,
                "Date": "2026-01-02",
                "Time": "10:00",
                "Payment": "Ewallet",
                "cogs": 20,
                "gross margin percentage": 4.76,
                "gross income": 1,
                "Rating": 8,
            },
        ]
    )


def test_transform_rejects_invalid_and_duplicate_rows() -> None:
    clean, rejects, quality = transform(sample_frame())
    assert clean["invoice_id"].tolist() == ["A-1"]
    assert clean.loc[0, "payment_method"] == "Ewallet"
    assert clean.loc[0, "satisfaction"] == "Satisfied"
    assert set(rejects["rejection_reason"]) == {"duplicate_invoice_id", "missing_or_invalid_date"}
    assert quality["clean_rows"] == 1
    assert quality["revenue_reconciliation_failures"] == 0


def test_summary_uses_clean_transactions() -> None:
    clean, _, _ = transform(sample_frame())
    summary = build_summary(clean)
    assert summary["total_revenue"] == 21.0
    assert summary["highest_revenue_city"] == "Cairo"
    assert summary["overall_satisfaction_percent"] == 100.0


def test_missing_schema_is_rejected() -> None:
    with pytest.raises(DataQualityError, match="Missing required columns"):
        transform(pd.DataFrame({"Invoice ID": ["A-1"]}))
