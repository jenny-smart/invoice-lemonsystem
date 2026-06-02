from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from urllib.parse import urlencode
import binascii
import requests

from Crypto.Cipher import AES


@dataclass
class NewebPayService:
    cfg: Dict[str, str]
    dry_run: bool = True

    def _required(self, key: str) -> str:
        value = self.cfg.get(key)
        if not value:
            raise ValueError(f"Missing {key}")
        return value

    @staticmethod
    def _pad(data: bytes) -> bytes:
        block_size = 32
        padding = block_size - len(data) % block_size
        return data + bytes([padding]) * padding

    def encrypt_post_data(self, data: Dict[str, object]) -> str:
        hash_key = self._required("newebpay_hash_key").encode("utf-8")
        hash_iv = self._required("newebpay_hash_iv").encode("utf-8")
        raw = urlencode(data).encode("utf-8")
        cipher = AES.new(hash_key, AES.MODE_CBC, hash_iv)
        return binascii.hexlify(cipher.encrypt(self._pad(raw))).decode("utf-8")

    def cancel_credit_card(self, merchant_order_no: str, amount: int) -> Dict[str, object]:
        merchant_id = self._required("newebpay_merchant_id")
        url = self.cfg.get("newebpay_cancel_url") or "https://core.spgateway.com/API/CreditCard/Cancel"

        post_data = {
            "RespondType": "JSON",
            "Version": "1.0",
            "Amt": amount,
            "MerchantOrderNo": merchant_order_no,
        }
        encrypted = self.encrypt_post_data(post_data)

        payload = {
            "MerchantID_": merchant_id,
            "PostData_": encrypted,
        }

        if self.dry_run:
            return {
                "success": True,
                "message": "DRY RUN：已建立藍新 CreditCard/Cancel payload，未送出",
                "url": url,
                "payload_keys": list(payload.keys()),
                "merchant_order_no": merchant_order_no,
                "amount": amount,
            }

        response = requests.post(url, data=payload, timeout=30)
        ok = response.status_code == 200
        return {
            "success": ok,
            "message": "藍新取消授權已送出" if ok else f"藍新 API HTTP {response.status_code}",
            "status_code": response.status_code,
            "raw": response.text,
        }
