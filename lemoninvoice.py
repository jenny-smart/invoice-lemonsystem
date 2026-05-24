"""
檸檬家事發票系統 - Streamlit App
主入口：lemoninvoice.py

新版流程：
- 台北 / 台中 / 桃園 / 新竹 / 高雄各自設定發票系統帳密、檸檬家事帳密、帳務處理表 ID。
- 不寫回檸檬家事後台，只從檸檬家事抓資料。
- 從各區帳務處理表讀取訂單編號、發票金額、發票號碼、折讓單含稅金額。
- 訂單編號一律轉成「原訂單編號-1」。
- 有統編時：原發票姓名欄填抬頭、填統編欄位、選含稅。
- 開完發票號碼或折讓單號後，回填各區帳務處理表。
"""

from __future__ import annotations
from datetime import date
from io import BytesIO
from typing import Dict, List
import pandas as pd
import streamlit as st

st.set_page_config(page_title="檸檬家事發票系統", page_icon="🧾", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
.block-container { padding-top: 0.5rem !important; max-width: 1400px; }
.top-logo { display:flex; align-items:center; gap:10px; padding:10px 0 4px 0; font-size:19px; font-weight:700; color:#0F6E56; border-bottom:1px solid #e8e8e8; margin-bottom:0.5rem; }
</style>
""", unsafe_allow_html=True)

DEFAULT_REGIONS = ["台北", "台中", "桃園", "新竹", "高雄"]
ACTION_TYPES = ["開立發票", "開立折讓單", "全部"]
TABS = ["首頁", "開立發票", "開立折讓單", "下載發票", "下載紙本發票", "設定"]

def default_region_config() -> Dict[str, Dict[str, str]]:
    return {r: {
        "invoice_user": "", "invoice_pass": "",
        "lemon_user": "", "lemon_pass": "",
        "sheet_id": "", "sheet_name_invoice": "開立發票", "sheet_name_allowance": "開立折讓單",
    } for r in DEFAULT_REGIONS}

def init_state():
    defaults = {
        "active_tab": "首頁", "active_region": DEFAULT_REGIONS[0],
        "region_config": default_region_config(),
        "date_start": date.today().replace(day=1), "date_end": date.today(),
        "action_type": "全部", "result_df": None, "allowance_df": None, "execution_log": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "data") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def normalized_order_id(raw_id: str) -> str:
    raw_id = str(raw_id).strip()
    return raw_id if raw_id.endswith("-1") else f"{raw_id}-1"

def calc_pretax(amount_with_tax: float, tax_rate: float = 0.05) -> int:
    return round(float(amount_with_tax) / (1 + tax_rate)) if amount_with_tax else 0

def calc_tax(amount_with_tax: float, tax_rate: float = 0.05) -> int:
    return int(round(float(amount_with_tax) - calc_pretax(amount_with_tax, tax_rate)))

def get_regions() -> List[str]:
    return list(st.session_state.region_config.keys())

def get_cfg(region: str) -> Dict[str, str]:
    return st.session_state.region_config.get(region, {})

def is_region_ready(region: str) -> bool:
    cfg = get_cfg(region)
    return all(cfg.get(k) for k in ["invoice_user", "invoice_pass", "lemon_user", "lemon_pass", "sheet_id"])

def add_log(message: str) -> None:
    st.session_state.execution_log.insert(0, f"{date.today()}｜{message}")

# TODO: replace stub functions with real Google Sheets / Lemonclean / invoice system integrations.
def read_invoice_rows_from_accounting_sheet(region: str, date_start: date, date_end: date) -> pd.DataFrame:
    rows = [
        {"列號": 2, "區域": region, "原始訂單編號": "LC202605240001", "訂單編號": normalized_order_id("LC202605240001"), "發票金額": 3000, "帳務表發票號碼": "", "處理狀態": "待開立"},
        {"列號": 3, "區域": region, "原始訂單編號": "LC202605230042", "訂單編號": normalized_order_id("LC202605230042"), "發票金額": 5250, "帳務表發票號碼": "", "處理狀態": "待開立"},
    ]
    return pd.DataFrame(rows)

def read_allowance_rows_from_accounting_sheet(region: str, date_start: date, date_end: date) -> pd.DataFrame:
    rows = [{"列號": 2, "區域": region, "原始訂單編號": "LC202605180009", "訂單編號": normalized_order_id("LC202605180009"), "發票號碼": "CD98765432", "折讓含稅金額": 1050, "折讓未稅金額": calc_pretax(1050), "折讓稅額": calc_tax(1050), "折讓原因": "部分退款", "折讓單號": "", "處理狀態": "待開立"}]
    return pd.DataFrame(rows)

def fetch_order_detail_from_lemonclean(region: str, order_id: str) -> Dict[str, str]:
    if order_id.endswith("0042-1"):
        return {"訂單編號": order_id, "客戶姓名": "範例公司", "抬頭": "範例股份有限公司", "統編": "12345678", "電話": "0912345678", "地址": "台北市範例區範例路 1 號", "Email": "example@company.com"}
    return {"訂單編號": order_id, "客戶姓名": "王小明", "抬頭": "", "統編": "", "電話": "0912345678", "地址": "台北市範例區檸檬路 1 號", "Email": "customer@example.com"}

def build_invoice_payload(row: pd.Series, order: Dict[str, str]) -> Dict[str, object]:
    has_tax_id = bool(order.get("統編"))
    return {
        "order_id": row["訂單編號"], "invoice_amount": int(row["發票金額"]),
        "invoice_name": order.get("抬頭") if has_tax_id else order.get("客戶姓名"),
        "buyer_tax_id": order.get("統編", ""), "is_tax_included": has_tax_id,
        "phone": order.get("電話", ""), "email": order.get("Email", ""), "address": order.get("地址", ""),
        "source_region": row["區域"],
    }

def issue_invoice_to_invoice_system(region: str, payload: Dict[str, object]) -> Dict[str, str]:
    fake_invoice_no = "AB" + str(abs(hash(payload["order_id"])))[0:8]
    return {"success": True, "invoice_no": fake_invoice_no, "message": "測試模式：發票開立成功"}

def issue_allowance_to_invoice_system(region: str, row: pd.Series) -> Dict[str, str]:
    fake_allowance_no = "AL" + str(abs(hash(str(row["發票號碼"]) + str(row["訂單編號"]))))[0:8]
    return {"success": True, "allowance_no": fake_allowance_no, "message": "測試模式：折讓單開立成功"}

def write_invoice_no_back_to_sheet(region: str, row_number: int, invoice_no: str) -> None:
    add_log(f"{region} 第 {row_number} 列已回填發票號碼 {invoice_no}")

def write_allowance_no_back_to_sheet(region: str, row_number: int, allowance_no: str) -> None:
    add_log(f"{region} 第 {row_number} 列已回填折讓單號 {allowance_no}")

st.markdown('<div class="top-logo">🧾 檸檬家事發票系統</div>', unsafe_allow_html=True)

tab_cols = st.columns(len(TABS))
for i, (col, tab_name) in enumerate(zip(tab_cols, TABS)):
    with col:
        label = f"**{tab_name}**" if tab_name == st.session_state.active_tab else tab_name
        if st.button(label, key=f"tab_{i}", use_container_width=True):
            st.session_state.active_tab = tab_name
            st.rerun()
st.markdown("---")

run_clicked = False
if st.session_state.active_tab != "設定":
    regions = get_regions()
    col_d1, col_d2, col_sep, col_act, col_reg, col_run = st.columns([2, 2, 0.2, 2, 2, 1.5])
    with col_d1:
        st.session_state.date_start = st.date_input("開始日期", value=st.session_state.date_start, key="filter_date_start", label_visibility="collapsed")
    with col_d2:
        st.session_state.date_end = st.date_input("結束日期", value=st.session_state.date_end, key="filter_date_end", label_visibility="collapsed")
    with col_sep:
        st.markdown("<div style='padding-top:8px;text-align:center;color:#9ca3af'>～</div>", unsafe_allow_html=True)
    with col_act:
        st.session_state.action_type = st.selectbox("執行項目", ACTION_TYPES, index=ACTION_TYPES.index(st.session_state.action_type), key="filter_action", label_visibility="collapsed")
    with col_reg:
        if st.session_state.active_region not in regions:
            st.session_state.active_region = regions[0]
        selected = st.selectbox("執行區域", regions, index=regions.index(st.session_state.active_region), key="filter_region", label_visibility="collapsed")
        if selected != st.session_state.active_region:
            st.session_state.active_region = selected
            st.session_state.result_df = None
            st.session_state.allowance_df = None
            st.rerun()
    with col_run:
        run_clicked = st.button("▶ 執行", type="primary", use_container_width=True)
    st.markdown("---")

if run_clicked and st.session_state.active_region:
    region = st.session_state.active_region
    tab = st.session_state.active_tab
    if not is_region_ready(region):
        st.warning(f"{region} 尚未完整設定帳密與帳務處理表 ID，請先到「設定」填寫。")
    else:
        with st.spinner(f"讀取 {region} 帳務處理表…"):
            if tab in ("首頁", "開立發票", "下載發票", "下載紙本發票"):
                st.session_state.result_df = read_invoice_rows_from_accounting_sheet(region, st.session_state.date_start, st.session_state.date_end)
                add_log(f"已讀取 {region} 待開發票資料")
            elif tab == "開立折讓單":
                st.session_state.allowance_df = read_allowance_rows_from_accounting_sheet(region, st.session_state.date_start, st.session_state.date_end)
                add_log(f"已讀取 {region} 待開折讓單資料")

def page_home() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("目前區域", region)
    c2.metric("發票資料來源", "帳務處理表")
    c3.metric("檸檬家事", "只讀")
    c4.metric("回填位置", "帳務處理表")
    st.divider()
    st.subheader("目前流程")
    st.markdown("""
1. 選擇區域。
2. 從該區帳務處理表讀取要處理的訂單。
3. 訂單編號一律轉成 `原訂單編號-1`。
4. 登入檸檬家事，只抓訂單資料，不回寫後台。
5. 登入該區發票系統開立發票或折讓單。
6. 將發票號碼或折讓單號回填該區帳務處理表。
""")
    st.subheader(f"{region} 設定狀態")
    rows = [{"項目": name, "狀態": "✅" if cfg.get(key) else "❌"} for name, key in [("發票系統帳號", "invoice_user"), ("發票系統密碼", "invoice_pass"), ("檸檬家事帳號", "lemon_user"), ("檸檬家事密碼", "lemon_pass"), ("帳務處理表 ID", "sheet_id")]]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def page_issue_invoice() -> None:
    region = st.session_state.active_region
    st.subheader(f"開立發票｜{region}")
    df = st.session_state.result_df
    if df is None:
        st.info("請設定日期與區域後按「▶ 執行」，從該區帳務處理表讀取待開發票訂單。")
        return
    enriched_rows = []
    for _, row in df.iterrows():
        order = fetch_order_detail_from_lemonclean(region, row["訂單編號"])
        payload = build_invoice_payload(row, order)
        enriched_rows.append({**row.to_dict(), **order, "發票姓名欄": payload["invoice_name"], "是否含稅": "是" if payload["is_tax_included"] else "否"})
    view_df = pd.DataFrame(enriched_rows)
    st.markdown(f"共找到 **{len(view_df)}** 筆待開發票資料")
    st.dataframe(view_df[["列號", "原始訂單編號", "訂單編號", "客戶姓名", "抬頭", "統編", "發票姓名欄", "是否含稅", "發票金額", "帳務表發票號碼", "處理狀態"]], use_container_width=True, hide_index=True)
    col_run, col_dl = st.columns([2, 1])
    with col_run:
        if st.button("🧾 批次開立發票並回填帳務表", type="primary", use_container_width=True):
            results = []
            for _, row in view_df.iterrows():
                order = fetch_order_detail_from_lemonclean(region, row["訂單編號"])
                payload = build_invoice_payload(row, order)
                result = issue_invoice_to_invoice_system(region, payload)
                if result["success"]:
                    write_invoice_no_back_to_sheet(region, int(row["列號"]), result["invoice_no"])
                results.append({"訂單編號": row["訂單編號"], "發票金額": row["發票金額"], "發票號碼": result.get("invoice_no", ""), "結果": result["message"]})
            st.success("測試模式完成：已模擬開立發票與回填帳務表。")
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    with col_dl:
        st.download_button("⬇ 匯出 Excel", data=to_excel_bytes(view_df, "待開發票"), file_name=f"invoices_{region}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

def page_allowance() -> None:
    region = st.session_state.active_region
    st.subheader(f"開立折讓單｜{region}")
    df = st.session_state.allowance_df
    if df is None:
        st.info("請設定日期與區域後按「▶ 執行」，從該區帳務處理表讀取待開折讓單資料。")
        return
    st.markdown(f"共找到 **{len(df)}** 筆待開折讓單資料")
    st.dataframe(df[["列號", "原始訂單編號", "訂單編號", "發票號碼", "折讓含稅金額", "折讓未稅金額", "折讓稅額", "折讓原因", "折讓單號", "處理狀態"]], use_container_width=True, hide_index=True)
    col_run, col_dl = st.columns([2, 1])
    with col_run:
        if st.button("📄 批次開立折讓單並回填帳務表", type="primary", use_container_width=True):
            results = []
            for _, row in df.iterrows():
                result = issue_allowance_to_invoice_system(region, row)
                if result["success"]:
                    write_allowance_no_back_to_sheet(region, int(row["列號"]), result["allowance_no"])
                results.append({"訂單編號": row["訂單編號"], "發票號碼": row["發票號碼"], "折讓含稅金額": row["折讓含稅金額"], "折讓未稅金額": row["折讓未稅金額"], "折讓稅額": row["折讓稅額"], "折讓單號": result.get("allowance_no", ""), "結果": result["message"]})
            st.success("測試模式完成：已模擬開立折讓單與回填帳務表。")
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    with col_dl:
        st.download_button("⬇ 匯出 Excel", data=to_excel_bytes(df, "待開折讓單"), file_name=f"allowances_{region}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

def page_export_invoices(paper_only: bool = False) -> None:
    region = st.session_state.active_region
    title = "下載紙本發票" if paper_only else "下載發票"
    st.subheader(f"{title}｜{region}")
    st.caption("正式串接後會從各區帳務處理表或發票系統下載指定期間資料。")
    if st.button("查詢", type="secondary"):
        df = read_invoice_rows_from_accounting_sheet(region, st.session_state.date_start, st.session_state.date_end)
        if paper_only:
            df = df.copy(); df["紙本發票"] = "待串接欄位"
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇ 下載 Excel", data=to_excel_bytes(df, "紙本發票" if paper_only else "發票"), file_name=(f"paper_invoices_{region}.xlsx" if paper_only else f"invoices_{region}.xlsx"), mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def page_settings() -> None:
    st.subheader("區域設定")
    st.caption("台北 / 台中 / 桃園 / 新竹 / 高雄各自設定發票系統帳密、檸檬家事帳密、帳務處理表 ID。")
    for rname in get_regions():
        cfg = st.session_state.region_config[rname]
        with st.expander(f"📍 {rname}", expanded=(rname == st.session_state.active_region)):
            with st.form(f"settings_{rname}"):
                st.markdown("**發票系統帳密**")
                c1, c2 = st.columns(2)
                invoice_user = c1.text_input("發票系統帳號", value=cfg.get("invoice_user", ""), key=f"inv_u_{rname}")
                invoice_pass = c2.text_input("發票系統密碼", value=cfg.get("invoice_pass", ""), type="password", key=f"inv_p_{rname}")
                st.markdown("**檸檬家事帳密**")
                c3, c4 = st.columns(2)
                lemon_user = c3.text_input("檸檬家事帳號", value=cfg.get("lemon_user", ""), key=f"lm_u_{rname}")
                lemon_pass = c4.text_input("檸檬家事密碼", value=cfg.get("lemon_pass", ""), type="password", key=f"lm_p_{rname}")
                st.markdown("**帳務處理表**")
                sheet_id = st.text_input("Google Sheet ID", value=cfg.get("sheet_id", ""), key=f"sheet_{rname}")
                c5, c6 = st.columns(2)
                sheet_name_invoice = c5.text_input("開立發票工作表名稱", value=cfg.get("sheet_name_invoice", "開立發票"), key=f"sheet_inv_{rname}")
                sheet_name_allowance = c6.text_input("開立折讓單工作表名稱", value=cfg.get("sheet_name_allowance", "開立折讓單"), key=f"sheet_alw_{rname}")
                if st.form_submit_button("儲存設定", type="primary", use_container_width=True):
                    st.session_state.region_config[rname] = {"invoice_user": invoice_user, "invoice_pass": invoice_pass, "lemon_user": lemon_user, "lemon_pass": lemon_pass, "sheet_id": sheet_id, "sheet_name_invoice": sheet_name_invoice, "sheet_name_allowance": sheet_name_allowance}
                    st.success(f"已儲存 {rname} 設定。")
                    st.rerun()
    st.divider(); st.subheader("Streamlit Secrets 範本")
    st.warning("請不要把正式帳號密碼 commit 到 GitHub。正式部署請使用 Streamlit Cloud Secrets。")
    st.code(open('.streamlit/secrets.example.toml', encoding='utf-8').read() if __import__('os').path.exists('.streamlit/secrets.example.toml') else '', language="toml")

def page_logs() -> None:
    if st.session_state.execution_log:
        st.divider(); st.subheader("執行紀錄")
        for item in st.session_state.execution_log[:10]: st.caption(item)

tab = st.session_state.active_tab
if tab == "首頁": page_home()
elif tab == "開立發票": page_issue_invoice()
elif tab == "開立折讓單": page_allowance()
elif tab == "下載發票": page_export_invoices(False)
elif tab == "下載紙本發票": page_export_invoices(True)
elif tab == "設定": page_settings()
page_logs()
