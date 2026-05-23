import os
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="檸檬家事發票系統",
    page_icon="🧾",
    layout="wide",
)

APP_NAME = "invoice-lemonsystem"


@st.cache_data
def sample_invoice_rows():
    return pd.DataFrame(
        [
            {
                "訂單編號": "LC202605240001",
                "發票號碼": "AB12345678",
                "開票日期": "2026-05-24",
                "客戶姓名": "測試客戶",
                "統編": "",
                "發票類型": "二聯式",
                "載具類型": "紙本",
                "金額": 3000,
                "狀態": "已開立",
            }
        ]
    )


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="invoices")
    return output.getvalue()


def render_sidebar():
    st.sidebar.title("檸檬家事發票系統")
    return st.sidebar.radio(
        "功能選單",
        ["首頁", "開立發票", "開立折讓單", "下載發票", "下載紙本發票", "設定"],
    )


def page_home():
    st.title("檸檬家事發票系統")
    st.caption("Streamlit Cloud app: invoice-lemonsystem.streamlit.app")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("今日開票張數", "0")
    col2.metric("今日開票金額", "$0")
    col3.metric("待開票訂單", "0")
    col4.metric("開票失敗", "0")

    st.divider()
    st.subheader("目前狀態")
    st.info("這是 MVP 介面。下一步接上檸檬家事資料庫與鯨躍／關網 SOAP API。")


def page_issue_invoice():
    st.title("開立發票")
    purchase_id = st.text_input("Purchase ID / 訂單 ID")
    invoice_kind = st.selectbox("發票種類", ["normal", "weekly_price", "new_year"])

    if st.button("查詢訂單", type="secondary"):
        if not purchase_id:
            st.warning("請先輸入訂單 ID。")
        else:
            st.success("已取得訂單資料（目前為測試畫面）。")
            st.json({"purchase_id": purchase_id, "invoice_kind": invoice_kind, "amount": 3000})

    if st.button("開立發票", type="primary"):
        if not purchase_id:
            st.warning("請先輸入訂單 ID。")
        else:
            st.info("正式串接後，這裡會呼叫鯨躍／關網 CreateInvoiceV3。")


def page_allowance():
    st.title("開立折讓單")
    purchase_id = st.text_input("Purchase ID / 訂單 ID", key="allowance_purchase_id")
    invoice_no = st.text_input("原發票號碼")
    invoice_date = st.date_input("原發票日期", value=date.today())
    allowance_amount = st.number_input("折讓金額", min_value=0, step=1)
    reason = st.text_area("折讓原因", value="部分退款")

    if st.button("開立折讓單", type="primary"):
        if not invoice_no or allowance_amount <= 0:
            st.warning("請輸入發票號碼與大於 0 的折讓金額。")
        else:
            st.info("正式串接後，這裡會呼叫鯨躍／關網折讓單 API。")
            st.json(
                {
                    "purchase_id": purchase_id,
                    "invoice_no": invoice_no,
                    "invoice_date": str(invoice_date),
                    "allowance_amount": allowance_amount,
                    "reason": reason,
                }
            )


def page_export_invoices(paper_only: bool = False):
    st.title("下載紙本發票" if paper_only else "下載發票")
    col1, col2 = st.columns(2)
    date_start = col1.date_input("開始日期", value=date.today().replace(day=1))
    date_end = col2.date_input("結束日期", value=date.today())

    if st.button("查詢"):
        df = sample_invoice_rows()
        if paper_only:
            df = df[df["載具類型"] == "紙本"]
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "下載 Excel",
            data=to_excel_bytes(df),
            file_name=("paper_invoices.xlsx" if paper_only else "invoices.xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption(f"查詢區間：{date_start} ~ {date_end}")


def page_settings():
    st.title("設定")
    st.subheader("環境變數檢查")
    required_envs = ["DB_HOST", "DB_NAME", "DB_USER", "CETUS_WSDL", "CETUS_RENT_ID"]
    rows = [{"變數": k, "是否已設定": "✅" if os.getenv(k) else "❌"} for k in required_envs]
    st.table(pd.DataFrame(rows))
    st.warning("請不要把正式 DB 密碼或鯨躍 API 密鑰寫進 GitHub，請使用 Streamlit Secrets。")


def main():
    page = render_sidebar()
    if page == "首頁":
        page_home()
    elif page == "開立發票":
        page_issue_invoice()
    elif page == "開立折讓單":
        page_allowance()
    elif page == "下載發票":
        page_export_invoices(False)
    elif page == "下載紙本發票":
        page_export_invoices(True)
    elif page == "設定":
        page_settings()


if __name__ == "__main__":
    main()
