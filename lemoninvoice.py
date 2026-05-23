"""
檸檬家事發票系統 - Streamlit App
UI: 上方導覽列 + 執行日期區間 + 執行項目 + 執行區域
後端: 各區帳務處理表（Google Sheets）→ 發票系統 API（待串接）
"""

import os
from datetime import date, timedelta
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

# ── 自訂 CSS：上方導覽列風格 ──────────────────────────────────────────────────
st.markdown(
    """
<style>
/* 隱藏預設 sidebar toggle & header padding */
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
.block-container { padding-top: 0.5rem !important; }

/* 頂部 Logo 列 */
.top-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 0 4px 0;
    font-size: 18px;
    font-weight: 600;
    color: #0F6E56;
    border-bottom: 1px solid #e8e8e8;
    margin-bottom: 0.5rem;
}

/* 篩選工具列 */
.filter-bar {
    background: #f8f9fa;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 1.2rem;
}

/* 指標卡片 */
.metric-row {
    display: flex;
    gap: 12px;
    margin-bottom: 1.2rem;
}
.metric-card {
    flex: 1;
    background: #f3faf7;
    border-radius: 8px;
    padding: 14px 16px;
}
.metric-card.danger { background: #fff2f2; }
.metric-label { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.metric-value { font-size: 24px; font-weight: 600; color: #111; }
.metric-value.danger { color: #dc2626; }
.metric-sub { font-size: 11px; color: #9ca3af; margin-top: 2px; }

/* 地區按鈕群組 */
div[data-testid="stHorizontalBlock"] button {
    border-radius: 6px !important;
}

/* 狀態徽章 */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}
.badge-success { background: #d1fae5; color: #065f46; }
.badge-warn    { background: #fef3c7; color: #92400e; }
.badge-gray    { background: #f3f4f6; color: #6b7280; }
.badge-danger  { background: #fee2e2; color: #991b1b; }
</style>
""",
    unsafe_allow_html=True,
)

# ── 常數設定 ──────────────────────────────────────────────────────────────────
REGIONS = ["台北", "台中", "桃園", "新竹", "高雄"]

ACTION_TYPES = ["開立發票", "開立折讓單", "全部"]

# 各區設定（實際帳密請放 Streamlit Secrets 或環境變數）
REGION_CONFIG: dict[str, dict] = {
    "台北": {
        "invoice_user": os.getenv("INV_USER_TP", ""),
        "invoice_pass": os.getenv("INV_PASS_TP", ""),
        "lemon_user":   os.getenv("LM_USER_TP", ""),
        "lemon_pass":   os.getenv("LM_PASS_TP", ""),
        "sheet_id":     os.getenv("SHEET_ID_TP", ""),   # 帳務處理表 ID
    },
    "台中": {
        "invoice_user": os.getenv("INV_USER_TC", ""),
        "invoice_pass": os.getenv("INV_PASS_TC", ""),
        "lemon_user":   os.getenv("LM_USER_TC", ""),
        "lemon_pass":   os.getenv("LM_PASS_TC", ""),
        "sheet_id":     os.getenv("SHEET_ID_TC", ""),
    },
    "桃園": {
        "invoice_user": os.getenv("INV_USER_TY", ""),
        "invoice_pass": os.getenv("INV_PASS_TY", ""),
        "lemon_user":   os.getenv("LM_USER_TY", ""),
        "lemon_pass":   os.getenv("LM_PASS_TY", ""),
        "sheet_id":     os.getenv("SHEET_ID_TY", ""),
    },
    "新竹": {
        "invoice_user": os.getenv("INV_USER_HC", ""),
        "invoice_pass": os.getenv("INV_PASS_HC", ""),
        "lemon_user":   os.getenv("LM_USER_HC", ""),
        "lemon_pass":   os.getenv("LM_PASS_HC", ""),
        "sheet_id":     os.getenv("SHEET_ID_HC", ""),
    },
    "高雄": {
        "invoice_user": os.getenv("INV_USER_KH", ""),
        "invoice_pass": os.getenv("INV_PASS_KH", ""),
        "lemon_user":   os.getenv("LM_USER_KH", ""),
        "lemon_pass":   os.getenv("LM_PASS_KH", ""),
        "sheet_id":     os.getenv("SHEET_ID_KH", ""),
    },
}

# ── Session State 初始化 ──────────────────────────────────────────────────────
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "首頁"
if "active_region" not in st.session_state:
    st.session_state.active_region = "台北"
if "date_start" not in st.session_state:
    st.session_state.date_start = date.today().replace(day=1)
if "date_end" not in st.session_state:
    st.session_state.date_end = date.today()
if "action_type" not in st.session_state:
    st.session_state.action_type = "全部"
if "result_df" not in st.session_state:
    st.session_state.result_df = None

# ── 頂部 Logo ─────────────────────────────────────────────────────────────────
st.markdown('<div class="top-logo">🧾 檸檬家事發票系統</div>', unsafe_allow_html=True)

# ── 頂部導覽列（用 columns 模擬 tab bar）────────────────────────────────────────
TABS = ["首頁", "開立發票", "開立折讓單", "下載發票", "下載紙本發票", "設定"]
tab_cols = st.columns(len(TABS))
for i, (col, tab_name) in enumerate(zip(tab_cols, TABS)):
    with col:
        label = tab_name
        if tab_name == st.session_state.active_tab:
            label = f"**{tab_name}**"
        if st.button(label, key=f"tab_{i}", use_container_width=True):
            st.session_state.active_tab = tab_name
            st.rerun()

st.markdown("---")

# ── 篩選工具列（共用，只在非「設定」頁顯示）──────────────────────────────────
if st.session_state.active_tab != "設定":
    with st.container():
        col_d1, col_d2, col_sep1, col_act, col_sep2, col_reg, col_run = st.columns(
            [2, 2, 0.2, 2, 0.2, 5, 1.5]
        )

        with col_d1:
            d_start = st.date_input(
                "開始日期",
                value=st.session_state.date_start,
                key="filter_date_start",
                label_visibility="collapsed",
            )
            st.session_state.date_start = d_start

        with col_d2:
            d_end = st.date_input(
                "結束日期",
                value=st.session_state.date_end,
                key="filter_date_end",
                label_visibility="collapsed",
            )
            st.session_state.date_end = d_end

        with col_sep1:
            st.markdown("<div style='padding-top:8px;text-align:center;color:#9ca3af'>～</div>", unsafe_allow_html=True)

        with col_act:
            action = st.selectbox(
                "執行項目",
                ACTION_TYPES,
                index=ACTION_TYPES.index(st.session_state.action_type),
                key="filter_action",
                label_visibility="collapsed",
            )
            st.session_state.action_type = action

        with col_sep2:
            st.markdown("")

        # 地區按鈕
        with col_reg:
            reg_cols = st.columns(len(REGIONS))
            for rc, rname in zip(reg_cols, REGIONS):
                with rc:
                    is_active = st.session_state.active_region == rname
                    btn_label = f"**{rname}**" if is_active else rname
                    if st.button(btn_label, key=f"reg_{rname}", use_container_width=True):
                        st.session_state.active_region = rname
                        st.session_state.result_df = None
                        st.rerun()

        with col_run:
            run_clicked = st.button("▶ 執行", type="primary", use_container_width=True)

    st.markdown("---")

# ── 工具函式 ──────────────────────────────────────────────────────────────────
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="invoices")
    return output.getvalue()


def status_badge(status: str) -> str:
    mapping = {
        "已開立": "badge-success",
        "待開立": "badge-warn",
        "已回填": "badge-gray",
        "開票失敗": "badge-danger",
    }
    cls = mapping.get(status, "badge-gray")
    return f'<span class="badge {cls}">{status}</span>'


def make_order_id(raw_id: str) -> str:
    """訂單編號一律加 -1 後綴"""
    if raw_id and not raw_id.endswith("-1"):
        return raw_id + "-1"
    return raw_id


def calc_pretax(amount_with_tax: float, tax_rate: float = 0.05) -> float:
    """含稅金額回推未稅（折讓單使用）"""
    return round(amount_with_tax / (1 + tax_rate))


# ── 資料抓取佔位函式（待正式串接）─────────────────────────────────────────────
def fetch_pending_invoices(region: str, date_start: date, date_end: date) -> pd.DataFrame:
    """
    從各區帳務處理表取得待開發票訂單。
    實際需用 gspread 或 Google Sheets API 讀取 REGION_CONFIG[region]['sheet_id']。
    回傳欄位：訂單編號、客戶姓名、統編、抬頭、發票金額、狀態
    """
    # ---- 測試用假資料 ----
    return pd.DataFrame([
        {
            "原始訂單編號": "LC202605240001",
            "訂單編號":     make_order_id("LC202605240001"),
            "客戶姓名":     "王小明",
            "統編":         "",
            "抬頭":         "",
            "發票金額":     3000,
            "狀態":         "待開立",
            "發票號碼":     "",
        },
        {
            "原始訂單編號": "LC202605230042",
            "訂單編號":     make_order_id("LC202605230042"),
            "客戶姓名":     "範例公司",
            "統編":         "12345678",
            "抬頭":         "範例股份有限公司",
            "發票金額":     5250,
            "狀態":         "已開立",
            "發票號碼":     "AB12345678",
        },
    ])


def fetch_pending_allowances(region: str, date_start: date, date_end: date) -> pd.DataFrame:
    """
    從各區帳務處理表取得待開折讓單訂單。
    回傳欄位：訂單編號、發票號碼、折讓含稅金額、折讓未稅金額、狀態
    """
    # ---- 測試用假資料 ----
    return pd.DataFrame([
        {
            "原始訂單編號": "LC202605180009",
            "訂單編號":     make_order_id("LC202605180009"),
            "發票號碼":     "CD98765432",
            "折讓含稅金額": 1050,
            "折讓未稅金額": calc_pretax(1050),
            "折讓原因":     "部分退款",
            "狀態":         "待開立",
            "折讓單號":     "",
        },
    ])


# ── 各頁面 ────────────────────────────────────────────────────────────────────

# ┌─ 首頁 ─────────────────────────────────────────────────────────────────────
def page_home():
    region = st.session_state.active_region
    cfg = REGION_CONFIG[region]

    # 指標卡片（用 columns 模擬）
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("今日開票張數", "0", help="來自帳務處理表")
    c2.metric("今日開票金額", "$0")
    c3.metric("待開票訂單",   "0")
    c4.metric("開票失敗",     "0")

    st.divider()
    st.subheader(f"目前區域：{region}")

    env_ok = all([cfg["invoice_user"], cfg["invoice_pass"], cfg["sheet_id"]])
    if env_ok:
        st.success(f"✅ {region} 環境變數已設定，可以執行。")
    else:
        st.warning(f"⚠️ {region} 尚有環境變數未設定，請至「設定」頁面確認。")

    st.info("這是 MVP 介面。下一步接上帳務處理表（Google Sheets）與鯨躍／關網 SOAP API。")


# ┌─ 開立發票 ──────────────────────────────────────────────────────────────────
def page_issue_invoice():
    region = st.session_state.active_region
    st.subheader(f"開立發票｜{region}")

    if "run_clicked" in st.session_state and st.session_state.get("_run_issue"):
        with st.spinner("從帳務處理表讀取待開票訂單…"):
            df = fetch_pending_invoices(
                region,
                st.session_state.date_start,
                st.session_state.date_end,
            )
        st.session_state.result_df = df
        st.session_state._run_issue = False

    df = st.session_state.result_df
    if df is None:
        st.info("請設定篩選條件後按「▶ 執行」讀取待開票訂單。")
        return

    pending = df[df["狀態"] == "待開立"]
    st.markdown(f"共找到 **{len(pending)}** 筆待開票訂單")

    # 顯示表格（含 HTML 徽章）
    display_df = df[["訂單編號", "客戶姓名", "統編", "抬頭", "發票金額", "狀態", "發票號碼"]].copy()
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    if len(pending) > 0:
        col_run, col_dl = st.columns([2, 1])
        with col_run:
            if st.button("🧾 批次開立選取發票", type="primary"):
                st.info(
                    "正式串接後會依序：\n"
                    "1. 登入鯨躍／關網發票系統（各區帳密）\n"
                    "2. 登入檸檬家事（各區帳密）取得訂單資訊\n"
                    "3. 若有統編 → 填抬頭 + 統編 + 勾選含稅\n"
                    "4. 開立完成 → 回填發票號碼至帳務處理表"
                )
        with col_dl:
            st.download_button(
                "⬇ 匯出 Excel",
                data=to_excel_bytes(df),
                file_name=f"invoices_{region}_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# ┌─ 開立折讓單 ────────────────────────────────────────────────────────────────
def page_allowance():
    region = st.session_state.active_region
    st.subheader(f"開立折讓單｜{region}")

    df = st.session_state.result_df
    if df is None:
        st.info("請設定篩選條件後按「▶ 執行」讀取待開折讓單訂單。")
        return

    pending = df[df["狀態"] == "待開立"]
    st.markdown(f"共找到 **{len(pending)}** 筆待開折讓單訂單")

    display_df = df[["訂單編號", "發票號碼", "折讓含稅金額", "折讓未稅金額", "折讓原因", "狀態", "折讓單號"]].copy()
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    if len(pending) > 0:
        col_run, col_dl = st.columns([2, 1])
        with col_run:
            if st.button("📄 批次開立折讓單", type="primary"):
                st.info(
                    "正式串接後會依序：\n"
                    "1. 從帳務處理表取得發票號碼 + 折讓含稅金額\n"
                    "2. 回推未稅折讓金額（÷1.05）\n"
                    "3. 登入鯨躍／關網開立折讓單\n"
                    "4. 折讓單號碼回填帳務處理表"
                )
        with col_dl:
            st.download_button(
                "⬇ 匯出 Excel",
                data=to_excel_bytes(df),
                file_name=f"allowances_{region}_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# ┌─ 下載發票 ──────────────────────────────────────────────────────────────────
def page_export_invoices(paper_only: bool = False):
    title = "下載紙本發票" if paper_only else "下載發票"
    region = st.session_state.active_region
    st.subheader(f"{title}｜{region}")

    if st.button("查詢", type="secondary"):
        df = fetch_pending_invoices(
            region,
            st.session_state.date_start,
            st.session_state.date_end,
        )
        if paper_only:
            # 紙本：無載具（統編為空且未設電子載具）
            df = df[df["統編"] == ""]
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇ 下載 Excel",
            data=to_excel_bytes(df),
            file_name=("paper_invoices.xlsx" if paper_only else "invoices.xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ┌─ 設定 ──────────────────────────────────────────────────────────────────────
def page_settings():
    st.subheader("環境變數設定狀態")
    st.warning("請不要把帳密寫進 GitHub，請使用 Streamlit Secrets（secrets.toml）。")

    env_keys = [
        ("台北", ["INV_USER_TP", "INV_PASS_TP", "LM_USER_TP", "LM_PASS_TP", "SHEET_ID_TP"]),
        ("台中", ["INV_USER_TC", "INV_PASS_TC", "LM_USER_TC", "LM_PASS_TC", "SHEET_ID_TC"]),
        ("桃園", ["INV_USER_TY", "INV_PASS_TY", "LM_USER_TY", "LM_PASS_TY", "SHEET_ID_TY"]),
        ("新竹", ["INV_USER_HC", "INV_PASS_HC", "LM_USER_HC", "LM_PASS_HC", "SHEET_ID_HC"]),
        ("高雄", ["INV_USER_KH", "INV_PASS_KH", "LM_USER_KH", "LM_PASS_KH", "SHEET_ID_KH"]),
    ]

    rows = []
    for region_name, keys in env_keys:
        for k in keys:
            rows.append({
                "區域":     region_name,
                "變數名稱": k,
                "類型":     "發票系統" if k.startswith("INV") else ("帳務表" if k.startswith("SHEET") else "檸檬家事"),
                "狀態":     "✅ 已設定" if os.getenv(k) else "❌ 未設定",
            })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("secrets.toml 範本")
    st.code(
        """\
# .streamlit/secrets.toml

# 台北
INV_USER_TP  = "your_invoice_account"
INV_PASS_TP  = "your_invoice_password"
LM_USER_TP   = "your_lemon_account"
LM_PASS_TP   = "your_lemon_password"
SHEET_ID_TP  = "google_sheet_id_taipei"

# 台中（依此類推）
INV_USER_TC  = ""
INV_PASS_TC  = ""
LM_USER_TC   = ""
LM_PASS_TC   = ""
SHEET_ID_TC  = ""

# 桃園、新竹、高雄 ... 同上格式
""",
        language="toml",
    )


# ── 執行按鈕處理：依目前頁面決定抓哪種資料 ───────────────────────────────────
if st.session_state.active_tab != "設定" and "run_clicked" in dir():
    if run_clicked:
        region = st.session_state.active_region
        tab = st.session_state.active_tab
        with st.spinner(f"從帳務處理表讀取資料（{region}）…"):
            if tab in ("首頁", "開立發票", "下載發票", "下載紙本發票"):
                st.session_state.result_df = fetch_pending_invoices(
                    region,
                    st.session_state.date_start,
                    st.session_state.date_end,
                )
            elif tab == "開立折讓單":
                st.session_state.result_df = fetch_pending_allowances(
                    region,
                    st.session_state.date_start,
                    st.session_state.date_end,
                )

# ── 路由：依 active_tab 渲染對應頁面 ─────────────────────────────────────────
tab = st.session_state.active_tab

if tab == "首頁":
    page_home()
elif tab == "開立發票":
    page_issue_invoice()
elif tab == "開立折讓單":
    # 如果 result_df 是發票資料，換成折讓資料
    if st.session_state.result_df is not None and "折讓含稅金額" not in st.session_state.result_df.columns:
        st.session_state.result_df = None
    page_allowance()
elif tab == "下載發票":
    page_export_invoices(False)
elif tab == "下載紙本發票":
    page_export_invoices(True)
elif tab == "設定":
    page_settings()
