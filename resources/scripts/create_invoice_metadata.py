"""
create_invoice_metadata.py — Supplier_Invoice__c + Cost_Center__c metaadat-létrehozó
UNICEF Beszállítói Számla POC

Programatikusan létrehozza a két custom objektumot és az összes mezőt a
Salesforce TOOLING API-n keresztül, ugyanazzal a hitelesítési módszerrel,
amit az upload_content.py / download_content.py is használ (.env, simple-salesforce).

FONTOS: a rekord-szintű MCP connector (createSobjectRecord) NEM tud metaadatot
létrehozni — ezért használjuk a Tooling API-t egy scriptből.

Használat:
    pip install --break-system-packages simple-salesforce python-dotenv requests
    python3 create_invoice_metadata.py

A .env fájlt ugyanabba a mappába tedd, mint a scriptet (SF_USERNAME, SF_PASSWORD,
SF_TOKEN, SF_DOMAIN=test). Ugyanaz a .env, amit a contract POC használ.

A script idempotens: ha egy objektum/mező már létezik, kihagyja és továbblép.

Megjegyzés a FLS-ről és a page layoutról:
    A Tooling API-val létrehozott mezők alapból csak a System Administrator
    profilon láthatók, és NEM kerülnek rá automatikusan a page layoutra.
    A deploy után kézzel (vagy külön lépésben) kell:
      1) a mezőket a page layoutra húzni,
      2) a jóváhagyó felhasználók profiljának field-level security-t adni.
    Lásd a DEPLOY_PLAN dokumentum "Deploy utáni teendők" szakaszát.
"""

import os
import sys
import json
from pathlib import Path

try:
    import requests
    from dotenv import load_dotenv
    from simple_salesforce import Salesforce
except ImportError as e:
    print(f"Hiányzó függőség: {e.name}. Futtasd: "
          f"pip install --break-system-packages simple-salesforce python-dotenv requests")
    sys.exit(1)


# =============================================================================
# OBJEKTUM- ÉS MEZŐDEFINÍCIÓK
# =============================================================================

# ---- 1. Cost_Center__c objektum (a számla parent-je a költséghelyhez) ----
COST_CENTER_OBJECT = {
    "fullName": "Cost_Center__c",
    "metadata": {
        "label": "Költséghely",
        "pluralLabel": "Költséghelyek",
        "nameField": {"type": "Text", "label": "Költséghely neve"},
        "deploymentStatus": "Deployed",
        "sharingModel": "ReadWrite",
    },
}

COST_CENTER_FIELDS = [
    {"name": "Code__c", "metadata": {"type": "Text", "label": "Kód", "length": 40}},
    {"name": "Active__c", "metadata": {"type": "Checkbox", "label": "Aktív", "defaultValue": True}},
]

# ---- 2. Supplier_Invoice__c objektum (a beszállítói számla) ----
INVOICE_OBJECT = {
    "fullName": "Supplier_Invoice__c",
    "metadata": {
        "label": "Beszállítói számla",
        "pluralLabel": "Beszállítói számlák",
        # Text névmező: a Name = "szolgáltatás + dátum", az ügynök tölti ki.
        # Szándékosan NEM auto-number, mert két record viselheti ugyanazt a nevet
        # (ugyanaz a szolgáltatás ugyanazon a napon, eltérő verzióval).
        "nameField": {"type": "Text", "label": "Számla megnevezése"},
        "deploymentStatus": "Deployed",
        "sharingModel": "ReadWrite",
    },
}

INVOICE_FIELDS = [
    # ---- Kapcsolatok ----
    {"name": "Supplier_Account__c", "metadata": {
        "type": "Lookup", "label": "Beszállító (Account)",
        "referenceTo": "Account",
        "relationshipName": "Supplier_Invoices",
        "relationshipLabel": "Beszállítói számlák"}},
    {"name": "Supplier_Contact__c", "metadata": {
        "type": "Lookup", "label": "Beszállító (Contact)",
        "referenceTo": "Contact",
        "relationshipName": "Supplier_Invoices",
        "relationshipLabel": "Beszállítói számlák"}},
    {"name": "Cost_Center__c", "metadata": {
        "type": "Lookup", "label": "Költséghely",
        "referenceTo": "Cost_Center__c",
        "relationshipName": "Supplier_Invoices",
        "relationshipLabel": "Beszállítói számlák"}},
    {"name": "Area_Approver__c", "metadata": {
        "type": "Lookup", "label": "Terület jóváhagyója",
        "referenceTo": "User",
        "relationshipName": "Approver_Supplier_Invoices",
        "relationshipLabel": "Jóváhagyandó beszállítói számlák"}},

    # ---- Számla fejadatok (a PDF-ből kinyerve) ----
    {"name": "Invoice_Number__c", "metadata": {"type": "Text", "label": "Számlasorszám", "length": 80}},
    {"name": "Issue_Date__c", "metadata": {"type": "Date", "label": "Kiállítás kelte"}},
    {"name": "Fulfillment_Date__c", "metadata": {"type": "Date", "label": "Teljesítés kelte"}},
    {"name": "Due_Date__c", "metadata": {"type": "Date", "label": "Fizetési határidő"}},
    {"name": "Service_Description__c", "metadata": {"type": "Text", "label": "Szolgáltatás megnevezése", "length": 255}},
    {"name": "Net_Amount__c", "metadata": {"type": "Currency", "label": "Nettó összeg", "precision": 18, "scale": 2}},
    {"name": "VAT_Amount__c", "metadata": {"type": "Currency", "label": "ÁFA összeg", "precision": 18, "scale": 2}},
    {"name": "Gross_Amount__c", "metadata": {"type": "Currency", "label": "Bruttó összeg", "precision": 18, "scale": 2}},

    # ---- Snapshot mezők (a rögzítéskori állapot — audit) ----
    {"name": "Supplier_Name__c", "metadata": {"type": "Text", "label": "Beszállító neve (snapshot)", "length": 255}},
    {"name": "Supplier_VAT_Number__c", "metadata": {"type": "Text", "label": "Beszállító adószáma (snapshot)", "length": 20}},

    # ---- Folyamat-mezők ----
    {"name": "Area__c", "metadata": {
        "type": "Picklist", "label": "Terület",
        "valueSet": {"valueSetDefinition": {"sorted": False, "value": [
            {"fullName": "Fundraising", "label": "Fundraising", "default": False},
            {"fullName": "Advocacy", "label": "Advocacy", "default": False},
            {"fullName": "Communications", "label": "Communications", "default": False},
            {"fullName": "Finance", "label": "Finance", "default": False},
        ]}}}},
    {"name": "Orderer__c", "metadata": {
        "type": "Picklist", "label": "Megrendelő",
        # POC: karbantartott picklist (nem minden megrendelőnek van SF-licence).
        # Seed-értékek — a valós nevekkel bővítendő.
        "valueSet": {"valueSetDefinition": {"sorted": True, "value": [
            {"fullName": "Nagy Anna", "label": "Nagy Anna", "default": False},
            {"fullName": "Kiss Péter", "label": "Kiss Péter", "default": False},
            {"fullName": "Szabó Júlia", "label": "Szabó Júlia", "default": False},
            {"fullName": "Tóth Gábor", "label": "Tóth Gábor", "default": False},
            {"fullName": "Egyéb", "label": "Egyéb", "default": False},
        ]}}}},
    {"name": "Approval_Status__c", "metadata": {
        "type": "Picklist", "label": "Jóváhagyási státusz",
        "valueSet": {"valueSetDefinition": {"sorted": False, "value": [
            {"fullName": "Betöltve", "label": "Betöltve", "default": True},
            {"fullName": "Területvezetői jóváhagyásra vár", "label": "Területvezetői jóváhagyásra vár", "default": False},
            {"fullName": "Pénzügyi igazgatói jóváhagyásra vár", "label": "Pénzügyi igazgatói jóváhagyásra vár", "default": False},
            {"fullName": "Jóváhagyva", "label": "Jóváhagyva", "default": False},
            {"fullName": "Elutasítva", "label": "Elutasítva", "default": False},
        ]}}}},
    {"name": "Version_Number__c", "metadata": {"type": "Number", "label": "Verziószám", "precision": 3, "scale": 0}},
    {"name": "Source_ContentVersion_Id__c", "metadata": {"type": "Text", "label": "Forrás dokumentum (ContentVersion Id)", "length": 18}},
]


# =============================================================================
# TOOLING API SEGÉDFÜGGVÉNYEK
# =============================================================================

def load_sf():
    script_dir = Path(__file__).parent
    env_file = script_dir / '.env'
    if not env_file.exists():
        env_file = script_dir / 'creds.env.txt'
    if not env_file.exists():
        print(json.dumps({"success": False, "error": f"Nincs .env a {script_dir} mappában"}))
        sys.exit(1)
    load_dotenv(env_file)
    sf = Salesforce(
        username=os.getenv('SF_USERNAME'),
        password=os.getenv('SF_PASSWORD'),
        security_token=os.getenv('SF_TOKEN'),
        domain=os.getenv('SF_DOMAIN', 'test'),
    )
    return sf


def make_poster(sf):
    tooling_url = f"{sf.base_url}tooling/sobjects/"
    headers = {
        "Authorization": f"Bearer {sf.session_id}",
        "Content-Type": "application/json",
    }

    def post(sobject_type, full_name, metadata):
        payload = {"FullName": full_name, "Metadata": metadata}
        r = requests.post(f"{tooling_url}{sobject_type}/", headers=headers, json=payload)
        if r.status_code in (200, 201):
            return "created"
        # Hibaelemzés — duplikátum = már létezik, nem hiba
        try:
            err = r.json()
            text = json.dumps(err, ensure_ascii=False)
        except Exception:
            text = r.text
        if any(k in text for k in ("DUPLICATE", "already", "duplicate value", "FIELD_INTEGRITY")):
            if "DUPLICATE" in text or "already" in text:
                return "exists"
        print(f"   ⚠ HIBA ({full_name}): {text}")
        return "error"

    return post


# =============================================================================
# FŐ FOLYAMAT
# =============================================================================

def main():
    sf = load_sf()
    post = make_poster(sf)

    print("== UNICEF Beszállítói Számla POC — metaadat-létrehozás ==\n")

    # 1) Cost_Center__c objektum ELŐBB (mert a számla lookup-ol rá)
    print("1) Cost_Center__c objektum")
    status = post("CustomObject", COST_CENTER_OBJECT["fullName"], COST_CENTER_OBJECT["metadata"])
    print(f"   → {status}")
    for f in COST_CENTER_FIELDS:
        full = f"Cost_Center__c.{f['name']}"
        s = post("CustomField", full, f["metadata"])
        print(f"   • {f['name']}: {s}")

    # 2) Supplier_Invoice__c objektum
    print("\n2) Supplier_Invoice__c objektum")
    status = post("CustomObject", INVOICE_OBJECT["fullName"], INVOICE_OBJECT["metadata"])
    print(f"   → {status}")

    # 3) Supplier_Invoice__c mezők
    print("\n3) Supplier_Invoice__c mezők")
    for f in INVOICE_FIELDS:
        full = f"Supplier_Invoice__c.{f['name']}"
        s = post("CustomField", full, f["metadata"])
        print(f"   • {f['name']}: {s}")

    print("\n== Kész. ==")
    print("NE FELEJTSD a deploy utáni teendőket:")
    print("  1) Mezők a page layoutra (Setup → Object Manager → Supplier_Invoice__c → Page Layouts)")
    print("  2) Field-level security a jóváhagyó profiloknak")
    print("  3) (Opcionális) Tab létrehozása a navigációhoz")
    print("  Lásd: DEPLOY_PLAN_Supplier_Invoice.md")


if __name__ == "__main__":
    main()
