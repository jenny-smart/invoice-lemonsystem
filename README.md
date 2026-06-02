# invoice-lemonsystem v4

Main file path: `lemoninvoice.py`

## v4 workflow

This version uses one accounting worksheet per region.

Rules:

- B column status = `待收款` → create invoice.
- B column status = `待退款` → create allowance.
- G column = order id.
- System order id is always `G欄訂單編號-1`.
- Login to Lemonclean by order id and read order data only.
- Do not write back to Lemonclean.
- Write invoice number or allowance number back to the same accounting worksheet.
