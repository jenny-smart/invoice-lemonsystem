"""
檸檬家事發票系統 - Streamlit App
UI: 上方導覽列 + 執行日期區間 + 執行項目 + 執行區域（下拉）
區域完全由使用者在設定頁新增，無預設值
"""

import os
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

# ── 頁面設定 ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="檸檬家事發票系統",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 自訂 CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
.block-container { padding-top: 0.5rem !important; }
.top-logo {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 0 4px 0; font-size: 18px; font-weight: 600;
    color: #0F6E56; border-bottom: 1px solid #e8e8e8; margin-bottom: 0.5rem;
}
.badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.badge-success { background: #d1fae5; color: #065f46; }
.badge-warn    { background: #fef3c7; color: #92400e; }
.badge-gray    { background: #f3f4f6; color: #6b7280; }
.badge-danger  { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

# ── 常數 ──────────────────────────────────────────────────────────────────────
ACTION_TYPES = ["開立發票", "開立折讓單", "全部"]
TABS = ["首頁", "開立發票", "開立折讓單", "下載發票", "下載紙本發票", "設定"]

# ── Session State 初始化 ──────────────────────────────────────────────────────
defaults = {
    "active_tab":    "首頁",
    "active_region": None,        # 無預設，由使用者在設定頁新增
    "region_config": {},          # {區域名: {invoice_user, invoice_pass, lemon_user, lemon_pass, sheet_id}}
    "date_start":    date.today().replace(day=1),
    "date_end":      date.today(),
    "action_type":   "全部",
    "result_df":     None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 工具函式 ──────────────────────────────────────────────────────────────────
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="invoices")
    return output.getvalue()

def make_order_id(raw_id: str) -> str:
    if raw_id and not raw_id.endswith("-1"):
        return raw_id + "-1"
    return raw_id

def calc_pretax(amount_with_tax: float, tax_rate: float = 0.05) -> float:
    return round(amount_with_tax / (1 + tax_rate))

def get_regions() -> list[str]:
    return list(st.session_state.region_config.keys())

def get_cfg(region: str) -> dict:
    return st.session_state.region_config.get(region, {})

# ── 資料抓取佔位函式 ──────────────────────────────────────────────────────────
def fetch_pending_invoices(region, date_start, date_end) -> pd.DataFrame:
    return pd.DataFrame([
        {"原始訂單編號": "LC202605240001", "訂單編號": make_order_id("LC202605240001"),
         "客戶姓名": "王小明", "統編": "", "抬頭": "", "發票金額": 3000, "狀態": "待開立", "發票號碼": ""},
        {"原始訂單編號": "LC202605230042", "訂單編號": make_order_id("LC202605230042"),
         "客戶姓名": "範例公司", "統編": "12345678", "抬頭": "範例股份有限公司",
         "發票金額": 5250, "狀態": "已開立", "發票號碼": "AB12345678"},
    ])

def fetch_pending_allowances(region, date_start, date_end) -> pd.DataFrame:
    return pd.DataFrame([
        {"原始訂單編號": "LC202605180009", "訂單編號": make_order_id("LC202605180009"),
         "發票號碼": "CD98765432", "折讓含稅金額": 1050, "折讓未稅金額": calc_pretax(1050),
         "折讓原因": "部分退款", "狀態": "待開立", "折讓單號": ""},
    ])

# ── 頂部 Logo ─────────────────────────────────────────────────────────────────
st.markdown('<div class="top-logo">🧾 檸檬家事發票系統</div>', unsafe_allow_html=True)

# ── 頂部導覽列 ────────────────────────────────────────────────────────────────
tab_cols = st.columns(len(TABS))
for i, (col, tab_name) in enumerate(zip(tab_cols, TABS)):
    with col:
        label = f"**{tab_name}**" if tab_name == st.session_state.active_tab else tab_name
        if st.button(label, key=f"tab_{i}", use_container_width=True):
            st.session_state.active_tab = tab_name
            st.rerun()

st.markdown("---")

# ── 篩選工具列（非設定頁顯示）────────────────────────────────────────────────
run_clicked = False
if st.session_state.active_tab != "設定":
    regions = get_regions()
    col_d1, col_d2, col_sep, col_act, col_reg, col_run = st.columns([2, 2, 0.2, 2, 2, 1.5])

    with col_d1:
        st.session_state.date_start = st.date_input(
            "開始日期", value=st.session_state.date_start,
            key="filter_date_start", label_visibility="collapsed")

    with col_d2:
        st.session_state.date_end = st.date_input(
            "結束日期", value=st.session_state.date_end,
            key="filter_date_end", label_visibility="collapsed")

    with col_sep:
        st.markdown("<div style='padding-top:8px;text-align:center;color:#9ca3af'>～</div>",
                    unsafe_allow_html=True)

    with col_act:
        st.session_state.action_type = st.selectbox(
            "執行項目", ACTION_TYPES,
            index=ACTION_TYPES.index(st.session_state.action_type),
            key="filter_action", label_visibility="collapsed")

    with col_reg:
        if regions:
            # 確保 active_region 在清單內
            if st.session_state.active_region not in regions:
                st.session_state.active_region = regions[0]
            cur_idx = regions.index(st.session_state.active_region)
            selected = st.selectbox(
                "執行區域", regions, index=cur_idx,
                key="filter_region", label_visibility="collapsed")
            if selected != st.session_state.active_region:
                st.session_state.active_region = selected
                st.session_state.result_df = None
                st.rerun()
        else:
            st.selectbox("執行區域", ["（尚未設定區域）"],
                         disabled=True, label_visibility="collapsed")

    with col_run:
        run_clicked = st.button("▶ 執行", type="primary", use_container_width=True,
                                disabled=(not regions))

    st.markdown("---")

# ── 執行按鈕：抓資料 ──────────────────────────────────────────────────────────
if run_clicked and st.session_state.active_region:
    region = st.session_state.active_region
    tab    = st.session_state.active_tab
    with st.spinner(f"從帳務處理表讀取資料（{region}）…"):
        if tab in ("首頁", "開立發票", "下載發票", "下載紙本發票"):
            st.session_state.result_df = fetch_pending_invoices(
                region, st.session_state.date_start, st.session_state.date_end)
        elif tab == "開立折讓單":
            st.session_state.result_df = fetch_pending_allowances(
                region, st.session_state.date_start, st.session_state.date_end)

# ── 各頁面 ────────────────────────────────────────────────────────────────────

def page_home():
    regions = get_regions()
    if not regions:
        st.warning("尚未設定任何區域，請先至「設定」頁面新增區域。")
        return

    region = st.session_state.active_region or regions[0]
    cfg = get_cfg(region)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("今日開票張數", "0", help="來自帳務處理表")
    c2.metric("今日開票金額", "$0")
    c3.metric("待開票訂單",   "0")
    c4.metric("開票失敗",     "0")

    st.divider()
    st.subheader(f"目前區域：{region}")
    env_ok = all([cfg.get("invoice_user"), cfg.get("invoice_pass"), cfg.get("sheet_id")])
    if env_ok:
        st.success(f"✅ {region} 設定完整，可以執行。")
    else:
        st.warning(f"⚠️ {region} 有欄位未填寫，請至「設定」頁面確認。")
    st.info("MVP 介面。下一步接上帳務處理表（Google Sheets）與鯨躍／關網 SOAP API。")


def page_issue_invoice():
    region = st.session_state.active_region
    st.subheader(f"開立發票｜{region or '（未選區域）'}")
    df = st.session_state.result_df
    if df is None:
        st.info("請設定篩選條件後按「▶ 執行」讀取待開票訂單。")
        return
    if "折讓含稅金額" in df.columns:
        st.session_state.result_df = None
        st.info("請按「▶ 執行」重新讀取發票資料。")
        return

    pending = df[df["狀態"] == "待開立"]
    st.markdown(f"共找到 **{len(pending)}** 筆待開票訂單")
    st.dataframe(df[["訂單編號","客戶姓名","統編","抬頭","發票金額","狀態","發票號碼"]],
                 use_container_width=True, hide_index=True)

    if len(pending) > 0:
        col_run, col_dl = st.columns([2, 1])
        with col_run:
            if st.button("🧾 批次開立發票", type="primary"):
                st.info("正式串接後：登入發票系統→登入檸檬家事取得資訊→有統編填抬頭+統編+含稅→回填發票號碼至帳務表")
        with col_dl:
            st.download_button("⬇ 匯出 Excel", data=to_excel_bytes(df),
                               file_name=f"invoices_{region}_{date.today()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def page_allowance():
    region = st.session_state.active_region
    st.subheader(f"開立折讓單｜{region or '（未選區域）'}")
    df = st.session_state.result_df
    if df is None:
        st.info("請設定篩選條件後按「▶ 執行」讀取待開折讓單訂單。")
        return
    if "折讓含稅金額" not in df.columns:
        st.session_state.result_df = None
        st.info("請按「▶ 執行」重新讀取折讓單資料。")
        return

    pending = df[df["狀態"] == "待開立"]
    st.markdown(f"共找到 **{len(pending)}** 筆待開折讓單訂單")
    st.dataframe(df[["訂單編號","發票號碼","折讓含稅金額","折讓未稅金額","折讓原因","狀態","折讓單號"]],
                 use_container_width=True, hide_index=True)

    if len(pending) > 0:
        col_run, col_dl = st.columns([2, 1])
        with col_run:
            if st.button("📄 批次開立折讓單", type="primary"):
                st.info("正式串接後：取含稅金額→回推未稅（÷1.05）→開立折讓單→折讓單號回填帳務表")
        with col_dl:
            st.download_button("⬇ 匯出 Excel", data=to_excel_bytes(df),
                               file_name=f"allowances_{region}_{date.today()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def page_export_invoices(paper_only: bool = False):
    region = st.session_state.active_region
    title  = "下載紙本發票" if paper_only else "下載發票"
    st.subheader(f"{title}｜{region or '（未選區域）'}")
    if st.button("查詢", type="secondary"):
        df = fetch_pending_invoices(region, st.session_state.date_start, st.session_state.date_end)
        if paper_only:
            df = df[df["統編"] == ""]
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇ 下載 Excel", data=to_excel_bytes(df),
                           file_name=("paper_invoices.xlsx" if paper_only else "invoices.xlsx"),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def page_settings():
    st.subheader("區域設定")
    st.caption("所有資料僅存在本次 session，重新整理頁面後需重新輸入。如需永久保存請改用 secrets.toml。")

    # ── 新增區域表單 ──────────────────────────────────────────────────────────
    with st.expander("➕ 新增區域", expanded=(len(get_regions()) == 0)):
        with st.form("add_region_form", clear_on_submit=True):
            st.markdown("**區域基本資訊**")
            new_name = st.text_input("區域名稱", placeholder="例：台北、台中…")

            st.markdown("**發票系統帳密**")
            c1, c2 = st.columns(2)
            inv_user = c1.text_input("帳號", key="inv_u")
            inv_pass = c2.text_input("密碼", type="password", key="inv_p")

            st.markdown("**檸檬家事帳密**")
            c3, c4 = st.columns(2)
            lm_user = c3.text_input("帳號", key="lm_u")
            lm_pass = c4.text_input("密碼", type="password", key="lm_p")

            st.markdown("**帳務處理表**")
            sheet_id = st.text_input("Google Sheet ID", placeholder="試算表網址中間那段 ID")

            submitted = st.form_submit_button("新增區域", type="primary", use_container_width=True)
            if submitted:
                if not new_name.strip():
                    st.error("請填寫區域名稱。")
                elif new_name.strip() in st.session_state.region_config:
                    st.error(f"「{new_name.strip()}」已存在。")
                else:
                    st.session_state.region_config[new_name.strip()] = {
                        "invoice_user": inv_user,
                        "invoice_pass": inv_pass,
                        "lemon_user":   lm_user,
                        "lemon_pass":   lm_pass,
                        "sheet_id":     sheet_id,
                    }
                    if st.session_state.active_region is None:
                        st.session_state.active_region = new_name.strip()
                    st.success(f"✅ 已新增區域「{new_name.strip()}」")
                    st.rerun()

    # ── 已設定區域列表 ────────────────────────────────────────────────────────
    regions = get_regions()
    if not regions:
        st.info("尚未設定任何區域，請使用上方表單新增。")
        return

    st.markdown(f"**已設定 {len(regions)} 個區域**")
    st.markdown("---")

    for rname in regions:
        cfg = st.session_state.region_config[rname]
        with st.expander(f"📍 {rname}", expanded=False):
            col_info, col_del = st.columns([4, 1])

            with col_info:
                rows = [
                    {"項目": "發票系統帳號", "值": cfg.get("invoice_user") or "（未填）",
                     "狀態": "✅" if cfg.get("invoice_user") else "❌"},
                    {"項目": "發票系統密碼", "值": "●●●●●●" if cfg.get("invoice_pass") else "（未填）",
                     "狀態": "✅" if cfg.get("invoice_pass") else "❌"},
                    {"項目": "檸檬家事帳號", "值": cfg.get("lemon_user") or "（未填）",
                     "狀態": "✅" if cfg.get("lemon_user") else "❌"},
                    {"項目": "檸檬家事密碼", "值": "●●●●●●" if cfg.get("lemon_pass") else "（未填）",
                     "狀態": "✅" if cfg.get("lemon_pass") else "❌"},
                    {"項目": "帳務處理表 ID", "值": cfg.get("sheet_id") or "（未填）",
                     "狀態": "✅" if cfg.get("sheet_id") else "❌"},
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            with col_del:
                if st.button("🗑 刪除", key=f"del_{rname}"):
                    del st.session_state.region_config[rname]
                    if st.session_state.active_region == rname:
                        remaining = get_regions()
                        st.session_state.active_region = remaining[0] if remaining else None
                    st.rerun()

    st.markdown("---")
    st.subheader("secrets.toml 永久保存範本")
    st.warning("以上設定重新整理後會消失。如需永久保存，請將帳密填入 .streamlit/secrets.toml：")
    example_lines = []
    for rname, cfg in st.session_state.region_config.items():
        key = rname.upper().replace(" ", "_")
        example_lines.append(f"# {rname}")
        example_lines.append(f'INV_USER_{key}  = "{cfg.get("invoice_user","")}"')
        example_lines.append(f'INV_PASS_{key}  = "{cfg.get("invoice_pass","") and "your_password"}"')
        example_lines.append(f'LM_USER_{key}   = "{cfg.get("lemon_user","")}"')
        example_lines.append(f'LM_PASS_{key}   = "{cfg.get("lemon_pass","") and "your_password"}"')
        example_lines.append(f'SHEET_ID_{key}  = "{cfg.get("sheet_id","")}"')
        example_lines.append("")
    st.code("\n".join(example_lines), language="toml")


# ── 路由 ──────────────────────────────────────────────────────────────────────
tab = st.session_state.active_tab

if tab == "首頁":
    page_home()
elif tab == "開立發票":
    page_issue_invoice()
elif tab == "開立折讓單":
    page_allowance()
elif tab == "下載發票":
    page_export_invoices(False)
elif tab == "下載紙本發票":
    page_export_invoices(True)
elif tab == "設定":
    page_settings()
