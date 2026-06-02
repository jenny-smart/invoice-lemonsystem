from __future__ import annotations

from typing import Dict


def fetch_order_detail_from_lemonclean(region: str, order_id: str, cfg: Dict[str, str], dry_run: bool = True) -> Dict[str, str]:
    """
    Login to Lemonclean and fetch order detail.
    This function must only read Lemonclean data. Do not write back.
    """
    if dry_run:
        if order_id.endswith("0042-1"):
            return {
                "訂單編號": order_id,
                "客戶姓名": "範例公司",
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
            "客戶姓名": "王小明",
            "抬頭": "",
            "統編": "",
            "電話": "0912345678",
            "地址": "台北市範例區檸檬路 1 號",
            "Email": "customer@example.com",
            "服務名稱": "清潔服務",
            "服務類型代碼": "1",
        }

    # TODO: Use requests.Session to login and parse order detail page or use internal API if available.
    raise NotImplementedError("檸檬家事登入讀取尚未接上正式 endpoint。")
