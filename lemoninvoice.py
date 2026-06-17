"""
檸檬家事 - 發票開立查詢介面
從官網 API 查詢訂單資訊，整理後送至發票開立系統
"""

import streamlit as st
import requests

# ── 設定 ──────────────────────────────────────────
API_BASE = st.secrets.get("LEMON_API_BASE", "https://api.lemonclean.com.tw")
INVOICE_API_BASE = st.secrets.get("INVOICE_API_BASE", "https://www.ei.com.tw/InvoiceB2C/InvoiceAPI")

# 對應表
INVOICE_TYPE_MAP = {
    0: "二聯式（個人）",
    1: "捐贈發票",
    2: "電子載具",
    3: "三聯式（公司）",
}

CARRIER_TYPE_MAP = {
    1: "會員載具",
    2: "手機條碼",
    3: "自然人憑證",
    4: "捐贈（DonateMark=2）",
}

PAYWAY_MAP = {
    1: "信用卡",
    2: "ATM 轉帳",
    3: "Line Pay / 其他",
    4: "現場付款",
}

# ── 頁面設定 ──────────────────────────────────────
st.set_page_config(
    page_title="檸檬家事 發票開立",
    page_icon="🍋",
    layout="centered",
)

st.markdown("""
<style>
    .block-container { max-width: 760px; }
    .field-label { font-size: 0.82rem; color: #888; margin-bottom: 2px; }
    .field-value { font-size: 1rem; font-weight: 500; color: #1a1a1a; padding: 6px 10px;
                   background: #f7f9fc; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid #FFD700; }
    .section-title { font-size: 0.9rem; font-weight: 700; color: #555;
                     text-transform: uppercase; letter-spacing: 0.05em;
                     border-bottom: 1px solid #eee; padding-bottom: 4px; margin: 16px 0 10px; }
    .badge-2 { background: #e8f4fd; color: #1565c0; padding: 2px 10px; border-radius: 12px; font-size: 0.82rem; }
    .badge-3 { background: #fff3e0; color: #e65100; padding: 2px 10px; border-radius: 12px; font-size: 0.82rem; }
    .badge-donate { background: #f3e5f5; color: #6a1b9a; padding: 2px 10px; border-radius: 12px; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)

st.title("🍋 發票開立查詢")
st.caption("輸入發票號碼或訂單編號，從官網查詢訂單資訊並整理為發票開立所需欄位。")

# ── Step 1：查詢訂單 ───────────────────────────────
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    invoice_no_input = st.text_input(
        "發票號碼 / 訂單編號",
        placeholder="例：AA12345678 或 LC20240501001",
        help="輸入 10 碼發票號碼或訂單編號均可查詢"
    )
with col2:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    search_btn = st.button("🔍 查詢", use_container_width=True, type="primary")

def fetch_order(query: str) -> dict | None:
    """呼叫官網 API 查詢訂單"""
    try:
        resp = requests.post(
            f"{API_BASE}/order",
            json={"order_no": query},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("return_code") == "0000" and data.get("data"):
            return data["data"]
    except Exception as e:
        st.error(f"API 查詢失敗：{e}")
    return None


def field(label: str, value):
    """顯示單一欄位"""
    display = str(value) if value not in (None, "", 0) else "—"
    st.markdown(
        f'<div class="field-label">{label}</div>'
        f'<div class="field-value">{display}</div>',
        unsafe_allow_html=True,
    )


def build_invoice_payload(p: dict) -> dict:
    """
    依官網訂單資料，組出發票開立所需的欄位。
    完整依照 Invoice.php makeInvoice() 邏輯。
    """
    invoice_type = p.get("invoice_type", 0)
    carrier_type_id = p.get("carrier_type_id", 0)

    payload = {
        # 訂單
        "OrderId": f"{p.get('order_no', '')}-1",
        "OrderDate": p.get("created_at", "")[:10].replace("-", "/") if p.get("created_at") else "",
        # 買方
        "BuyerName": "",
        "BuyerIdentifier": "",
        "BuyerAddress": p.get("address", ""),
        "BuyerEmailAddress": p.get("email", ""),
        "BuyerTelephoneNumber": p.get("phone", ""),
        # 載具
        "CarrierType": "",
        "CarrierId1": "",
        "CarrierId2": "",
        # 捐贈
        "DonateMark": 0,
        "NPOBAN": "",
        # 付款
        "PayWay": 3,
        # 金額
        "UnitPrice": (p.get("total") or 0) - (p.get("fare") or 0),
        # 含稅
        "TaxType": 1,
        "TaxRate": 0.05,
        "HasTax": 1,
    }

    # ── 買方資訊 / 發票類型 ──
    if invoice_type == 1:          # 捐贈
        payload["BuyerName"] = p.get("name", "")
        payload["DonateMark"] = 1
        payload["NPOBAN"] = p.get("donate_code", "")

    elif invoice_type == 2:        # 電子載具
        payload["BuyerName"] = p.get("name", "")
        if carrier_type_id == 2:   # 手機條碼
            payload["CarrierType"] = "3J0002"
            payload["CarrierId1"] = p.get("carrier_info", "")
            payload["CarrierId2"] = p.get("carrier_info", "")
        elif carrier_type_id == 3: # 自然人憑證
            payload["CarrierType"] = "CQ0001"
            payload["CarrierId1"] = p.get("carrier_info", "")
            payload["CarrierId2"] = p.get("carrier_info", "")
        elif carrier_type_id == 1: # 會員載具 → CarrierId 填訂購人 email
            payload["CarrierType"] = ""
            payload["CarrierId1"] = p.get("email", "")
            payload["CarrierId2"] = p.get("email", "")
        elif carrier_type_id == 4: # 捐贈2
            payload["DonateMark"] = 2

    elif invoice_type == 3:        # 三聯式
        payload["BuyerIdentifier"] = p.get("company_no", "")
        payload["BuyerName"] = p.get("company_title", "")
        payload["DonateMark"] = 2
        payload["HasTax"] = 1      # 含稅必勾

    else:                          # 二聯式（個人）
        payload["BuyerName"] = p.get("name", "")

    # ── 付款方式 ──
    payway = p.get("payway", 0)
    if payway == 1:
        payload["PayWay"] = 3   # 信用卡
    elif payway == 2:
        payload["PayWay"] = 2   # ATM
    else:
        payload["PayWay"] = 3

    return payload


# ── 查詢結果 ──────────────────────────────────────
if search_btn and invoice_no_input.strip():
    query = invoice_no_input.strip()

    with st.spinner("查詢中…"):
        purchase = fetch_order(query)

    if purchase is None:
        st.warning("查無訂單，請確認號碼是否正確。")
        st.stop()

    # ── 訂單基本資訊 ──
    invoice_type = purchase.get("invoice_type", 0)
    carrier_type_id = purchase.get("carrier_type_id", 0)

    st.success(f"✅ 查詢成功：{purchase.get('order_no', '')}")

    st.markdown('<div class="section-title">📋 原始訂單資訊</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        field("訂單編號", purchase.get("order_no"))
        field("訂購人姓名", purchase.get("name"))
        field("電話", purchase.get("phone"))
        field("Email", purchase.get("email"))
    with c2:
        field("地址", purchase.get("address"))
        field("付款方式", PAYWAY_MAP.get(purchase.get("payway", 0), "—"))
        field("金額（含運）", f"NT$ {purchase.get('total', 0):,}")
        field("運費", f"NT$ {purchase.get('fare', 0):,}")

    # 發票類型標籤
    inv_label = INVOICE_TYPE_MAP.get(invoice_type, "—")
    badge_cls = "badge-3" if invoice_type == 3 else ("badge-donate" if invoice_type == 1 else "badge-2")
    st.markdown(
        f'<div class="section-title">🧾 發票類型 &nbsp; '
        f'<span class="{badge_cls}">{inv_label}</span></div>',
        unsafe_allow_html=True,
    )

    if invoice_type == 1:
        field("捐贈碼 NPOBAN", purchase.get("donate_code"))
    elif invoice_type == 2:
        field("載具類型", CARRIER_TYPE_MAP.get(carrier_type_id, "—"))
        if carrier_type_id in (2, 3):
            field("載具條碼", purchase.get("carrier_info"))
    elif invoice_type == 3:
        field("公司抬頭", purchase.get("company_title"))
        field("統一編號", purchase.get("company_no"))
        st.info("三聯式：含稅需勾選", icon="ℹ️")

    # ── 發票開立欄位 ──
    st.markdown('<div class="section-title">🖨️ 發票開立欄位（整理後）</div>', unsafe_allow_html=True)

    payload = build_invoice_payload(purchase)

    # 可供手動調整
    with st.expander("✏️ 確認 / 修改發票資料", expanded=True):
        p = payload  # shorthand
        
        col_a, col_b = st.columns(2)
        with col_a:
            p["OrderId"] = st.text_input("訂單編號（OrderId）", value=p["OrderId"])
            p["BuyerName"] = st.text_input("買方名稱", value=p["BuyerName"])
            p["BuyerIdentifier"] = st.text_input(
                "買方統編",
                value=p["BuyerIdentifier"],
                help="三聯式才需填入"
            )
            p["BuyerTelephoneNumber"] = st.text_input("買方電話", value=p["BuyerTelephoneNumber"])
        with col_b:
            p["BuyerAddress"] = st.text_input("買方地址", value=p["BuyerAddress"])
            p["BuyerEmailAddress"] = st.text_input("買方 Email", value=p["BuyerEmailAddress"])
            p["PayWay"] = st.selectbox(
                "付款方式（PayWay）",
                options=[2, 3],
                format_func=lambda x: "2 - ATM 轉帳" if x == 2 else "3 - 信用卡 / 其他",
                index=0 if p["PayWay"] == 2 else 1,
            )

        st.markdown("**發票方式**")
        inv_mode = st.radio(
            "發票方式",
            ["二聯式（個人）", "手機載具", "會員載具", "三聯式（公司）", "捐贈"],
            horizontal=True,
            index={"二聯式（個人）": 0, "手機載具": 1, "會員載具": 2, "三聯式（公司）": 3, "捐贈": 4}.get(
                {0: "二聯式（個人）", 1: "捐贈", 2: (
                    "手機載具" if carrier_type_id == 2 else "會員載具" if carrier_type_id == 1 else "二聯式（個人）"
                ), 3: "三聯式（公司）"}.get(invoice_type, "二聯式（個人）")
            , 0),
            label_visibility="collapsed",
        )

        # 依選擇調整 carrier
        if inv_mode == "手機載具":
            mobile_carrier = st.text_input(
                "手機條碼（輸入兩次確認）",
                value=p.get("CarrierId1", ""),
                placeholder="/XXXXXXX",
            )
            p["CarrierType"] = "3J0002"
            p["CarrierId1"] = mobile_carrier
            p["CarrierId2"] = mobile_carrier
            p["DonateMark"] = 0
            p["BuyerIdentifier"] = ""
        elif inv_mode == "會員載具":
            member_email = p.get("BuyerEmailAddress", "")
            st.info(f"會員載具：CarrierId 將帶入訂購人 Email：**{member_email}**", icon="📧")
            p["CarrierType"] = ""
            p["CarrierId1"] = member_email
            p["CarrierId2"] = member_email
            p["DonateMark"] = 0
        elif inv_mode == "三聯式（公司）":
            p["BuyerIdentifier"] = st.text_input("統一編號", value=p["BuyerIdentifier"])
            p["BuyerName"] = st.text_input("公司抬頭", value=p["BuyerName"])
            p["HasTax"] = 1
            p["CarrierType"] = ""
            p["DonateMark"] = 2
        elif inv_mode == "捐贈":
            p["DonateMark"] = 1
            npoban = st.text_input("捐贈碼（NPOBAN）", value=p.get("NPOBAN", ""))
            p["NPOBAN"] = npoban
        else:  # 二聯式
            p["CarrierType"] = ""
            p["CarrierId1"] = ""
            p["CarrierId2"] = ""
            p["DonateMark"] = 0
            p["BuyerIdentifier"] = ""

        if p.get("BuyerIdentifier"):
            has_tax = st.checkbox("含稅（BuyerIdentifier 有值時必勾）", value=True)
            p["HasTax"] = 1 if has_tax else 0

    # ── 預覽送出 XML ──
    with st.expander("🔍 預覽 XML 內容"):
        xml_preview = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice XSDVersion="2.8">
  <OrderId>{p['OrderId']}</OrderId>
  <OrderDate>{p['OrderDate']}</OrderDate>
  <BuyerIdentifier>{p['BuyerIdentifier']}</BuyerIdentifier>
  <BuyerName>{p['BuyerName']}</BuyerName>
  <BuyerAddress>{p['BuyerAddress']}</BuyerAddress>
  <BuyerTelephoneNumber>{p['BuyerTelephoneNumber']}</BuyerTelephoneNumber>
  <BuyerEmailAddress>{p['BuyerEmailAddress']}</BuyerEmailAddress>
  <DonateMark>{p['DonateMark']}</DonateMark>
  <InvoiceType>07</InvoiceType>
  <CarrierType>{p['CarrierType']}</CarrierType>
  <CarrierId1>{p['CarrierId1']}</CarrierId1>
  <CarrierId2>{p['CarrierId2']}</CarrierId2>
  <NPOBAN>{p['NPOBAN']}</NPOBAN>
  <TaxType>{p['TaxType']}</TaxType>
  <TaxRate>{p['TaxRate']}</TaxRate>
  <PayWay>{p['PayWay']}</PayWay>
  <Details>
    <ProductItem>
      <Description>清潔服務</Description>
      <Quantity>1</Quantity>
      <Unit>次</Unit>
      <UnitPrice>{p['UnitPrice']}</UnitPrice>
    </ProductItem>
  </Details>
</Invoice>"""
        st.code(xml_preview, language="xml")

    # ── 送出按鈕 ──
    st.markdown("---")
    submit_col1, submit_col2 = st.columns([1, 2])
    with submit_col1:
        submit_btn = st.button("🖨️ 送出開立發票", type="primary", use_container_width=True)
    with submit_col2:
        st.caption("確認資料無誤後，點擊送出發票至 ei.com.tw 發票系統。")

    if submit_btn:
        st.info("⚙️ 此按鈕實際串接時需呼叫 `ei.com.tw SOAP API` (`CreateInvoiceV3`)。\n\n"
                "請在後端 PHP `makeInvoice()` 或新增一支 Streamlit → PHP proxy endpoint 來執行，"
                "避免在前端直接暴露 SOAP 認證資訊。", icon="🔒")
        st.json(payload)

elif search_btn and not invoice_no_input.strip():
    st.warning("請輸入發票號碼或訂單編號。")
