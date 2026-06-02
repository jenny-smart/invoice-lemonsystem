from __future__ import annotations

from datetime import date
from typing import Dict

import pandas as pd


def _sample_accounting_rows(region: str) -> pd.DataFrame:
    """
    模擬同一張帳務工作表。

    重要欄位：
    - B欄狀態：待收款 / 待退款
    - G欄訂單編號
    """
    return pd.DataFrame([
        {
            "列號": 39,
            "區域": region,
            "B欄狀態": "待退款",
            "退款原因": "異動服務退款",
            "G欄訂單編號": "LC00201697",
            "客戶姓名": "陳瑄妤",
            "發票金額": 0,
            "發票號碼": "AB12345678",
            "折讓含稅金額": 1050,
            "回填結果": "",
        },
        {
            "列號": 45,
            "區域": region,
            "B欄狀態": "待收款",
            "退款原因": "工具組收款",
            "G欄訂單編號": "LC00203920",
            "客戶姓名": "饒亞孟",
            "發票金額": 3000,
            "發票號碼": "",
            "折讓含稅金額": 0,
            "回填結果": "",
        },
        {
            "列號": 47,
            "區域": region,
            "B欄狀態": "待收款",
            "退款原因": "異動發票",
            "G欄訂單編號": "LC002041001",
            "客戶姓名": "張嘉芸",
            "發票金額": 5250,
            "發票號碼": "",
            "折讓含稅金額": 0,
            "回填結果": "",
        },
    ])


def normalize_accounting_dataframe(df: pd.DataFrame, region: str) -> pd.DataFrame:
    """
    將 Google Sheet 讀出的欄位標準化。

    若正式讀取時使用 A/B/C 欄原始標題，可在這裡做欄名對應。
    目前規格：
    - B欄：狀態，值包含「待收款」或「待退款」
    - G欄：訂單編號
    """
    df = df.copy()

    if "列號" not in df.columns:
        df.insert(0, "列號", range(2, len(df) + 2))

    if "區域" not in df.columns:
        df["區域"] = region

    aliases = {
        "狀態": "B欄狀態",
        "收退款狀態": "B欄狀態",
        "訂單編號": "G欄訂單編號",
        "訂編": "G欄訂單編號",
    }

    for old, new in aliases.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    required_defaults = {
        "B欄狀態": "",
        "G欄訂單編號": "",
        "發票金額": 0,
        "發票號碼": "",
        "折讓含稅金額": 0,
        "退款原因": "",
        "回填結果": "",
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    return df


def read_accounting_rows(region: str, cfg: Dict[str, str], date_start: date, date_end: date, dry_run: bool = True) -> pd.DataFrame:
    if dry_run:
        return normalize_accounting_dataframe(_sample_accounting_rows(region), region)

    # TODO: 接 gspread service account。
    # sheet_id = cfg["sheet_id"]
    # sheet_name = cfg.get("sheet_name_accounting") or first worksheet
    # 讀整張工作表後呼叫 normalize_accounting_dataframe
    raise NotImplementedError("Google Sheets 讀取尚未接上 service account。")


def filter_invoice_rows(accounting_df: pd.DataFrame) -> pd.DataFrame:
    df = accounting_df.copy()
    return df[df["B欄狀態"].astype(str).str.strip().eq("待收款")].reset_index(drop=True)


def filter_allowance_rows(accounting_df: pd.DataFrame) -> pd.DataFrame:
    df = accounting_df.copy()
    return df[df["B欄狀態"].astype(str).str.strip().eq("待退款")].reset_index(drop=True)


def write_invoice_result(region: str, cfg: Dict[str, str], row_number: int, result: Dict[str, object], dry_run: bool = True) -> None:
    if dry_run:
        return
    # TODO: 回填同一張帳務工作表：
    # - 發票號碼
    # - 回填結果 / 處理狀態
    # - 錯誤訊息
    raise NotImplementedError("Google Sheets 回填尚未接上 service account。")


def write_allowance_result(region: str, cfg: Dict[str, str], row_number: int, result: Dict[str, object], dry_run: bool = True) -> None:
    if dry_run:
        return
    # TODO: 回填同一張帳務工作表：
    # - 折讓單號
    # - 回填結果 / 處理狀態
    # - 錯誤訊息
    raise NotImplementedError("Google Sheets 回填尚未接上 service account。")
