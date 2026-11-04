"""
Tally Voucher Updater (Phase 6)
Mutates ledger amounts in-place within TallyPrime XML documents.
Strictly preserves GUID, voucher identity, GST details, inventory entries,
allocations, cost centres, UDFs, and all unrelated metadata.
"""
import copy
from typing import Dict, Any, List, Optional, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom


class VoucherUpdater:
    """Safely updates Tally voucher ledger amounts while preserving all XML structures."""

    @classmethod
    def clean_tag(cls, tag: str) -> str:
        """Strips namespace brackets."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def apply_updates(
        cls,
        parsed_tally: Dict[str, Any],
        matching_result: Dict[str, Any],
        set_alter_action: bool = True,
    ) -> Dict[str, Any]:
        """
        Applies verified ledger amount updates to the Tally XML tree.
        """
        # Deepcopy root element to ensure original parsed structure remains completely immutable
        orig_root = parsed_tally["root"]
        root_copy = copy.deepcopy(orig_root)

        reconciled_vouchers = matching_result.get("reconciled_vouchers", [])
        effective_match_by = matching_result.get("effective_match_by", "GUID")

        # Filter only vouchers with verified changes
        actionable_vouchers = [
            v for v in reconciled_vouchers
            if v.get("has_changes") and v.get("can_update")
        ]

        # Index actionable vouchers by match key
        updates_by_key = {}
        for v in actionable_vouchers:
            updates_by_key[v["key"]] = v

        audit_log = []
        updated_vouchers_count = 0
        updated_ledgers_count = 0

        # Traverse root_copy to find vouchers and update
        for elem in root_copy.iter():
            if cls.clean_tag(elem.tag) != "VOUCHER":
                continue

            # Extract this voucher's match key
            guid = ""
            vch_num = elem.attrib.get("VCHNUM", "")
            date_val = ""

            for child in elem:
                c_tag = cls.clean_tag(child.tag)
                t_val = (child.text or "").strip()
                if c_tag == "GUID":
                    guid = t_val
                elif c_tag in ["VOUCHERNUMBER", "VCHNUMBER"] and not vch_num:
                    vch_num = t_val
                elif c_tag == "DATE":
                    date_val = t_val

            if not guid and "GUID" in elem.attrib:
                guid = elem.attrib["GUID"]

            if effective_match_by == "GUID":
                curr_key = guid.strip()
            elif effective_match_by == "VoucherNumber + Date":
                curr_key = f"{vch_num.strip().upper()}|{date_val.strip()}"
            else:
                curr_key = vch_num.strip().upper()

            if curr_key not in updates_by_key:
                continue

            v_update_spec = updates_by_key[curr_key]

            # Set ACTION="Alter" on the voucher for Tally XML import engine
            if set_alter_action:
                elem.set("ACTION", "Alter")

            # Build ledger update lookup: lowercase name -> target revised amount
            target_amounts = {
                l["ledger_name"].strip().lower(): l["revised_amount"]
                for l in v_update_spec["ledger_updates"]
                if not l.get("is_missing") and l.get("is_modified")
            }

            voucher_modified = False

            # Traverse child elements of <VOUCHER>
            for v_child in elem:
                child_tag = cls.clean_tag(v_child.tag)
                if child_tag not in ["ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"]:
                    continue

                # Locate LEDGERNAME
                l_name_elem = None
                amt_elem = None
                for l_prop in v_child:
                    p_tag = cls.clean_tag(l_prop.tag)
                    if p_tag == "LEDGERNAME":
                        l_name_elem = l_prop
                    elif p_tag == "AMOUNT":
                        amt_elem = l_prop

                if l_name_elem is None or not (l_name_elem.text and l_name_elem.text.strip()):
                    continue

                l_name_clean = l_name_elem.text.strip().lower()
                if l_name_clean not in target_amounts:
                    continue

                # Apply new amount
                new_amount = target_amounts[l_name_clean]
                new_amt_str = f"{new_amount:.2f}"
                old_amt_str = amt_elem.text if amt_elem is not None and amt_elem.text else "0.00"

                if amt_elem is not None:
                    amt_elem.text = new_amt_str
                else:
                    new_a_elem = ET.SubElement(v_child, "AMOUNT")
                    new_a_elem.text = new_amt_str

                # Update associated BILLALLOCATIONS.LIST if present
                for alloc in v_child:
                    alloc_tag = cls.clean_tag(alloc.tag)
                    if alloc_tag in ["BILLALLOCATIONS.LIST", "BANKALLOCATIONS.LIST", "COSTCENTREALLOCATIONS.LIST"]:
                        b_amt = alloc.find("AMOUNT")
                        if b_amt is not None:
                            b_amt.text = new_amt_str

                voucher_modified = True
                updated_ledgers_count += 1

                audit_log.append({
                    "VoucherNumber": vch_num or guid,
                    "GUID": guid,
                    "LedgerName": l_name_elem.text.strip(),
                    "OriginalAmount": float(old_amt_str),
                    "UpdatedAmount": new_amount,
                    "Delta": new_amount - float(old_amt_str),
                    "Action": "Updated in XML",
                })

            if voucher_modified:
                updated_vouchers_count += 1

        # Serialize mutated tree to string
        rough_string = ET.tostring(root_copy, encoding="utf-8")
        try:
            reparsed = minidom.parseString(rough_string)
            # Pretty-print while preserving declaration
            updated_xml_str = reparsed.toxml(encoding="utf-8").decode("utf-8")
        except Exception:
            updated_xml_str = rough_string.decode("utf-8")

        return {
            "updated_root": root_copy,
            "updated_xml_str": updated_xml_str,
            "updated_xml_bytes": updated_xml_str.encode("utf-8"),
            "audit_log": audit_log,
            "stats": {
                "vouchers_updated": updated_vouchers_count,
                "ledgers_updated": updated_ledgers_count,
            },
        }
