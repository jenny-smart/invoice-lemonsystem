from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Dict, List
from xml.sax.saxutils import escape
import hashlib
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="檸檬家事發票系統",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
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
""", unsafe_allow_html=True)

DEFAULT_REGIONS = ["台北", "台中", "桃園", "新竹", "高雄"]
TABS = ["首頁", "開立發票", "發票下載", "開立折讓單", "藍新金流", "下載檔案", "設定"]

def default_region_config() -> Dict[str, Dict[str, str]]:
    return {
        region: {
            "invoice_wsdl": "https://www.ei.com.tw/InvoiceB2C/InvoiceAPI?wsdl",
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
        for region in DEFAULT_REGIONS
    }

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

def calc_pretax(amount_with_tax: float, tax_rate: float = 0.05) -> int:
    if amount_with_tax is None:
        return 0
    return round(float(amount_with_tax) / (1 + tax_rate))

def calc_tax(amount_with_tax: float, tax_rate: float = 0.05) -> int:
    return int(round(float(amount_with_tax) - calc_pretax(amount_with_tax, tax_rate)))

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

def sample_accounting_rows(region: str) -> pd.DataFrame:
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

    defaults = {
        "B欄狀態": "",
        "G欄訂單編號": "",
        "發票金額": 0,
        "發票號碼": "",
        "折讓含稅金額": 0,
        "退款原因": "",
        "回填結果": "",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    return df

def read_accounting_rows(region: str, cfg: Dict[str, str], date_start: date, date_end: date, dry_run: bool = True) -> pd.DataFrame:
    if dry_run:
        return normalize_accounting_dataframe(sample_accounting_rows(region), region)

    raise NotImplementedError("Google Sheets 讀取尚未接上 service account。")

def filter_invoice_rows(accounting_df: pd.DataFrame) -> pd.DataFrame:
    return accounting_df[
        accounting_df["B欄狀態"].astype(str).str.strip().eq("待收款")
    ].reset_index(drop=True)

def filter_allowance_rows(accounting_df: pd.DataFrame) -> pd.DataFrame:
    return accounting_df[
        accounting_df["B欄狀態"].astype(str).str.strip().eq("待退款")
    ].reset_index(drop=True)

def write_invoice_result(region: str, cfg: Dict[str, str], row_number: int, result: Dict[str, object], dry_run: bool = True) -> None:
    if dry_run:
        add_log(f"DRY RUN：{region} 第 {row_number} 列回填發票號碼 {result.get('invoice_no', '')}")
        return
    raise NotImplementedError("Google Sheets 回填尚未接上 service account。")

def write_allowance_result(region: str, cfg: Dict[str, str], row_number: int, result: Dict[str, object], dry_run: bool = True) -> None:
    if dry_run:
        add_log(f"DRY RUN：{region} 第 {row_number} 列回填折讓單號 {result.get('allowance_no', '')}")
        return
    raise NotImplementedError("Google Sheets 回填尚未接上 service account。")

def fetch_order_detail_from_lemonclean(region: str, order_id: str, cfg: Dict[str, str], dry_run: bool = True) -> Dict[str, str]:
    if dry_run:
        if order_id.endswith("41001-1"):
            return {
                "訂單編號": order_id,
                "客戶姓名": "張嘉芸",
                "抬頭": "範例股份有限公司",
                "統編": "12345678",
                "電話": "0912345678",
                "地址": "台北市範例區範例路 1 號",
                "Email": "example@company.com",
                "服務名稱": "清潔服務",
                "服務類型代碼": "1",
            }
        return {
            "訂單編號": order_id,
            "客戶姓名": "一般客戶",
            "抬頭": "",
            "統編": "",
            "電話": "0912345678",
            "地址": "台北市範例區檸檬路 1 號",
            "Email": "customer@example.com",
            "服務名稱": "清潔服務",
            "服務類型代碼": "1",
        }
    raise NotImplementedError("檸檬家事登入讀取尚未接上正式 endpoint。")

class InvoiceService:
    def __init__(self, cfg: Dict[str, str], dry_run: bool = True):
        self.cfg = cfg
        self.dry_run = dry_run

    def _wsdl(self) -> str:
        return self.cfg.get("invoice_wsdl") or "https://www.ei.com.tw/InvoiceB2C/InvoiceAPI?wsdl"

    def _rent_id(self) -> str:
        rent_id = self.cfg.get("invoice_rent_id")
        if not rent_id:
            raise ValueError("Missing invoice_rent_id / RentID")
        return rent_id

    def build_invoice_xml(self, payload: Dict[str, object]) -> str:
        product = (
            "<ProductItem>"
            f"<ProductionCode>{escape(str(payload.get('production_code', '1')))}</ProductionCode>"
            f"<Description>{escape(str(payload.get('description', '清潔服務')))}</Description>"
            "<Quantity>1</Quantity>"
            "<Unit>次</Unit>"
            f"<UnitPrice>{int(payload.get('unit_price', 0))}</UnitPrice>"
            "</ProductItem>"
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Invoice XSDVersion="2.8">'
            f"<OrderId>{escape(str(payload['order_id']))}</OrderId>"
            f"<OrderDate>{escape(str(payload.get('order_date', '')))}</OrderDate>"
            f"<BuyerIdentifier>{escape(str(payload.get('buyer_identifier', '')))}</BuyerIdentifier>"
            f"<BuyerName>{escape(str(payload.get('buyer_name', '')))}</BuyerName>"
            f"<BuyerAddress>{escape(str(payload.get('buyer_address', '')))}</BuyerAddress>"
            f"<BuyerEmailAddress>{escape(str(payload.get('buyer_email', '')))}</BuyerEmailAddress>"
            f"<DonateMark>{int(payload.get('donate_mark', 0))}</DonateMark>"
            "<InvoiceType>07</InvoiceType>"
            f"<CarrierType>{escape(str(payload.get('carrier_type', '')))}</CarrierType>"
            f"<CarrierId1>{escape(str(payload.get('carrier_id1', '')))}</CarrierId1>"
            f"<CarrierId2>{escape(str(payload.get('carrier_id2', '')))}</CarrierId2>"
            f"<NPOBAN>{escape(str(payload.get('npoban', '')))}</NPOBAN>"
            f"<TaxType>{int(payload.get('tax_type', 1))}</TaxType>"
            f"<TaxRate>{payload.get('tax_rate', 0.05)}</TaxRate>"
            f"<PayWay>{int(payload.get('pay_way', 3))}</PayWay>"
            "<Remark></Remark>"
            f"<Details>{product}</Details>"
            "</Invoice>"
        )

    def create_invoice(self, payload: Dict[str, object]) -> Dict[str, object]:
        xml = self.build_invoice_xml(payload)
        params = {"invoicexml": xml, "hastax": 1, "rentid": self._rent_id()}

        if self.dry_run:
            fake_no = "T" + hashlib.sha1(str(payload["order_id"]).encode("utf-8")).hexdigest()[:9].upper()
            return {
                "success": True,
                "invoice_no": fake_no[:10],
                "message": "DRY RUN：已建立 CreateInvoiceV3 payload，未送出",
                "method": "CreateInvoiceV3",
                "params": params,
            }

        from zeep import Client
        client = Client(self._wsdl())
        result = client.service.CreateInvoiceV3(**params)
        raw = str(getattr(result, "return", result))
        return {
            "success": len(raw) == 10,
            "invoice_no": raw if len(raw) == 10 else "",
            "message": "發票開立成功" if len(raw) == 10 else f"發票開立失敗：{raw}",
            "raw": raw,
        }

    def query_invoice_number(self, order_id: str) -> Dict[str, object]:
        params = {"orderid": order_id, "rentid": self._rent_id()}

        if self.dry_run:
            fake_no = "Q" + hashlib.sha1(order_id.encode("utf-8")).hexdigest()[:9].upper()
            return {
                "success": True,
                "invoice_no": fake_no[:10],
                "message": "DRY RUN：已建立 QueryInvoiceNumberByOrderid payload，未送出",
                "method": "QueryInvoiceNumberByOrderid",
                "params": params,
            }

        from zeep import Client
        client = Client(self._wsdl())
        result = client.service.QueryInvoiceNumberByOrderid(**params)
        raw = str(getattr(result, "return", result))
        return {
            "success": len(raw) == 10,
            "invoice_no": raw if len(raw) == 10 else "",
            "message": "查詢成功" if len(raw) == 10 else f"查詢失敗：{raw}",
            "raw": raw,
        }

    def create_allowance(self, payload: Dict[str, object]) -> Dict[str, object]:
        params = {
            "allowancexml": f"<Allowance><OrderId>{escape(str(payload['order_id']))}</OrderId></Allowance>",
            "rentid": self._rent_id(),
        }

        if self.dry_run:
            fake_no = "AL" + hashlib.sha1((payload["order_id"] + payload["invoice_no"]).encode("utf-8")).hexdigest()[:8].upper()
            return {
                "success": True,
                "allowance_no": fake_no[:10],
                "message": "DRY RUN：已建立折讓單 payload，未送出；正式 method 需依鯨躍規格確認",
                "params": params,
            }

        raise NotImplementedError("折讓單 SOAP method 未在現有 Laravel 程式中找到，需先向鯨躍確認正式 method 與 XML 規格。")

class NewebPayService:
    def __init__(self, cfg: Dict[str, str], dry_run: bool = True):
        self.cfg = cfg
        self.dry_run = dry_run

    def cancel_credit_card(self, merchant_order_no: str, amount: int) -> Dict[str, object]:
        merchant_id = self.cfg.get("newebpay_merchant_id", "")
        if not merchant_id:
            return {"success": False, "message": "缺少藍新 MerchantID"}

        if self.dry_run:
            return {
                "success": True,
                "message": "DRY RUN：已建立藍新 CreditCard/Cancel payload，未送出",
                "merchant_order_no": merchant_order_no,
                "amount": amount,
            }

        return {"success": False, "message": "正式藍新流程尚未啟用。"}

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
        st.session_state.active_region = st.selectbox("執行區域", regions, index=regions.index(st.session_state.active_region), label_visibility="collapsed")
    with c4:
        st.session_state.dry_run = st.toggle("測試模式，不真正送出", value=st.session_state.dry_run)
    with c5:
        clicked = st.button("▶ 讀取帳務表", type="primary", use_container_width=True)
    st.markdown("---")
    return clicked

def load_and_split_accounting_rows(region: str, cfg: Dict[str, str]) -> None:
    accounting_df = read_accounting_rows(region, cfg, st.session_state.date_start, st.session_state.date_end, dry_run=st.session_state.dry_run)
    st.session_state.accounting_df = accounting_df
    st.session_state.invoice_df = filter_invoice_rows(accounting_df)
    st.session_state.allowance_df = filter_allowance_rows(accounting_df)
    add_log(f"已讀取 {region} 帳務工作表：待收款 {len(st.session_state.invoice_df)} 筆，待退款 {len(st.session_state.allowance_df)} 筆")

def page_home() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("目前區域", region)
    c2.metric("來源", "同一張帳務工作表")
    c3.metric("發票判斷", "B欄=待收款")
    c4.metric("折讓判斷", "B欄=待退款")
    st.subheader("新版判斷規則")
    st.markdown("""
- 同一張帳務處理表。
- **B 欄狀態 = 待收款**：開立發票。
- **B 欄狀態 = 待退款**：開立折讓單。
- **G 欄訂單編號**：用來登入檸檬官網查詢訂單資料。
- 系統使用的訂單編號會自動轉成：`G欄訂單編號-1`。
- 開立完成後，只回填同一張帳務處理表，不回寫檸檬家事後台。
""")
    rows = [
        {"項目": "發票 RentID", "狀態": "✅" if cfg.get("invoice_rent_id") else "❌"},
        {"項目": "檸檬家事帳號", "狀態": "✅" if cfg.get("lemon_user") else "❌"},
        {"項目": "檸檬家事密碼", "狀態": "✅" if cfg.get("lemon_pass") else "❌"},
        {"項目": "帳務處理表 ID", "狀態": "✅" if cfg.get("sheet_id") else "❌"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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
        enriched_rows.append({**row.to_dict(), **order, "發票姓名欄": payload["buyer_name"], "是否含稅": "是" if payload["is_tax_included"] else "否"})
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
            results.append({"列號": row["列號"], "G欄訂單編號": row["G欄訂單編號"], "訂單編號_系統": row["訂單編號_系統"], "發票金額": row["發票金額"], "發票號碼": result.get("invoice_no", ""), "結果": result.get("message", "")})
        st.success("發票流程完成。")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

def page_invoice_download() -> None:
    region = st.session_state.active_region
    cfg = get_cfg(region)
    st.subheader(f"發票下載／查詢｜{region}")
    order_id = st.text_input("訂單編號，可留空改用帳務表資料")
    service = InvoiceService(cfg, dry_run=st.session_state.dry_run)
    if st.button("查詢單筆發票號碼"):
        if not order_id:
            st.warning("請輸入訂單編號。")
        else:
            st.json(service.query_invoice_number(normalized_order_id(order_id)))
    st.divider()
    df = st.session_state.invoice_df
    if df is None:
        st.info("按「▶ 讀取帳務表」後可批次查詢。")
        return
    if st.button("批次查詢發票號碼"):
        results = []
        for _, row in df.iterrows():
            oid = normalized_order_id(row["G欄訂單編號"])
            result = service.query_invoice_number(oid)
            results.append({"列號": row["列號"], "G欄訂單編號": row["G欄訂單編號"], "訂單編號_系統": oid, "發票號碼": result.get("invoice_no", ""), "結果": result.get("message", "")})
        out = pd.DataFrame(results)
        st.dataframe(out, use_container_width=True, hide_index=True)
        st.download_button("⬇ 下載查詢結果", data=to_excel_bytes(out, "發票查詢"), file_name=f"invoice_query_{region}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
            result = service.create_allowance({"order_id": row["訂單編號_系統"], "invoice_no": row["發票號碼"], "allowance_amount_with_tax": int(row["折讓含稅金額"]), "allowance_amount_pretax": int(row["折讓未稅金額"]), "allowance_tax": int(row["折讓稅額"]), "reason": row.get("退款原因", "退款折讓"), "allowance_date": date.today().strftime("%Y/%m/%d")})
            if result["success"]:
                write_allowance_result(region, cfg, int(row["列號"]), result, dry_run=st.session_state.dry_run)
            results.append({"列號": row["列號"], "G欄訂單編號": row["G欄訂單編號"], "訂單編號_系統": row["訂單編號_系統"], "發票號碼": row["發票號碼"], "折讓含稅金額": row["折讓含稅金額"], "折讓未稅金額": row["折讓未稅金額"], "折讓稅額": row["折讓稅額"], "折讓單號": result.get("allowance_no", ""), "結果": result.get("message", "")})
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
        st.json(service.cancel_credit_card(merchant_order_no, int(amount)))

def page_download_files() -> None:
    region = st.session_state.active_region
    st.subheader(f"下載檔案｜{region}")
    if st.session_state.accounting_df is not None:
        st.download_button("⬇ 下載完整帳務表讀取結果", data=to_excel_bytes(st.session_state.accounting_df, "帳務表"), file_name=f"accounting_rows_{region}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if st.session_state.invoice_df is not None:
        st.download_button("⬇ 下載待開發票資料（B欄待收款）", data=to_excel_bytes(st.session_state.invoice_df, "待開發票"), file_name=f"pending_invoices_{region}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if st.session_state.allowance_df is not None:
        st.download_button("⬇ 下載待開折讓單資料（B欄待退款）", data=to_excel_bytes(st.session_state.allowance_df, "待開折讓單"), file_name=f"pending_allowances_{region}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
                sheet_name_accounting = st.text_input("帳務工作表名稱", value=cfg.get("sheet_name_accounting", ""), placeholder="例如：清潔異動。可空白，空白時讀第一個工作表")
                st.markdown("**藍新金流**")
                c8, c9, c10 = st.columns(3)
                newebpay_merchant_id = c8.text_input("MerchantID", value=cfg.get("newebpay_merchant_id", ""))
                newebpay_hash_key = c9.text_input("HashKey", value=cfg.get("newebpay_hash_key", ""), type="password")
                newebpay_hash_iv = c10.text_input("HashIV", value=cfg.get("newebpay_hash_iv", ""), type="password")
                submitted = st.form_submit_button("儲存設定", type="primary", use_container_width=True)
                if submitted:
                    st.session_state.region_config[rname] = {**cfg, "invoice_rent_id": invoice_rent_id, "invoice_wsdl": invoice_wsdl, "lemon_user": lemon_user, "lemon_pass": lemon_pass, "sheet_id": sheet_id, "sheet_name_accounting": sheet_name_accounting, "newebpay_merchant_id": newebpay_merchant_id, "newebpay_hash_key": newebpay_hash_key, "newebpay_hash_iv": newebpay_hash_iv}
                    st.success(f"已儲存 {rname} 設定。")
                    st.rerun()
    st.divider()
    st.subheader("Secrets 範本")
    st.code("[regions.台北]\ninvoice_rent_id = \"\"\ninvoice_wsdl = \"https://www.ei.com.tw/InvoiceB2C/InvoiceAPI?wsdl\"\nlemon_user = \"\"\nlemon_pass = \"\"\nsheet_id = \"\"\nsheet_name_accounting = \"\"\nnewebpay_merchant_id = \"\"\nnewebpay_hash_key = \"\"\nnewebpay_hash_iv = \"\"\nnewebpay_cancel_url = \"https://core.spgateway.com/API/CreditCard/Cancel\"", language="toml")

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
