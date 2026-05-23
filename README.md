# invoice-lemonsystem

檸檬家事發票與折讓單 Streamlit 工具。

## Streamlit Cloud 設定

- App URL: `invoice-lemonsystem.streamlit.app`
- Main file path: `lemoninvoice.py`

## Local Run

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run lemoninvoice.py
```

## Secrets

正式部署請在 Streamlit Cloud 的 Secrets 設定資料庫與鯨躍 API 參數，不要 commit `.env` 或 secrets。
