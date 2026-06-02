from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from xml.sax.saxutils import escape
import hashlib


@dataclass
class InvoiceService:
    cfg: Dict[str, str]
    dry_run: bool = True

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

    def build_allowance_xml(self, payload: Dict[str, object]) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Allowance XSDVersion="2.8">'
            f"<OrderId>{escape(str(payload['order_id']))}</OrderId>"
            f"<InvoiceNumber>{escape(str(payload['invoice_no']))}</InvoiceNumber>"
            f"<AllowanceDate>{escape(str(payload.get('allowance_date', '')))}</AllowanceDate>"
            f"<AllowanceAmount>{int(payload.get('allowance_amount_pretax', 0))}</AllowanceAmount>"
            f"<TaxAmount>{int(payload.get('allowance_tax', 0))}</TaxAmount>"
            f"<TotalAmount>{int(payload.get('allowance_amount_with_tax', 0))}</TotalAmount>"
            f"<Reason>{escape(str(payload.get('reason', '退款折讓')))}</Reason>"
            "</Allowance>"
        )

    def create_allowance(self, payload: Dict[str, object]) -> Dict[str, object]:
        xml = self.build_allowance_xml(payload)
        params = {"allowancexml": xml, "rentid": self._rent_id()}

        if self.dry_run:
            fake_no = "AL" + hashlib.sha1((payload["order_id"] + payload["invoice_no"]).encode("utf-8")).hexdigest()[:8].upper()
            return {
                "success": True,
                "allowance_no": fake_no[:10],
                "message": "DRY RUN：已建立折讓單 payload，未送出；正式 method 需依鯨躍規格確認",
                "params": params,
            }

        raise NotImplementedError("折讓單 SOAP method 未在現有 Laravel 程式中找到，需先向鯨躍確認正式 method 與 XML 規格。")
