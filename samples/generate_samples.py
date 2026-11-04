"""
Sample Data Generator
Generates realistic multi-format test datasets covering all supported formats:
Excel (.xlsx with multiple sheets), CSV (with data quality anomalies),
XML (hierarchical with repeated elements), JSON (nested and flat),
TXT (delimited logs), and ZIP (bundle of datasets).
"""
import os
import json
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import pandas as pd
import numpy as np


def generate_all_samples(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Multi-sheet Excel workbook (sample_sales.xlsx)
    excel_path = target_dir / "sample_sales.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_orders = pd.DataFrame({
            "OrderID": [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010],
            "CustomerName": ["Acme Corp", "Globex Inc", "Initech LLC", "Umbrella Corp", "Wayne Ent", "Stark Ind", "Hooli", "Acme Corp", "Pied Piper", "Massive Dynamic"],
            "Region": ["North", "South", "East", "West", "North", "South", "East", "North", "West", "South"],
            "Amount": [1520.50, 840.00, 2300.75, 450.00, 12000.00, 3100.20, 95.00, 1520.50, 4800.00, 750.00],
            "OrderDate": ["2026-01-15", "16/01/2026", "2026-01-18", "19-01-2026", "2026-01-20", "2026-01-22", "23/01/2026", "2026-01-15", "2026-01-26", "2026-01-28"],
            "Status": ["Delivered", "Pending", "Delivered", "Cancelled", "Delivered", "Delivered", "Shipped", "Delivered", "Delivered", "Shipped"],
        })
        df_orders.to_excel(writer, sheet_name="Orders", index=False)

        df_customers = pd.DataFrame({
            "CustomerID": ["C-01", "C-02", "C-03", "C-04", "C-05"],
            "Company": ["Acme Corp", "Globex Inc", "Initech LLC", "Umbrella Corp", "Wayne Ent"],
            "ContactEmail": ["contact@acme.com", "info@globex.org", "sales@initech.com", None, "bruce@wayne.com"],
            "CreditLimit": [50000, 25000, 100000, 15000, 500000],
            "Tier": ["Gold", "Silver", "Platinum", "Bronze", "VIP"],
        })
        df_customers.to_excel(writer, sheet_name="Customers", index=False)

        df_inventory = pd.DataFrame({
            "SKU": ["SKU-101", "SKU-102", "SKU-103", "SKU-104", "SKU-105"],
            "ItemName": ["Industrial Widget", "Nano Component", "Sensor Matrix", "Quantum Relay", "Fiber Bus"],
            "StockOnHand": [120, 45, 0, 18, 95],
            "UnitPrice": [45.0, 180.0, 75.5, 320.0, 12.5],
        })
        df_inventory.to_excel(writer, sheet_name="Inventory", index=False)

    # 2. CSV with anomalies (sample_customers.csv)
    csv_path = target_dir / "sample_customers.csv"
    csv_data = pd.DataFrame({
        "ID": [101, 102, 103, 104, 105, 106, 107, 108, 109, 109],  # duplicate 109
        "Name": ["John Doe", "Jane Smith", "Bob Jones", "Alice Brown", "Charlie Davis", "Eva White", "Frank Miller", "Grace Hopper", "Alan Turing", "Alan Turing"],
        "RegistrationDate": ["2026-01-05", "06/01/2026", "2026-01-07", "08-01-2026", "2026-01-09", "10/01/2026", "2026-01-11", "2026-01-12", "13-01-2026", "13-01-2026"],
        "Balance": [250.0, 1420.5, None, 89.9, 5400.0, 310.2, 75.0, None, 92000.0, 92000.0],  # missing values + 92000 outlier
        "Country": ["USA", "Canada", "UK", "Germany", "USA", "France", "Japan", "USA", "UK", "UK"],
        "IsActive": [True, True, False, True, True, False, True, True, True, True],
    })
    csv_data.to_csv(csv_path, index=False)

    # 3. Hierarchical XML with repeated elements (sample_data.xml)
    xml_path = target_dir / "sample_data.xml"
    root = ET.Element("TRANSACTIONS", {"version": "2.4", "source": "ERP_System"})
    meta = ET.SubElement(root, "HEADER")
    ET.SubElement(meta, "TIMESTAMP").text = "2026-11-03T10:30:00"
    ET.SubElement(meta, "ORGANIZATION").text = "Global Enterprises Ltd"

    records = ET.SubElement(root, "RECORDLIST")
    for i in range(1, 6):
        rec = ET.SubElement(records, "RECORD", {"id": f"REC-{1000+i}", "type": "INVOICE"})
        ET.SubElement(rec, "VOUCHERNUMBER").text = f"INV-2026-{100+i}"
        ET.SubElement(rec, "DATE").text = f"2026-02-0{i}"
        ET.SubElement(rec, "PARTYNAME").text = f"Client Corp {chr(64+i)}"
        ET.SubElement(rec, "AMOUNT").text = str(1500 * i + 250.50)
        
        items = ET.SubElement(rec, "LINEITEMS")
        for j in range(1, 3):
            item = ET.SubElement(items, "ITEM", {"line": str(j)})
            ET.SubElement(item, "DESCRIPTION").text = f"Service Package {j}"
            ET.SubElement(item, "RATE").text = str(500 * j)
            ET.SubElement(item, "QUANTITY").text = str(j)

    xml_str = minidom.parseString(ET.tostring(root, "utf-8")).toprettyxml(indent="  ")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_str)

    # 4. JSON with nested objects (sample_inventory.json)
    json_path = target_dir / "sample_inventory.json"
    json_data = {
        "catalog_name": "Global Hardware Inventory",
        "exported_at": "2026-11-03T12:00:00Z",
        "total_categories": 3,
        "items": [
            {"item_id": "ITM-001", "name": "Precision Server Rack 42U", "category": "Infrastructure", "stock": 14, "cost": 1250.00, "tags": ["server", "rack", "datacenter"]},
            {"item_id": "ITM-002", "name": "Optical Transceiver 100G", "category": "Networking", "stock": 85, "cost": 320.50, "tags": ["optics", "fiber", "highspeed"]},
            {"item_id": "ITM-003", "name": "Managed Switch 48-Port", "category": "Networking", "stock": 22, "cost": 2100.00, "tags": ["switch", "cisco", "poe"]},
            {"item_id": "ITM-004", "name": "UPS Power Backup 3000VA", "category": "Power", "stock": 7, "cost": 1780.00, "tags": ["ups", "battery", "redundancy"]},
            {"item_id": "ITM-005", "name": "Enterprise NVMe SSD 3.84TB", "category": "Storage", "stock": 42, "cost": 490.00, "tags": ["nvme", "storage", "fast"]},
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    # 5. Delimited Text File (sample_log.txt)
    txt_path = target_dir / "sample_log.txt"
    txt_content = """Timestamp|Level|Service|Message|ResponseTimeMs
2026-11-03 08:00:12|INFO|AuthService|User login successful user_id=4021|12
2026-11-03 08:01:45|WARN|PaymentGateway|Latency threshold exceeded gateway_id=stripe|420
2026-11-03 08:02:10|INFO|OrderService|Order placed order_id=ORD-9912|85
2026-11-03 08:03:33|ERROR|InventoryService|Stock allocation failed for SKU-8841|110
2026-11-03 08:05:00|INFO|BillingService|Invoice generated inv_id=INV-4412|35
2026-11-03 08:06:21|INFO|AuditLogger|Daily batch reconciliation complete|2540
"""
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content.strip())

    # 6. ZIP bundle containing supported files (sample_archive.zip)
    zip_path = target_dir / "sample_archive.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(excel_path, arcname="sales_report.xlsx")
        zf.write(csv_path, arcname="customers_clean.csv")
        zf.write(json_path, arcname="catalog.json")
        zf.write(xml_path, arcname="erp_records.xml")
        zf.write(txt_path, arcname="system_events.txt")

    print(f"Successfully generated all 6 sample datasets in: {target_dir}")


if __name__ == "__main__":
    generate_all_samples(Path(__file__).resolve().parent)
