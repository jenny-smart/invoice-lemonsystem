from __future__ import annotations

from datetime import date
from typing import Dict, Optional

import pandas as pd


def _sample_invoice_rows(region: str) -> pd.DataFrame:
    return pd.DataFrame([
        {"列號": 2, "區域": region, "原始訂單編號": "LC202605240001", "訂單編號": "LC202605240001-1", "發票金額": 3000, "發票號碼": "", "處理狀態": "待開立"},
        {"列號": 3, "區域": region, "原始訂單編號": "LC202605230042", "訂單編號": "LC202605230042-1", "發票金額": 5250, "發票號碼": "", "處理狀態": "待開立"},
    ])


def _sample_allowance_rows(region: str) -> pd.DataFrame:
    return pd.DataFrame([
        {"列號": 2, "區域": region, "原始訂單編號": "LC202605180009", "訂單編號": "LC202605180009-1", "發票號碼": "CD98765432", "折讓含稅金額": 1050, "折讓原因": "部分退款", "折讓單號": "", "處理狀態": "待開立"},
    ])


def read_invoice_rows_from_accounting_sheet(region: str, cfg: Dict[str, str], date_start: date, date_end: date, dry_run: bool = True) -> pd.DataFrame:
    if dry_run:
        return _sample_invoice_rows(region)

    # TODO: Replace with gspread service account auth.
    # Required columns: 列號, 原始訂單編號, 發票金額, 發票號碼, 處理狀態
    raise NotImplementedError("Google Sheets 讀取尚未接上 service account。")


def read_allowance_rows_from_accounting_sheet(region: str, cfg: Dict[str, str], date_start: date, date_end: date, dry_run: bool = True) -> pd.DataFrame:
    if dry_run:
        return _sample_allowance_rows(region)

    # TODO: Replace with gspread service account auth.
    # Required columns: 列號, 原始訂單編號, 發票號碼, 折讓含稅金額, 折讓原因, 折讓單號, 處理狀態
    raise NotImplementedError("Google Sheets 讀取尚未接上 service account。")


def write_invoice_result(region: str, cfg: Dict[str, str], row_number: int, result: Dict[str, object], dry_run: bool = True) -> None:
    if dry_run:
        return
    # TODO: Update 發票號碼 / 處理狀態 / 錯誤訊息 in the regional accounting sheet.
    raise NotImplementedError("Google Sheets 回填尚未接上 service account。")


def write_allowance_result(region: str, cfg: Dict[str, str], row_number: int, result: Dict[str, object], dry_run: bool = True) -> None:
    if dry_run:
        return
    # TODO: Update 折讓單號 / 處理狀態 / 錯誤訊息 in the regional accounting sheet.
    raise NotImplementedError("Google Sheets 回填尚未接上 service account。")


def write_newebpay_result(region: str, cfg: Dict[str, str], row_number: Optional[int], result: Dict[str, object], dry_run: bool = True) -> None:
    if dry_run:
        return
    # TODO: Update 藍新處理結果.
    raise NotImplementedError("Google Sheets 回填尚未接上 service account。")
