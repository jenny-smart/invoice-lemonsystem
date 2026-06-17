"""
檸檬家事 - 發票資訊查詢與匯出
依服務日期起迄 + 地區查詢，匯出 Excel
"""

import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from datetime import date, timedelta

# ── 設定 ──────────────────────────────────────────────────
API_BASE = st.secrets.get("LEMON_API_BASE", "https://api.lemonclean.com.tw")

# company_id 對應（3 = 新竹 or 高雄，由地址再判斷）
REGIONS = {
    "台北": 1,
    "桃園": 2,
    "新竹／高雄": 3,
    "台中": 4,
}

PAYWAY_MAP = {1: "信用卡", 2: "ATM 轉帳", 3: "Line Pay / 其他", 4: "現場付款"}

INVOICE_TYPE_MAP = {
    0: "二聯式",
    1: "捐贈",
    2: "電子載具",
    3: "三聯式",
}

CARRIER_TYPE_MAP = {
    1: "會員載具",
    2: "手機條碼",
    3: "自然人憑證",
    4: "捐贈",
}

# ── 頁面設定 ───────────────────────────────────────────────
st.set_page_config(page_title="檸檬家事 發票匯出", page_icon="🍋", layout="wide")

st.markdown("""
<style>
    .section-title { font-size:0.9rem; font-weight:700; color:#555;
                     border-bottom:1px solid #eee; padding-bottom:4px; margin:16px 0 10px; }
    .stat-box { background:#f7f9fc; border-radius:8px; padding:12px 16px;
                border-left:4px solid #FFD700; margin-bottom:8px; }
    .stat-num { font-size:1.4rem; font-weight:700; color:#1a1a1a; }
    .stat-label { font-size:0.8rem; color:#888; }
</style>
""", unsafe_allow_html=True)

st.title("🍋 發票資訊查詢與匯出")
st.caption("依服務日期起迄查詢各地區發票資料，支援分區匯出 Excel。")


# ── 工具函式 ───────────────────────────────────────────────
def is_hsinchu(address: str) -> bool:
    """company_id=3，地址含新竹縣/市 → 新竹"""
    return any(k in (address or "") for k in ["新竹縣", "新竹市"])


def is_kaohsiung(address: str) -> bool:
    """company_id=3，地址含高雄/台南 → 高雄"""
    return any(k in (address or "") for k in ["高雄縣", "高雄市", "台南縣", "台南市"])


def classify_region(row: dict) -> str:
    company_id = row.get("company_id", 0)
    if company_id == 1:
        return "台北"
    elif company_id == 2:
        return "桃園"
    elif company_id == 3:
        addr = row.get("address", "")
        if is_kaohsiung(addr):
            return "高雄"
        else:
            return "新竹"
    elif company_id == 4:
        return "台中"
    return "其他"


def get_invoice_display(row: dict) -> tuple[str, str, str]:
    """
    回傳 (發票類型顯示, 發票抬頭/統編, 載具資訊)
    """
    inv_type = row.get("invoice_type", 0)
    type_str = INVOICE_TYPE_MAP.get(inv_type, "—")

    if inv_type == 3:
        title = f"{row.get('company_title', '')}／{row.get('company_no', '')}"
        carrier = ""
    elif inv_type == 2:
        title = row.get("name", "")
        ct = row.get("carrier_type_id", 0)
        carrier_label = CARRIER_TYPE_MAP.get(ct, "")
        if ct == 1:  # 會員載具
            carrier = f"會員載具（{row.get('email', '')}）"
        elif ct in (2, 3):
            carrier = f"{carrier_label}（{row.get('carrier_info', '')}）"
        else:
            carrier = carrier_label
    elif inv_type == 1:
        title = row.get("name", "")
        carrier = f"捐贈碼：{row.get('donate_code', '')}"
    else:
        title = row.get("name", "")
        carrier = ""

    return type_str, title, carrier


def fetch_orders(company_id: int, date_s: str, date_e: str) -> list:
    try:
        resp = requests.post(
            f"{API_BASE}/orders_by_date",
            json={"company_id": company_id, "clean_date_s": date_s, "clean_date_e": date_e},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("return_code") == "0000":
            return data.get("data", [])
    except Exception as e:
        st.error(f"查詢失敗（company_id={company_id}）：{e}")
    return []


def rows_to_df(rows: list) -> pd.DataFrame:
    records = []
    for r in rows:
        inv_type_str, inv_title, carrier_str = get_invoice_display(r)
        records.append({
            "服務日期":       r.get("date_clean", ""),
            "服務時段":       f"{r.get('period_s', '')}–{r.get('period_e', '')}",
            "訂單編號":       r.get("order_no", ""),
            "訂購人":         r.get("name", ""),
            "統編":           r.get("company_no", ""),
            "電話":           r.get("phone", ""),
            "Mail":           r.get("email", ""),
            "地址":           r.get("address", ""),
            "發票類型":       inv_type_str,
            "發票抬頭／統編": inv_title,
            "載具":           carrier_str,
            "發票號碼":       r.get("invoice_no", ""),
            "開立日期":       r.get("created_at", "")[:10] if r.get("created_at") else "",
            "開立金額":       (r.get("total") or 0) - (r.get("fare") or 0),
            "地區":           classify_region(r),
        })
    return pd.DataFrame(records)


def to_excel(region_dfs: dict[str, pd.DataFrame]) -> bytes:
    """每個地區一個 sheet，另加一個全部 sheet"""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # 全部
        all_df = pd.concat(region_dfs.values(), ignore_index=True) if region_dfs else pd.DataFrame()
        all_df.to_excel(writer, sheet_name="全部", index=False)
        # 各地區
        for region, df in region_dfs.items():
            df.to_excel(writer, sheet_name=region, index=False)
    return buf.getvalue()


# ── 查詢條件 ───────────────────────────────────────────────
st.markdown('<div class="section-title">🔍 查詢條件</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
with col1:
    date_s = st.date_input("服務日期（起）", value=date.today().replace(day=1))
with col2:
    date_e = st.date_input("服務日期（迄）", value=date.today())
with col3:
    region_options = ["全部地區", "台北", "桃園", "新竹", "高雄", "台中"]
    selected_regions = st.multiselect("地區", region_options,
                                       default=["全部地區"],
                                       placeholder="選擇地區…")
with col4:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    search_btn = st.button("🔍 查詢", type="primary", use_container_width=True)

if date_s > date_e:
    st.warning("起始日期不能晚於結束日期。")
    st.stop()

# ── 查詢 ───────────────────────────────────────────────────
if search_btn:
    date_s_str = date_s.strftime("%Y-%m-%d")
    date_e_str = date_e.strftime("%Y-%m-%d")

    # 決定要查哪些 company_id
    # 新竹和高雄都是 company_id=3，一起查再依地址拆分
    need_company_ids = set()
    if "全部地區" in selected_regions or not selected_regions:
        need_company_ids = {1, 2, 3, 4}
    else:
        for r in selected_regions:
            if r in ("台北",):      need_company_ids.add(1)
            elif r in ("桃園",):    need_company_ids.add(2)
            elif r in ("新竹", "高雄"): need_company_ids.add(3)
            elif r in ("台中",):    need_company_ids.add(4)

    all_rows = []
    with st.spinner("查詢中…"):
        for cid in sorted(need_company_ids):
            rows = fetch_orders(cid, date_s_str, date_e_str)
            all_rows.extend(rows)

    if not all_rows:
        st.warning("查無資料。")
        st.stop()

    df_all = rows_to_df(all_rows)

    # 依地區篩選（若選全部就不過濾）
    if "全部地區" not in selected_regions and selected_regions:
        df_all = df_all[df_all["地區"].isin(selected_regions)]

    st.session_state.df_all = df_all
    st.session_state.query_label = f"{date_s_str} ～ {date_e_str}"

# ── 顯示結果 ───────────────────────────────────────────────
if "df_all" not in st.session_state:
    st.stop()

df_all = st.session_state.df_all
label  = st.session_state.query_label

st.markdown(f'<div class="section-title">📊 查詢結果｜{label}</div>', unsafe_allow_html=True)

# 統計卡
regions_in_data = ["台北", "桃園", "新竹", "高雄", "台中"]
stat_cols = st.columns(len(regions_in_data) + 1)
with stat_cols[0]:
    st.markdown(
        f'<div class="stat-box"><div class="stat-num">{len(df_all)}</div>'
        f'<div class="stat-label">全部筆數</div></div>', unsafe_allow_html=True)
for i, r in enumerate(regions_in_data):
    cnt = len(df_all[df_all["地區"] == r])
    with stat_cols[i + 1]:
        st.markdown(
            f'<div class="stat-box"><div class="stat-num">{cnt}</div>'
            f'<div class="stat-label">{r}</div></div>', unsafe_allow_html=True)

# 地區分頁顯示
tab_labels = ["全部"] + [r for r in regions_in_data if len(df_all[df_all["地區"] == r]) > 0]
tabs = st.tabs(tab_labels)

display_cols = ["服務日期", "服務時段", "訂單編號", "訂購人", "統編",
                "電話", "Mail", "地址", "發票類型", "發票抬頭／統編",
                "載具", "發票號碼", "開立日期", "開立金額"]

region_dfs = {}
with tabs[0]:
    st.dataframe(df_all[display_cols], use_container_width=True, hide_index=True)

for i, r in enumerate(tab_labels[1:], 1):
    rdf = df_all[df_all["地區"] == r][display_cols].reset_index(drop=True)
    region_dfs[r] = rdf
    with tabs[i]:
        total = rdf["開立金額"].sum()
        st.caption(f"共 {len(rdf)} 筆，合計 NT$ {total:,}")
        st.dataframe(rdf, use_container_width=True, hide_index=True)

# ── 匯出 Excel ────────────────────────────────────────────
st.markdown("---")
ex_col1, ex_col2 = st.columns([1, 3])
with ex_col1:
    excel_bytes = to_excel(region_dfs if region_dfs else {"全部": df_all[display_cols]})
    st.download_button(
        label="📥 匯出 Excel",
        data=excel_bytes,
        file_name=f"invoice_{label.replace(' ', '').replace('～', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
with ex_col2:
    st.caption("Excel 包含「全部」sheet 及各地區獨立 sheet。")
