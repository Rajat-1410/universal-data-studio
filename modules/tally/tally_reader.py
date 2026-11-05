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
    def decode_and_sanitize_xml(cls, xml_content: Any) -> Tuple[ET.Element, str]:
        """
        Robustly decodes and sanitizes Tally XML from raw bytes or string.
        Handles:
          - Encodings: UTF-16, UTF-16-LE, UTF-16-BE, UTF-8-SIG, UTF-8, CP1252, Latin-1, ISO-8859-1
          - Strips leading BOMs, non-XML prefixes, trailing garbage, and invalid control chars
          - Normalizes XML declarations that conflict with Expat parser on Unicode strings
          - Escapes unescaped ampersands (& not followed by entity name)
          - Wraps in <ENVELOPE> if multiple root elements exist (e.g. repeated <TALLYMESSAGE>)
        """
        if isinstance(xml_content, bytes):
            raw = xml_content
            text = None

            # 1. Check Byte Order Marks (BOM)
            if raw.startswith(b"\xef\xbb\xbf"):
                try:
                    text = raw.decode("utf-8-sig")
                except Exception:
                    pass
            elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
                try:
                    text = raw.decode("utf-16")
                except Exception:
                    pass

            # 2. Check encoding attribute in XML declaration
            if text is None:
                m = re.search(rb"""<\?xml[^>]*encoding=['"]([^'"]+)['"]""", raw[:500])
                if m:
                    declared_enc = m.group(1).decode("ascii", errors="ignore").strip().lower()
                    try:
                        text = raw.decode(declared_enc)
                    except Exception:
                        pass

            # 3. Try standard candidate encodings
            if text is None:
                for enc in ["utf-8", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin-1", "iso-8859-1"]:
                    try:
                        candidate = raw.decode(enc)
                        if "<" in candidate and ">" in candidate:
                            text = candidate
                            break
                    except Exception:
                        continue

            if text is None:
                text = raw.decode("utf-8", errors="replace")
        else:
            text = str(xml_content)

        if not text or not text.strip():
            raise ValueError("Tally XML content is empty.")

        # Remove unicode BOM if present
        if text.startswith("\ufeff"):
            text = text[1:]
        text = text.strip()

        # Strip non-XML characters before first '<' and after last '>'
        if "<" in text and not text.startswith("<"):
            text = text[text.index("<"):]
        if ">" in text and not text.endswith(">"):
            text = text[:text.rindex(">") + 1]

        # Clean illegal XML 1.0 control characters (preserve tab \t, newline \n, carriage return \r)
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Escape unescaped ampersands: & not followed by a valid entity or character reference
        clean = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", clean)

        # Remove XML declaration when passing unicode str to Expat parser
        clean = re.sub(r"<\?xml[^>]*\?>", "", clean, count=1).strip()

        try:
            root = ET.fromstring(clean)
        except ET.ParseError as pe:
            # Try wrapping in ENVELOPE if document has multiple root elements
            try:
                wrapped = f"<ENVELOPE>\n{clean}\n</ENVELOPE>"
                root = ET.fromstring(wrapped)
            except Exception:
                raise ValueError(f"Invalid Tally XML syntax: {str(pe)}")

        return root, text

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
        root, xml_str = cls.decode_and_sanitize_xml(xml_content)

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
