# invoice-lemonsystem

Streamlit app for 檸檬家事發票系統.

## Streamlit Cloud

- App name: `invoice-lemonsystem`
- Main file path: `lemoninvoice.py`

## Current Version

- 台北 / 台中 / 桃園 / 新竹 / 高雄各自設定發票系統帳密、檸檬家事帳密、帳務處理表 Google Sheet ID。
- 只從檸檬家事讀資料，不寫回檸檬家事後台。
- 發票號碼與折讓單號回填各區帳務處理表。
- 訂單編號一律轉成 `原訂單編號-1`。
- 有統編時，發票姓名欄用抬頭、填統編、選含稅。
- 折讓金額以含稅輸入，系統回推未稅金額與稅額。
