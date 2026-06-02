# invoice-lemonsystem

Streamlit app for 檸檬家事發票、折讓單、發票查詢、藍新金流流程。

## Streamlit Cloud

- App name: `invoice-lemonsystem`
- Main file path: `lemoninvoice.py`

## Version 3 scope

- 鯨躍／關網 SOAP:
  - `CreateInvoiceV3`
  - `QueryInvoiceNumberByOrderid`
  - 折讓單 payload scaffold（正式 method 需向鯨躍確認）
- 藍新金流:
  - `CreditCard/Cancel` payload scaffold
- 各區設定:
  - 台北 / 台中 / 桃園 / 新竹 / 高雄
  - RentID
  - 檸檬家事帳密（只讀）
  - 各區帳務處理表 ID
  - 藍新 MerchantID / HashKey / HashIV
- 預設為 Dry Run，不會真正送出 API。

## Important

Do not commit real credentials to GitHub. Use Streamlit Cloud Secrets.
