from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Dict, List

import pandas as pd
import streamlit as st

from src.services.invoice_service import InvoiceService
from src.services.newebpay_service import NewebPayService
from src.services.sheet_service import (
    read_accounting_rows,
    filter_invoice_rows,
    filter_allowance_rows,
    write_invoice_result,
    write_allowance_result,
)
from src.services.lemonclean_service import fetch_order_detail_from_lemonclean
from src.utils.money import calc_pretax, calc_tax


st.set_page_config(
    page_title="檸檬家事發票系統",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
.block-container { padding-top: 0.5rem !important; max-width: 1480px; }
.top-logo {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 0 4px 0; font-size: 19px; font-weight: 700;
    color: #0F6E56; border-bottom: 1px solid #e8e8e8; margin-bottom: 0.5rem;
}
</style>
""",
    unsafe_allow_html=True,
)

DEFAULT_REGIONS = ["台北", "台中", "桃園", "新竹", "高雄"]
TABS = ["首頁", "開立發票", "發票下載", "開立折讓單", "藍新金流", "下載檔案", "設定"]


def default_region_config() -> Dict[str, Dict[str, str]]:
    cfg: Dict[str, Dict[str, str]] = {}
    for region in DEFAULT_REGIONS:
        cfg[region] = {
            "invoice_wsdl": "https://www.ei.com.tw/InvoiceB2C/InvoiceAPI?wsdl",
            "invoice_test_wsdl": "http://invoice.cetustek.com.tw/InvoiceB2C/InvoiceAPI?wsdl",
            "invoice_rent_id": "",
            "lemon_user": "",
            "lemon_pass": "",
            "sheet_id": "",
            "sheet_name_accounting": "",
            "newebpay_merchant_id": "",
            "newebpay_hash_key": "",
            "newebpay_hash_iv": "",
            "newebpay_cancel_url": "https://core.spgateway.com/API/CreditCard/Cancel",
        }
    return cfg


defaults = {
    "active_tab": "首頁",
    "active_region": DEFAULT_REGIONS[0],
    "region_config": default_region_config(),
    "date_start": date.today().replace(day=1),
    "date_end": date.today(),
    "dry_run": True,
    "accounting_df": None,
    "invoice_df": None,
    "allowance_df": None,
    "execution_log": [],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "data") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def normalized_order_id(raw_id: str) -> str:
    raw_id = str(raw_id).strip()
    return raw_id if raw_id.endswith("-1") else f"{raw_id}-1"


def get_regions() -> List[str]:
    return list(st.session_state.region_config.keys())


def get_cfg(region: str) -> Dict[str, str]:
    return st.session_state.region_config.get(region, {})


def is_region_ready(region: str) -> bool:
    cfg = get_cfg(region)
    required = ["invoice_rent_id", "sheet_id", "lemon_user", "lemon_pass"]
    return all(bool(cfg.get(k)) for k in required)


def add_log(message: str) -> None:
    st.session_state.execution_log.insert(0, f"{date.today()}｜{message}")


def build_invoice_payload(row: pd.Series, order: Dict[str, str]) -> Dict[str, object]:
    has_tax_id = bool(order.get("統編"))
    invoice_name = order.get("抬頭") if has_tax_id else order.get("客戶姓名")

    return {
        "order_id": row["訂單編號_系統"],
        "order_date": date.today().strftime("%Y/%m/%d"),
        "buyer_identifier": order.get("統編", ""),
        "buyer_name": invoice_name,
        "buyer_address": order.get("地址", ""),
        "buyer_email": order.get("Email", ""),
        "donate_mark": 2 if has_tax_id else 0,
        "carrier_type": "",
        "carrier_id1": "",
        "carrier_id2": "",
        "npoban": "",
        "tax_type": 1,
        "tax_rate": 0.05,
        "pay_way": 3,
        "production_code": order.get("服務類型代碼", "1"),
        "description": order.get("服務名稱", "清潔服務"),
        "unit_price": int(row["發票金額"]),
        "is_tax_included": has_tax_id,
        "region": row["區域"],
    }


def render_top_nav() -> None:
    st.markdown('<div class="top-logo">🧾 檸檬家事發票系統</div>', unsafe_allow_html=True)
    tab_cols = st.columns(len(TABS))
    for i, (col, tab_name) in enumerate(zip(tab_cols, TABS)):
        with col:
            label = f"**{tab_name}**" if tab_name == st.session_state.active_tab else tab_name
            if st.button(label, key=f"tab_{i}", use_container_width=True):
                st.session_state.active_tab = tab_name
                st.rerun()
    st.markdown("---")


def render_filter_bar() -> bool:
    if st.session_state.active_tab == "設定":
        return False

    regions = get_regions()
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1.5])

    with c1:
        st.session_state.date_start = st.date_input("開始日期", st.session_state.date_start, label_visibility="collapsed")
    with c2:
        st.session_state.date_end = st.date_input("結束日期", st.session_state.date_end, label_visibility="collapsed")
    with c3:
        if st.session_state.active_region not in regions:
            st.session_state.active_region = regions[0]
        st.session_state.active_region = st.selectbox(
            "執行區域",
            regions,
            index=regions.index(st.session_state.active_region),
            label_visibility="collapsed",
        )
    with c4:
        st.session_state.dry_run = st.toggle("測試模式，不真正送出", value=st.session_state.dry_run)
    with c5:
        clicked = st.button("▶ 讀取帳務表", type="primary", use_container_width=True)

    st.markdown("---")
    return clicked


def page_home() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("目前區域", region)
    c2.metric("來源", "同一張帳務工作表")
    c3.metric("發票判斷", "B欄=待收款")
    c4.metric("折讓判斷", "B欄=待退款")

    st.subheader("新版判斷規則")
    st.markdown(
        """
- 同一張帳務處理表。
- **B 欄狀態 = 待收款**：開立發票。
- **B 欄狀態 = 待退款**：開立折讓單。
- **G 欄訂單編號**：用來登入檸檬官網查詢訂單資料。
- 系統使用的訂單編號會自動轉成：`G欄訂單編號-1`。
- 開立完成後，只回填同一張帳務處理表，不回寫檸檬家事後台。
"""
    )

    st.subheader(f"{region} 設定狀態")
    rows = [
        {"項目": "發票 RentID", "狀態": "✅" if cfg.get("invoice_rent_id") else "❌"},
        {"項目": "檸檬家事帳號", "狀態": "✅" if cfg.get("lemon_user") else "❌"},
        {"項目": "檸檬家事密碼", "狀態": "✅" if cfg.get("lemon_pass") else "❌"},
        {"項目": "帳務處理表 ID", "狀態": "✅" if cfg.get("sheet_id") else "❌"},
        {"項目": "帳務工作表名稱", "狀態": "✅" if cfg.get("sheet_name_accounting") else "可空白"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def load_and_split_accounting_rows(region: str, cfg: Dict[str, str]) -> None:
    accounting_df = read_accounting_rows(
        region,
        cfg,
        st.session_state.date_start,
        st.session_state.date_end,
        dry_run=st.session_state.dry_run,
    )
    st.session_state.accounting_df = accounting_df
    st.session_state.invoice_df = filter_invoice_rows(accounting_df)
    st.session_state.allowance_df = filter_allowance_rows(accounting_df)
    add_log(f"已讀取 {region} 帳務工作表：待收款 {len(st.session_state.invoice_df)} 筆，待退款 {len(st.session_state.allowance_df)} 筆")


def page_issue_invoice() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)
    st.subheader(f"開立發票｜{region}")

    df = st.session_state.invoice_df
    if df is None:
        st.info("請按「▶ 讀取帳務表」，系統會從同一張工作表篩選 B 欄為「待收款」的資料。")
        return

    enriched_rows = []
    for _, row in df.iterrows():
        row = row.copy()
        row["訂單編號_系統"] = normalized_order_id(row["G欄訂單編號"])
        order = fetch_order_detail_from_lemonclean(region, row["訂單編號_系統"], cfg, dry_run=st.session_state.dry_run)
        payload = build_invoice_payload(row, order)
        enriched_rows.append({
            **row.to_dict(),
            **order,
            "發票姓名欄": payload["buyer_name"],
            "是否含稅": "是" if payload["is_tax_included"] else "否",
        })

    view_df = pd.DataFrame(enriched_rows)
    st.markdown(f"共找到 **{len(view_df)}** 筆 B 欄為「待收款」資料")
    st.dataframe(view_df, use_container_width=True, hide_index=True)

    if st.button("🧾 批次開立發票並回填同一張帳務表", type="primary"):
        service = InvoiceService(cfg, dry_run=st.session_state.dry_run)
        results = []

        for _, row in view_df.iterrows():
            order = fetch_order_detail_from_lemonclean(region, row["訂單編號_系統"], cfg, dry_run=st.session_state.dry_run)
            payload = build_invoice_payload(row, order)
            result = service.create_invoice(payload)

            if result["success"]:
                write_invoice_result(region, cfg, int(row["列號"]), result, dry_run=st.session_state.dry_run)

            results.append({
                "列號": row["列號"],
                "G欄訂單編號": row["G欄訂單編號"],
                "訂單編號_系統": row["訂單編號_系統"],
                "發票金額": row["發票金額"],
                "發票號碼": result.get("invoice_no", ""),
                "結果": result.get("message", ""),
            })

        st.success("發票流程完成。")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)


def page_invoice_download() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)
    st.subheader(f"發票下載／查詢｜{region}")

    order_id = st.text_input("訂單編號，可留空改用帳務表資料")
    service = InvoiceService(cfg, dry_run=st.session_state.dry_run)

    if st.button("查詢單筆發票號碼"):
        result = service.query_invoice_number(normalized_order_id(order_id))
        st.json(result)

    st.divider()
    df = st.session_state.invoice_df
    if df is None:
        st.info("按「▶ 讀取帳務表」後可批次查詢 B 欄待收款資料的發票號碼。")
        return

    if st.button("批次查詢發票號碼"):
        results = []
        for _, row in df.iterrows():
            oid = normalized_order_id(row["G欄訂單編號"])
            result = service.query_invoice_number(oid)
            results.append({
                "列號": row["列號"],
                "G欄訂單編號": row["G欄訂單編號"],
                "訂單編號_系統": oid,
                "發票號碼": result.get("invoice_no", ""),
                "結果": result.get("message", ""),
            })

        out = pd.DataFrame(results)
        st.dataframe(out, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇ 下載查詢結果",
            data=to_excel_bytes(out, "發票查詢"),
            file_name=f"invoice_query_{region}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def page_allowance() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)
    st.subheader(f"開立折讓單｜{region}")

    df = st.session_state.allowance_df
    if df is None:
        st.info("請按「▶ 讀取帳務表」，系統會從同一張工作表篩選 B 欄為「待退款」的資料。")
        return

    df = df.copy()
    df["訂單編號_系統"] = df["G欄訂單編號"].apply(normalized_order_id)
    df["折讓未稅金額"] = df["折讓含稅金額"].apply(calc_pretax)
    df["折讓稅額"] = df["折讓含稅金額"].apply(calc_tax)

    st.markdown(f"共找到 **{len(df)}** 筆 B 欄為「待退款」資料")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("📄 批次開立折讓單並回填同一張帳務表", type="primary"):
        service = InvoiceService(cfg, dry_run=st.session_state.dry_run)
        results = []

        for _, row in df.iterrows():
            result = service.create_allowance({
                "order_id": row["訂單編號_系統"],
                "invoice_no": row["發票號碼"],
                "allowance_amount_with_tax": int(row["折讓含稅金額"]),
                "allowance_amount_pretax": int(row["折讓未稅金額"]),
                "allowance_tax": int(row["折讓稅額"]),
                "reason": row.get("退款原因", "退款折讓"),
                "allowance_date": date.today().strftime("%Y/%m/%d"),
            })

            if result["success"]:
                write_allowance_result(region, cfg, int(row["列號"]), result, dry_run=st.session_state.dry_run)

            results.append({
                "列號": row["列號"],
                "G欄訂單編號": row["G欄訂單編號"],
                "訂單編號_系統": row["訂單編號_系統"],
                "發票號碼": row["發票號碼"],
                "折讓含稅金額": row["折讓含稅金額"],
                "折讓未稅金額": row["折讓未稅金額"],
                "折讓稅額": row["折讓稅額"],
                "折讓單號": result.get("allowance_no", ""),
                "結果": result.get("message", ""),
            })

        st.success("折讓單流程完成。")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)


def page_newebpay() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)
    st.subheader(f"藍新金流｜{region}")

    merchant_order_no = st.text_input("MerchantOrderNo / 訂單編號")
    amount = st.number_input("取消授權金額", min_value=0, step=1)
    service = NewebPayService(cfg, dry_run=st.session_state.dry_run)

    if st.button("執行藍新取消授權"):
        result = service.cancel_credit_card(merchant_order_no, int(amount))
        st.json(result)


def page_download_files() -> None:
    region = st.session_state.active_region
    st.subheader(f"下載檔案｜{region}")

    if st.session_state.accounting_df is not None:
        st.download_button(
            "⬇ 下載完整帳務表讀取結果",
            data=to_excel_bytes(st.session_state.accounting_df, "帳務表"),
            file_name=f"accounting_rows_{region}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if st.session_state.invoice_df is not None:
        st.download_button(
            "⬇ 下載待開發票資料（B欄待收款）",
            data=to_excel_bytes(st.session_state.invoice_df, "待開發票"),
            file_name=f"pending_invoices_{region}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if st.session_state.allowance_df is not None:
        st.download_button(
            "⬇ 下載待開折讓單資料（B欄待退款）",
            data=to_excel_bytes(st.session_state.allowance_df, "待開折讓單"),
            file_name=f"pending_allowances_{region}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def page_settings() -> None:
    st.subheader("區域設定")
    st.warning("正式帳密請放 Streamlit Cloud Secrets，不要 commit 到 GitHub。")

    for rname in get_regions():
        cfg = st.session_state.region_config[rname]
        with st.expander(f"📍 {rname}", expanded=(rname == st.session_state.active_region)):
            with st.form(f"settings_{rname}"):
                st.markdown("**鯨躍／關網發票 SOAP**")
                c1, c2 = st.columns(2)
                invoice_rent_id = c1.text_input("RentID / 公司統編", value=cfg.get("invoice_rent_id", ""))
                invoice_wsdl = c2.text_input("正式 WSDL", value=cfg.get("invoice_wsdl", ""))

                st.markdown("**檸檬家事帳密（只讀）**")
                c3, c4 = st.columns(2)
                lemon_user = c3.text_input("檸檬家事帳號", value=cfg.get("lemon_user", ""))
                lemon_pass = c4.text_input("檸檬家事密碼", value=cfg.get("lemon_pass", ""), type="password")

                st.markdown("**同一張帳務工作表**")
                sheet_id = st.text_input("Google Sheet ID", value=cfg.get("sheet_id", ""))
                sheet_name_accounting = st.text_input(
                    "帳務工作表名稱",
                    value=cfg.get("sheet_name_accounting", ""),
                    placeholder="例如：清潔異動。可空白，空白時讀第一個工作表",
                )

                st.markdown("**藍新金流**")
                c8, c9, c10 = st.columns(3)
                newebpay_merchant_id = c8.text_input("MerchantID", value=cfg.get("newebpay_merchant_id", ""))
                newebpay_hash_key = c9.text_input("HashKey", value=cfg.get("newebpay_hash_key", ""), type="password")
                newebpay_hash_iv = c10.text_input("HashIV", value=cfg.get("newebpay_hash_iv", ""), type="password")

                submitted = st.form_submit_button("儲存設定", type="primary", use_container_width=True)
                if submitted:
                    st.session_state.region_config[rname] = {
                        **cfg,
                        "invoice_rent_id": invoice_rent_id,
                        "invoice_wsdl": invoice_wsdl,
                        "lemon_user": lemon_user,
                        "lemon_pass": lemon_pass,
                        "sheet_id": sheet_id,
                        "sheet_name_accounting": sheet_name_accounting,
                        "newebpay_merchant_id": newebpay_merchant_id,
                        "newebpay_hash_key": newebpay_hash_key,
                        "newebpay_hash_iv": newebpay_hash_iv,
                    }
                    st.success(f"已儲存 {rname} 設定。")
                    st.rerun()

    st.divider()
    st.subheader("Streamlit Secrets 範本")
    st.code(open(".streamlit/secrets.example.toml", "r", encoding="utf-8").read(), language="toml")


def page_logs() -> None:
    if not st.session_state.execution_log:
        return
    st.divider()
    st.subheader("執行紀錄")
    for item in st.session_state.execution_log[:10]:
        st.caption(item)


render_top_nav()
run_clicked = render_filter_bar()

if run_clicked and st.session_state.active_region:
    region = st.session_state.active_region
    cfg = get_cfg(region)

    if not is_region_ready(region):
        st.warning(f"{region} 尚未完整設定，請先到「設定」填寫。")
    else:
        load_and_split_accounting_rows(region, cfg)

tab = st.session_state.active_tab

if tab == "首頁":
    page_home()
elif tab == "開立發票":
    page_issue_invoice()
elif tab == "發票下載":
    page_invoice_download()
elif tab == "開立折讓單":
    page_allowance()
elif tab == "藍新金流":
    page_newebpay()
elif tab == "下載檔案":
    page_download_files()
elif tab == "設定":
    page_settings()

page_logs()
