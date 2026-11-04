"""
Tally XML Reader (Phase 6)
Parses TallyPrime XML export documents without losing non-voucher metadata,
extracting voucher identities, ledgers, allocations, and accounting properties.
"""
import io
import re
from typing import Dict, Any, List, Optional, Tuple
import xml.etree.ElementTree as ET
import pandas as pd


class TallyReader:
    """Parses Tally XML documents without losing GST, inventory, or non-voucher metadata."""

    @classmethod
    def clean_tag(cls, tag: str) -> str:
        """Removes XML namespace brackets for comparison."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def parse_tally_xml(cls, xml_content: Any) -> Dict[str, Any]:
        """
        Parses Tally XML from bytes or string.
        Returns:
            {
                "root": ET.Element,
                "company_name": str,
                "vouchers": List[Dict[str, Any]],
                "vouchers_df": pd.DataFrame,
                "total_vouchers": int,
                "summary": Dict[str, Any],
                "raw_str": str
            }
        """
        if isinstance(xml_content, bytes):
            xml_str = xml_content.decode("utf-8", errors="replace")
        else:
            xml_str = str(xml_content)

        if not xml_str.strip():
            raise ValueError("Tally XML content is empty.")

        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as pe:
            raise ValueError(f"Invalid Tally XML syntax: {str(pe)}")

        # Extract Company Name if available
        company_name = "Unknown Company"
        for elem in root.iter():
            clean = cls.clean_tag(elem.tag)
            if clean in ["SVCURRENTCOMPANY", "COMPANY"]:
                if elem.text and elem.text.strip():
                    company_name = elem.text.strip()
                    break

        vouchers = []
        # Find all <VOUCHER> tags regardless of nesting depth
        for elem in root.iter():
            if cls.clean_tag(elem.tag) == "VOUCHER":
                v_data = cls._extract_voucher_info(elem)
                vouchers.append(v_data)

        # Build summary dataframe
        df_rows = []
        for v in vouchers:
            for l in v["ledger_entries"]:
                df_rows.append({
                    "GUID": v["guid"],
                    "VoucherNumber": v["voucher_number"],
                    "Date": v["date"],
                    "VoucherType": v["voucher_type"],
                    "PartyName": v["party_name"],
                    "LedgerName": l["ledger_name"],
                    "Amount": l["amount"],
                    "IsDeemedPositive": l["is_deemed_positive"],
                    "Narration": v["narration"],
                })

        vouchers_df = pd.DataFrame(df_rows) if df_rows else pd.DataFrame(
            columns=["GUID", "VoucherNumber", "Date", "VoucherType", "PartyName", "LedgerName", "Amount", "IsDeemedPositive", "Narration"]
        )

        voucher_types_count = {}
        for v in vouchers:
            vt = v["voucher_type"] or "Unknown"
            voucher_types_count[vt] = voucher_types_count.get(vt, 0) + 1

        summary = {
            "total_vouchers": len(vouchers),
            "total_ledger_rows": len(vouchers_df),
            "company_name": company_name,
            "voucher_types": voucher_types_count,
            "has_guids": sum(1 for v in vouchers if v["guid"]),
            "has_voucher_numbers": sum(1 for v in vouchers if v["voucher_number"]),
        }

        return {
            "root": root,
            "company_name": company_name,
            "vouchers": vouchers,
            "vouchers_df": vouchers_df,
            "total_vouchers": len(vouchers),
            "summary": summary,
            "raw_str": xml_str,
        }

    @classmethod
    def _extract_voucher_info(cls, v_elem: ET.Element) -> Dict[str, Any]:
        """Extracts complete voucher details while keeping a reference to the raw XML element."""
        attribs = dict(v_elem.attrib)
        guid = ""
        vch_num = attribs.get("VCHNUM", "")
        vch_type = attribs.get("VCHTYPE", "")
        date = ""
        party_name = ""
        narration = ""
        alter_id = attribs.get("ALTERID", "")
        master_id = attribs.get("MASTERID", "")

        ledger_entries = []

        for child in v_elem:
            c_tag = cls.clean_tag(child.tag)
            text_val = (child.text or "").strip()

            if c_tag == "GUID":
                guid = text_val
            elif c_tag in ["VOUCHERNUMBER", "VCHNUMBER"]:
                vch_num = text_val
            elif c_tag in ["VOUCHERTYPENAME", "VOUCHERTYPE"]:
                vch_type = text_val
            elif c_tag == "DATE":
                date = text_val
            elif c_tag in ["PARTYLEDGERNAME", "PARTYNAME", "BASICBUYERNAME"] and not party_name:
                party_name = text_val
            elif c_tag == "NARRATION":
                narration = text_val
            elif c_tag == "ALTERID":
                alter_id = text_val
            elif c_tag == "MASTERID":
                master_id = text_val
            elif c_tag in ["ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"]:
                l_info = cls._extract_ledger_entry(child)
                ledger_entries.append(l_info)

        # Fallback for GUID from attributes if not in tags
        if not guid and "GUID" in attribs:
            guid = attribs["GUID"]

        # Calculate debit / credit totals
        debits = sum(abs(l["amount"]) for l in ledger_entries if l["is_deemed_positive"] == "Yes" or l["amount"] < 0)
        credits = sum(abs(l["amount"]) for l in ledger_entries if l["is_deemed_positive"] == "No" or l["amount"] > 0)

        return {
            "guid": guid,
            "voucher_number": vch_num,
            "voucher_type": vch_type,
            "date": date,
            "party_name": party_name,
            "narration": narration,
            "alter_id": alter_id,
            "master_id": master_id,
            "attributes": attribs,
            "ledger_entries": ledger_entries,
            "total_debit": debits,
            "total_credit": credits,
            "raw_element": v_elem,
        }

    @classmethod
    def _extract_ledger_entry(cls, l_elem: ET.Element) -> Dict[str, Any]:
        """Extracts ledger name, amount, deemed positive status, and bill/bank allocations."""
        ledger_name = ""
        amount = 0.0
        is_deemed_positive = "No"
        bill_allocations = []
        bank_allocations = []
        cost_centres = []

        for item in l_elem:
            tag = cls.clean_tag(item.tag)
            txt = (item.text or "").strip()

            if tag == "LEDGERNAME":
                ledger_name = txt
            elif tag == "ISDEEMEDPOSITIVE":
                is_deemed_positive = txt
            elif tag == "AMOUNT":
                try:
                    amount = float(txt)
                except ValueError:
                    amount = 0.0
            elif tag == "BILLALLOCATIONS.LIST":
                b_name = item.find("NAME")
                b_type = item.find("BILLTYPE")
                b_amt = item.find("AMOUNT")
                bill_allocations.append({
                    "name": b_name.text.strip() if b_name is not None and b_name.text else "",
                    "bill_type": b_type.text.strip() if b_type is not None and b_type.text else "",
                    "amount": float(b_amt.text.strip()) if b_amt is not None and b_amt.text else 0.0,
                    "element": item,
                })
            elif tag == "BANKALLOCATIONS.LIST":
                bank_allocations.append({"element": item})
            elif tag == "COSTCENTREALLOCATIONS.LIST":
                cost_centres.append({"element": item})

        return {
            "ledger_name": ledger_name,
            "amount": amount,
            "is_deemed_positive": is_deemed_positive,
            "bill_allocations": bill_allocations,
            "bank_allocations": bank_allocations,
            "cost_centres": cost_centres,
            "element": l_elem,
        }
