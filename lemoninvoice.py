"""
檸檬家事 - 發票開立查詢介面
從官網 API 查詢訂單資訊，整理後送至發票開立系統
"""

import streamlit as st
import requests

# ── 設定 ──────────────────────────────────────────
API_BASE = st.secrets.get("LEMON_API_BASE", "https://api.lemonclean.com.tw")

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

# 商品清單：(編號, 名稱, 規格, 單位, 單價, 可改單價)
PRODUCTS = [
    (1,  "清潔服務-平日",   "2人", "1小時", 1200, False),
    (2,  "清潔服務-週末",   "2人", "1小時", 1400, False),
    (3,  "清潔服務-週末加價", "1人", "1小時", 100,  False),
    (4,  "異動費用-一般",   "2人", "1小時", 360,  True),
    (5,  "異動費用-VIP",    "",    "1",     600,  True),
    (8,  "車馬費",          "1人", "人",    100,  False),
    (11, "工具組",          "",    "組",    700,  False),
]
PRODUCT_NAMES = [f"{p[1]}（{p[2]}）" if p[2] else p[1] for p in PRODUCTS]
PRODUCT_MAP   = {p[1] if not p[2] else p[1]: p for p in PRODUCTS}  # name → tuple

# ── 頁面設定 ──────────────────────────────────────
st.set_page_config(
    page_title="檸檬家事 發票開立",
    page_icon="🍋",
    layout="centered",
)

st.markdown("""
<style>
    .block-container { max-width: 800px; }
    .field-label { font-size: 0.82rem; color: #888; margin-bottom: 2px; }
    .field-value { font-size: 1rem; font-weight: 500; color: #1a1a1a; padding: 6px 10px;
                   background: #f7f9fc; border-radius: 6px; margin-bottom: 8px;
                   border-left: 3px solid #FFD700; }
    .section-title { font-size: 0.9rem; font-weight: 700; color: #555;
                     text-transform: uppercase; letter-spacing: 0.05em;
                     border-bottom: 1px solid #eee; padding-bottom: 4px; margin: 16px 0 10px; }
    .badge-2     { background:#e8f4fd; color:#1565c0; padding:2px 10px; border-radius:12px; font-size:0.82rem; }
    .badge-3     { background:#fff3e0; color:#e65100; padding:2px 10px; border-radius:12px; font-size:0.82rem; }
    .badge-donate{ background:#f3e5f5; color:#6a1b9a; padding:2px 10px; border-radius:12px; font-size:0.82rem; }
    .total-row   { font-size:1.1rem; font-weight:700; color:#1a1a1a; text-align:right;
                   padding:10px; background:#fffde7; border-radius:6px; margin-top:8px; }
</style>
""", unsafe_allow_html=True)

st.title("🍋 發票開立查詢")
st.caption("輸入訂單編號，從官網查詢訂單資訊並整理為發票開立所需欄位。")

# ── 初始化 session_state ──────────────────────────
if "items" not in st.session_state:
    st.session_state.items = []   # list of {name, qty, unit_price, editable}

# ── Step 1：查詢訂單 ─────────────────────────────
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    order_input = st.text_input(
        "訂單編號",
        placeholder="例：LC20240501001",
    )
with col2:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    search_btn = st.button("🔍 查詢", use_container_width=True, type="primary")


def fetch_order(query: str):
    try:
        resp = requests.post(f"{API_BASE}/order", json={"order_no": query}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("return_code") == "0000" and data.get("data"):
            return data["data"]
    except Exception as e:
        st.error(f"API 查詢失敗：{e}")
    return None


def field(label: str, value):
    display = str(value) if value not in (None, "", 0) else "—"
    st.markdown(
        f'<div class="field-label">{label}</div>'
        f'<div class="field-value">{display}</div>',
        unsafe_allow_html=True,
    )


def build_base_payload(purchase: dict) -> dict:
    """組出買方 / 載具 / 付款欄位（不含明細）"""
    invoice_type   = purchase.get("invoice_type", 0)
    carrier_type_id = purchase.get("carrier_type_id", 0)

    p = {
        "OrderId":             f"{purchase.get('order_no', '')}-1",
        "OrderDate":           (purchase.get("created_at", "")[:10].replace("-", "/")
                                if purchase.get("created_at") else ""),
        "BuyerName":           "",
        "BuyerIdentifier":     "",
        "BuyerAddress":        purchase.get("address", ""),
        "BuyerEmailAddress":   purchase.get("email", ""),
        "BuyerTelephoneNumber": purchase.get("phone", ""),
        "CarrierType":         "",
        "CarrierId1":          "",
        "CarrierId2":          "",
        "DonateMark":          0,
        "NPOBAN":              "",
        "PayWay":              3,
        "TaxType":             1,
        "TaxRate":             0.05,
        "HasTax":              1,
    }

    if invoice_type == 1:
        p["BuyerName"]  = purchase.get("name", "")
        p["DonateMark"] = 1
        p["NPOBAN"]     = purchase.get("donate_code", "")
    elif invoice_type == 2:
        p["BuyerName"] = purchase.get("name", "")
        if carrier_type_id == 1:
            p["CarrierId1"] = purchase.get("email", "")
            p["CarrierId2"] = purchase.get("email", "")
        elif carrier_type_id == 2:
            p["CarrierType"] = "3J0002"
            p["CarrierId1"]  = purchase.get("carrier_info", "")
            p["CarrierId2"]  = purchase.get("carrier_info", "")
        elif carrier_type_id == 3:
            p["CarrierType"] = "CQ0001"
            p["CarrierId1"]  = purchase.get("carrier_info", "")
            p["CarrierId2"]  = purchase.get("carrier_info", "")
        elif carrier_type_id == 4:
            p["DonateMark"] = 2
    elif invoice_type == 3:
        p["BuyerIdentifier"] = purchase.get("company_no", "")
        p["BuyerName"]       = purchase.get("company_title", "")
        p["DonateMark"]      = 2
        p["HasTax"]          = 1
    else:
        p["BuyerName"] = purchase.get("name", "")

    payway = purchase.get("payway", 0)
    p["PayWay"] = 2 if payway == 2 else 3

    return p


# ── 查詢結果 ─────────────────────────────────────
if search_btn and order_input.strip():
    with st.spinner("查詢中…"):
        purchase = fetch_order(order_input.strip())
    if purchase is None:
        st.warning("查無訂單，請確認號碼是否正確。")
        st.stop()
    st.session_state.purchase = purchase
    st.session_state.items    = []   # 重置明細

elif search_btn:
    st.warning("請輸入訂單編號。")

# ── 以下只在有查詢結果時顯示 ─────────────────────
if "purchase" not in st.session_state:
    st.stop()

purchase        = st.session_state.purchase
invoice_type    = purchase.get("invoice_type", 0)
carrier_type_id = purchase.get("carrier_type_id", 0)

st.success(f"✅ 查詢成功：{purchase.get('order_no', '')}")

# ── 訂單基本資訊 ──────────────────────────────────
st.markdown('<div class="section-title">📋 訂單資訊</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    field("訂單編號",   purchase.get("order_no"))
    field("訂購人姓名", purchase.get("name"))
    field("電話",       purchase.get("phone"))
    field("Email",      purchase.get("email"))
with c2:
    field("地址",       purchase.get("address"))
    field("付款方式",   PAYWAY_MAP.get(purchase.get("payway", 0), "—"))
    field("訂單金額",   f"NT$ {purchase.get('total', 0):,}")
    field("運費",       f"NT$ {purchase.get('fare', 0):,}")

# 發票類型 badge
inv_label = INVOICE_TYPE_MAP.get(invoice_type, "—")
badge_cls = "badge-3" if invoice_type == 3 else ("badge-donate" if invoice_type == 1 else "badge-2")
st.markdown(
    f'<div class="section-title">🧾 發票類型 &nbsp;'
    f'<span class="{badge_cls}">{inv_label}</span></div>',
    unsafe_allow_html=True,
)
if invoice_type == 1:
    field("捐贈碼 NPOBAN", purchase.get("donate_code"))
elif invoice_type == 2:
    field("載具類型", CARRIER_TYPE_MAP.get(carrier_type_id, "—"))
    if carrier_type_id in (2, 3):
        field("載具條碼", purchase.get("carrier_info"))
    elif carrier_type_id == 1:
        field("會員載具 Email", purchase.get("email"))
elif invoice_type == 3:
    field("公司抬頭", purchase.get("company_title"))
    field("統一編號", purchase.get("company_no"))
    st.info("三聯式：含稅需勾選", icon="ℹ️")

# ── 發票明細 ─────────────────────────────────────
st.markdown('<div class="section-title">📦 發票明細</div>', unsafe_allow_html=True)

# 新增一筆
with st.container(border=True):
    st.markdown("**新增項目**")
    na_col, nb_col, nc_col, nd_col = st.columns([3, 1, 1, 1])
    with na_col:
        sel_name = st.selectbox("商品", PRODUCT_NAMES, key="sel_product", label_visibility="collapsed")
    # 找對應 product tuple
    sel_idx   = PRODUCT_NAMES.index(sel_name)
    sel_prod  = PRODUCTS[sel_idx]   # (id, name, spec, unit, price, editable)
    with nb_col:
        new_qty = st.number_input("數量", min_value=1, value=1, step=1, key="new_qty", label_visibility="collapsed")
    with nc_col:
        if sel_prod[5]:  # editable price
            new_price = st.number_input("單價", min_value=0, value=sel_prod[4], step=10, key="new_price", label_visibility="collapsed")
        else:
            st.markdown(f"<div style='padding-top:6px;font-weight:600'>{sel_prod[4]:,}</div>", unsafe_allow_html=True)
            new_price = sel_prod[4]
    with nd_col:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        add_btn = st.button("＋ 加入", use_container_width=True)

    if add_btn:
        st.session_state.items.append({
            "name":       sel_prod[1],
            "spec":       sel_prod[2],
            "unit":       sel_prod[3],
            "qty":        new_qty,
            "unit_price": new_price,
            "editable":   sel_prod[5],
        })
        st.rerun()

# 顯示已加入的明細
items = st.session_state.items
if items:
    header = st.columns([3, 1, 1, 1, 1])
    for h, t in zip(header, ["商品", "數量", "單價", "小計", ""]):
        h.markdown(f"<div style='font-size:0.8rem;color:#888'>{t}</div>", unsafe_allow_html=True)

    for i, item in enumerate(items):
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
        with c1:
            label = f"{item['name']}（{item['spec']}）" if item['spec'] else item['name']
            st.markdown(f"<div style='padding-top:6px'>{label}</div>", unsafe_allow_html=True)
        with c2:
            new_q = st.number_input("qty", min_value=1, value=item["qty"], step=1,
                                     key=f"qty_{i}", label_visibility="collapsed")
            st.session_state.items[i]["qty"] = new_q
        with c3:
            if item["editable"]:
                new_p = st.number_input("price", min_value=0, value=item["unit_price"], step=10,
                                         key=f"price_{i}", label_visibility="collapsed")
                st.session_state.items[i]["unit_price"] = new_p
            else:
                st.markdown(f"<div style='padding-top:6px'>{item['unit_price']:,}</div>",
                             unsafe_allow_html=True)
                new_p = item["unit_price"]
        with c4:
            subtotal = new_q * new_p
            st.markdown(f"<div style='padding-top:6px;font-weight:600'>{subtotal:,}</div>",
                         unsafe_allow_html=True)
        with c5:
            if st.button("🗑️", key=f"del_{i}", help="移除"):
                st.session_state.items.pop(i)
                st.rerun()

    total_amount = sum(it["qty"] * it["unit_price"] for it in st.session_state.items)
    st.markdown(f'<div class="total-row">合計：NT$ {total_amount:,}</div>', unsafe_allow_html=True)
else:
    st.caption("尚未加入任何項目，請從上方選擇商品。")
    total_amount = 0

# ── 買方資料確認 ──────────────────────────────────
st.markdown('<div class="section-title">🖨️ 發票開立資料確認</div>', unsafe_allow_html=True)

payload = build_base_payload(purchase)

with st.expander("✏️ 確認 / 修改買方資料", expanded=True):
    p = payload
    col_a, col_b = st.columns(2)
    with col_a:
        p["OrderId"]              = st.text_input("訂單編號（OrderId）", value=p["OrderId"])
        p["BuyerName"]            = st.text_input("買方名稱",            value=p["BuyerName"])
        p["BuyerIdentifier"]      = st.text_input("買方統編",            value=p["BuyerIdentifier"],
                                                   help="三聯式才需填入")
        p["BuyerTelephoneNumber"] = st.text_input("買方電話",            value=p["BuyerTelephoneNumber"])
    with col_b:
        p["BuyerAddress"]      = st.text_input("買方地址", value=p["BuyerAddress"])
        p["BuyerEmailAddress"] = st.text_input("買方 Email", value=p["BuyerEmailAddress"])
        p["PayWay"]            = st.selectbox(
            "付款方式（PayWay）",
            options=[2, 3],
            format_func=lambda x: "2 - ATM 轉帳" if x == 2 else "3 - 信用卡 / 其他",
            index=0 if p["PayWay"] == 2 else 1,
        )

    st.markdown("**發票方式**")
    default_mode = {
        0: "二聯式（個人）",
        1: "捐贈",
        2: "手機載具" if carrier_type_id == 2 else "會員載具" if carrier_type_id == 1 else "二聯式（個人）",
        3: "三聯式（公司）",
    }.get(invoice_type, "二聯式（個人）")

    inv_mode = st.radio(
        "發票方式",
        ["二聯式（個人）", "手機載具", "會員載具", "三聯式（公司）", "捐贈"],
        horizontal=True,
        index=["二聯式（個人）", "手機載具", "會員載具", "三聯式（公司）", "捐贈"].index(default_mode),
        label_visibility="collapsed",
    )

    if inv_mode == "手機載具":
        mobile_carrier = st.text_input("手機條碼", value=p.get("CarrierId1", ""), placeholder="/XXXXXXX")
        p["CarrierType"] = "3J0002"
        p["CarrierId1"]  = mobile_carrier
        p["CarrierId2"]  = mobile_carrier
        p["DonateMark"]  = 0
        p["BuyerIdentifier"] = ""
    elif inv_mode == "會員載具":
        st.info(f"CarrierId 帶入訂購人 Email：**{p['BuyerEmailAddress']}**", icon="📧")
        p["CarrierType"] = ""
        p["CarrierId1"]  = p["BuyerEmailAddress"]
        p["CarrierId2"]  = p["BuyerEmailAddress"]
        p["DonateMark"]  = 0
    elif inv_mode == "三聯式（公司）":
        p["BuyerIdentifier"] = st.text_input("統一編號", value=p["BuyerIdentifier"], key="uni2")
        p["BuyerName"]       = st.text_input("公司抬頭", value=p["BuyerName"],       key="bn2")
        p["HasTax"]          = 1
        p["CarrierType"]     = ""
        p["DonateMark"]      = 2
    elif inv_mode == "捐贈":
        p["DonateMark"] = 1
        p["NPOBAN"]     = st.text_input("捐贈碼（NPOBAN）", value=p.get("NPOBAN", ""))
    else:  # 二聯式
        p["CarrierType"]     = ""
        p["CarrierId1"]      = ""
        p["CarrierId2"]      = ""
        p["DonateMark"]      = 0
        p["BuyerIdentifier"] = ""

    if p.get("BuyerIdentifier"):
        has_tax = st.checkbox("含稅（三聯式必勾）", value=True)
        p["HasTax"] = 1 if has_tax else 0

# ── XML 預覽 ──────────────────────────────────────
with st.expander("🔍 預覽 XML"):
    items_xml = ""
    for it in (items if items else [{"name": "清潔服務", "spec": "", "unit": "次",
                                      "qty": 1, "unit_price": total_amount}]):
        items_xml += f"""
    <ProductItem>
      <Description>{it['name']}</Description>
      <Quantity>{it['qty']}</Quantity>
      <Unit>{it['unit']}</Unit>
      <UnitPrice>{it['unit_price']}</UnitPrice>
    </ProductItem>"""
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
  <Details>{items_xml}
  </Details>
</Invoice>"""
    st.code(xml_preview, language="xml")

# ── 送出 ──────────────────────────────────────────
st.markdown("---")
if not items:
    st.warning("請先加入至少一筆發票明細。")
else:
    s1, s2 = st.columns([1, 2])
    with s1:
        submit_btn = st.button("🖨️ 送出開立發票", type="primary", use_container_width=True,
                               disabled=(total_amount == 0))
    with s2:
        st.caption(f"共 {len(items)} 筆明細，合計 NT$ {total_amount:,}")

    if submit_btn:
        # 組最終 payload
        final_payload = {**p, "items": items, "total": total_amount}
        # TODO: 待 PHP proxy endpoint 確認後，改為：
        # resp = requests.post(f"{API_BASE}/invoice/create_proxy", json=final_payload, timeout=15)
        st.info("PHP proxy endpoint 尚未設定，以下為將送出的資料：", icon="🔒")
        st.json(final_payload)
