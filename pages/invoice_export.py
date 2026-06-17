"""
檸檬家事 - 發票資訊查詢與匯出
登入 backend 各區帳號，依服務日期起迄查詢訂單，匯出 Excel
"""

import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from datetime import date

# ── 設定 ──────────────────────────────────────────────────
BACKEND = "https://backend.lemonclean.com.tw"

# secrets.toml 格式：
# [backend]
# taipei_email    = "taipei@lemon.com"
# taipei_password = "xxxx"
# taoyuan_email   = "taoyuan@lemon.com"
# ...

REGION_KEYS = {
    "台北": ("taipei_email",    "taipei_password"),
    "桃園": ("taoyuan_email",   "taoyuan_password"),
    "新竹": ("hsinchu_email",   "hsinchu_password"),
    "台中": ("taichung_email",  "taichung_password"),
    "高雄": ("kaohsiung_email", "kaohsiung_password"),
}

INVOICE_TYPE_MAP  = {0: "二聯式", 1: "捐贈", 2: "電子載具", 3: "三聯式"}
CARRIER_TYPE_MAP  = {1: "會員載具", 2: "手機條碼", 3: "自然人憑證", 4: "捐贈"}
PAYWAY_MAP        = {1: "信用卡", 2: "ATM 轉帳", 3: "Line Pay / 其他", 4: "現場付款"}

# ── 頁面設定 ───────────────────────────────────────────────
st.set_page_config(page_title="檸檬家事 發票匯出", page_icon="🍋", layout="wide")

st.markdown("""
<style>
    .section-title { font-size:.9rem; font-weight:700; color:#555;
                     border-bottom:1px solid #eee; padding-bottom:4px; margin:16px 0 10px; }
    .stat-box  { background:#f7f9fc; border-radius:8px; padding:12px 16px;
                 border-left:4px solid #FFD700; margin-bottom:8px; }
    .stat-num  { font-size:1.4rem; font-weight:700; color:#1a1a1a; }
    .stat-label{ font-size:.8rem; color:#888; }
</style>
""", unsafe_allow_html=True)

st.title("🍋 發票資訊查詢與匯出")
st.caption("登入各區 backend 帳號，依服務日期起迄查詢，匯出 Excel。")


# ── 工具函式 ───────────────────────────────────────────────
def get_credentials(region: str):
    """從 secrets 取帳密"""
    ek, pk = REGION_KEYS[region]
    try:
        email    = st.secrets["backend"][ek]
        password = st.secrets["backend"][pk]
        return email, password
    except Exception:
        return None, None


def backend_login(region: str) -> requests.Session | None:
    """登入 backend，回傳帶 session cookie 的 requests.Session"""
    email, password = get_credentials(region)
    if not email:
        st.error(f"❌ {region}：secrets.toml 未設定帳密（backend.{REGION_KEYS[region][0]}）")
        return None

    sess = requests.Session()
    try:
        # 先取 CSRF token
        r = sess.get(f"{BACKEND}/login", timeout=10)
        # Laravel 用 _token（hidden input）
        from html.parser import HTMLParser
        class TokenParser(HTMLParser):
            token = ""
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "input" and attrs.get("name") == "_token":
                    self.token = attrs.get("value", "")
        p = TokenParser()
        p.feed(r.text)
        csrf = p.token

        resp = sess.post(
            f"{BACKEND}/login",
            data={"email": email, "password": password, "_token": csrf},
            timeout=15,
            allow_redirects=True,
        )
        # 登入成功會跳轉到 /，失敗仍在 /login
        if "/login" in resp.url:
            st.error(f"❌ {region}：帳號或密碼錯誤")
            return None
        return sess
    except Exception as e:
        st.error(f"❌ {region} 登入失敗：{e}")
        return None


def fetch_purchases(sess: requests.Session, date_s: str, date_e: str) -> list:
    """查詢訂單清單（JSON）"""
    try:
        resp = sess.get(
            f"{BACKEND}/purchase",
            params={
                "clean_date_s": date_s,
                "clean_date_e": date_e,
                "purchase_status": 1,   # 已付款
                "format": "json",       # 若 backend 支援
            },
            timeout=30,
        )
        # backend 回傳 HTML（非 JSON API），需解析 HTML table
        # 改用 export_order endpoint 直接拿資料
        return []
    except Exception as e:
        st.error(f"查詢失敗：{e}")
        return []


def fetch_export(sess: requests.Session, date_s: str, date_e: str) -> pd.DataFrame | None:
    """
    呼叫 /purchase/export_order 取得 Excel，解析成 DataFrame
    """
    try:
        resp = sess.post(
            f"{BACKEND}/purchase/export_order",
            data={"clean_date_s": date_s, "clean_date_e": date_e},
            timeout=60,
        )
        if resp.status_code != 200:
            st.error(f"export_order 回傳 {resp.status_code}")
            return None
        content_type = resp.headers.get("Content-Type", "")
        if "spreadsheet" in content_type or "excel" in content_type or "octet" in content_type:
            df = pd.read_excel(BytesIO(resp.content))
            return df
        else:
            st.error(f"未預期的回應格式：{content_type[:80]}")
            return None
    except Exception as e:
        st.error(f"匯出失敗：{e}")
        return None


def get_invoice_display(row) -> tuple:
    inv_type = int(row.get("invoice_type") or 0)
    type_str = INVOICE_TYPE_MAP.get(inv_type, "—")
    if inv_type == 3:
        title   = f"{row.get('company_title','')}／{row.get('company_no','')}"
        carrier = ""
    elif inv_type == 2:
        title = row.get("name", "")
        ct = int(row.get("carrier_type_id") or 0)
        if ct == 1:
            carrier = f"會員載具（{row.get('email','')}）"
        elif ct in (2, 3):
            carrier = f"{CARRIER_TYPE_MAP.get(ct,'')}（{row.get('carrier_info','')}）"
        else:
            carrier = CARRIER_TYPE_MAP.get(ct, "")
    elif inv_type == 1:
        title   = row.get("name", "")
        carrier = f"捐贈碼：{row.get('donate_code','')}"
    else:
        title   = row.get("name", "")
        carrier = ""
    return type_str, title, carrier


def rows_to_invoice_df(raw_df: pd.DataFrame, region: str) -> pd.DataFrame:
    """
    將 backend export Excel 的欄位轉換成發票所需欄位
    backend export 欄位參考 PurchaseService::exportOrder()
    """
    records = []
    for _, row in raw_df.iterrows():
        row = row.where(pd.notna(row), other="")
        inv_type_str, inv_title, carrier_str = get_invoice_display(row)
        records.append({
            "地區":           region,
            "服務日期":       row.get("服務日期", ""),
            "服務時段":       row.get("服務時間", ""),
            "訂單編號":       row.get("訂單編號", ""),
            "訂購人":         row.get("客戶姓名", ""),
            "統編":           row.get("company_no", ""),
            "電話":           row.get("聯絡電話", ""),
            "Mail":           row.get("EMAIL", ""),
            "地址":           row.get("客戶地址", ""),
            "發票類型":       inv_type_str,
            "發票抬頭／統編": inv_title,
            "載具":           carrier_str,
            "發票號碼":       row.get("發票號碼", ""),
            "開立日期":       row.get("付款日期", ""),
            "開立金額":       row.get("服務金額", ""),
        })
    return pd.DataFrame(records)


def to_excel_bytes(region_dfs: dict) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        all_df = pd.concat(region_dfs.values(), ignore_index=True) if region_dfs else pd.DataFrame()
        all_df.to_excel(writer, sheet_name="全部", index=False)
        for region, df in region_dfs.items():
            df.to_excel(writer, sheet_name=region, index=False)
    return buf.getvalue()


# ── 查詢條件 ───────────────────────────────────────────────
st.markdown('<div class="section-title">🔍 查詢條件</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
with c1:
    date_s = st.date_input("服務日期（起）", value=date.today().replace(day=1))
with c2:
    date_e = st.date_input("服務日期（迄）", value=date.today())
with c3:
    all_regions = list(REGION_KEYS.keys())
    selected = st.multiselect("地區", all_regions, default=all_regions)
with c4:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    search_btn = st.button("🔍 查詢", type="primary", use_container_width=True)

if date_s > date_e:
    st.warning("起始日期不能晚於結束日期。")
    st.stop()

# ── 執行查詢 ───────────────────────────────────────────────
if search_btn:
    if not selected:
        st.warning("請至少選擇一個地區。")
        st.stop()

    date_s_str = date_s.strftime("%Y-%m-%d")
    date_e_str = date_e.strftime("%Y-%m-%d")
    region_dfs = {}

    progress = st.progress(0, text="開始查詢…")
    for i, region in enumerate(selected):
        progress.progress((i) / len(selected), text=f"登入 {region}…")
        sess = backend_login(region)
        if sess is None:
            continue

        progress.progress((i + 0.5) / len(selected), text=f"查詢 {region} 訂單…")
        raw_df = fetch_export(sess, date_s_str, date_e_str)
        if raw_df is None or raw_df.empty:
            st.warning(f"⚠️ {region}：查無資料或匯出失敗")
            continue

        inv_df = rows_to_invoice_df(raw_df, region)
        region_dfs[region] = inv_df
        progress.progress((i + 1) / len(selected), text=f"{region} 完成（{len(inv_df)} 筆）")

    progress.empty()

    if not region_dfs:
        st.error("所有地區查詢均失敗。")
        st.stop()

    st.session_state.region_dfs   = region_dfs
    st.session_state.query_label  = f"{date_s_str} ～ {date_e_str}"

# ── 顯示結果 ───────────────────────────────────────────────
if "region_dfs" not in st.session_state:
    st.stop()

region_dfs = st.session_state.region_dfs
label      = st.session_state.query_label
all_df     = pd.concat(region_dfs.values(), ignore_index=True)

st.markdown(f'<div class="section-title">📊 查詢結果｜{label}</div>', unsafe_allow_html=True)

# 統計卡
stat_cols = st.columns(len(region_dfs) + 1)
with stat_cols[0]:
    st.markdown(
        f'<div class="stat-box"><div class="stat-num">{len(all_df)}</div>'
        f'<div class="stat-label">全部筆數</div></div>', unsafe_allow_html=True)
for i, (r, df) in enumerate(region_dfs.items()):
    with stat_cols[i + 1]:
        amt = pd.to_numeric(df["開立金額"], errors="coerce").sum()
        st.markdown(
            f'<div class="stat-box"><div class="stat-num">{len(df)}</div>'
            f'<div class="stat-label">{r}｜NT$ {int(amt):,}</div></div>',
            unsafe_allow_html=True)

# 分頁顯示
display_cols = ["服務日期", "服務時段", "訂單編號", "訂購人", "統編",
                "電話", "Mail", "地址", "發票類型", "發票抬頭／統編",
                "載具", "發票號碼", "開立日期", "開立金額"]

tabs = st.tabs(["全部"] + list(region_dfs.keys()))
with tabs[0]:
    st.dataframe(all_df[display_cols], use_container_width=True, hide_index=True)
for i, (r, df) in enumerate(region_dfs.items()):
    with tabs[i + 1]:
        total = pd.to_numeric(df["開立金額"], errors="coerce").sum()
        st.caption(f"共 {len(df)} 筆，合計 NT$ {int(total):,}")
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

# ── 匯出 ───────────────────────────────────────────────────
st.markdown("---")
ex1, ex2 = st.columns([1, 3])
with ex1:
    excel_bytes = to_excel_bytes(region_dfs)
    st.download_button(
        label="📥 匯出 Excel",
        data=excel_bytes,
        file_name=f"invoice_{label.replace(' ','').replace('～','_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
with ex2:
    st.caption("Excel 包含「全部」sheet 及各地區獨立 sheet，欄位：服務日期、時段、訂單編號、發票類型、抬頭統編、載具、開立金額等。")
