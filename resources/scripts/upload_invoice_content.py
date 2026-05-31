"""
upload_invoice_content.py — Számla-dokumentum feltöltő a UNICEF Számla POC-hez

Az eredeti upload_content.py (szerződés POC) adaptált változata. Egy számla-fájlt
(PDF, opcionálisan docx) tölt fel Salesforce ContentVersion-ként, és hozzácsatolja
egy Supplier_Invoice__c rekordhoz a FirstPublishLocationId mezőn keresztül.

KÜLÖNBSÉGEK az eredeti (szerződés) scripthez képest:
  1) PDF-et fogad el (az eredeti csak .docx-et) — a számlák PDF-ben érkeznek.
  2) NEM ellenőrzi a '800' (Contract) Id-prefixet — a parent egy custom objektum
     (Supplier_Invoice__c), aminek a key-prefixe org-függő. Csak a 15/18 karakteres
     hosszt validálja.

POC-szintű hitelesítés: username + password + security token a .env fájlból.
(Production: JWT Bearer flow Connected App private key-jel.)

Használat:
    python3 upload_invoice_content.py <invoice_record_id> <file_path> [title]

Argumentumok:
    invoice_record_id : a Supplier_Invoice__c rekord Id-ja (15 vagy 18 karakter)
    file_path         : a feltöltendő számla fájl elérési útja (.pdf vagy .docx)
    title             : opcionális megjelenítési cím (default: a fájlnév kiterjesztés nélkül)

Környezeti változók (.env a script mappájában):
    SF_USERNAME, SF_PASSWORD, SF_TOKEN, SF_DOMAIN (default 'test')

Kimenet (siker, JSON a stdout-ra):
    {"success": true, "contentVersionId": "068...", "contentDocumentId": "069...", ...}

Kilépési kódok:  0 siker · 1 argumentum/credential hiba · 2 Salesforce API hiba
"""

import os
import sys
import time
import json
import base64
from pathlib import Path

try:
    from dotenv import load_dotenv
    from simple_salesforce import Salesforce
except ImportError as e:
    print(json.dumps({
        "success": False,
        "error": f"Missing dependency: {e.name}. Run: pip install --break-system-packages simple-salesforce python-dotenv",
        "errorType": "ImportError"
    }))
    sys.exit(1)

# Engedélyezett kiterjesztések — a számlák jellemzően PDF-ek
ALLOWED_EXTENSIONS = ('.pdf', '.docx')


def fail(message: str, error_type: str = "Error", exit_code: int = 1):
    print(json.dumps({"success": False, "error": message, "errorType": error_type}))
    sys.exit(exit_code)


def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        fail("Usage: upload_invoice_content.py <invoice_record_id> <file_path> [title]", "ArgumentError")

    invoice_id = sys.argv[1]
    file_path = Path(sys.argv[2])
    title = sys.argv[3] if len(sys.argv) == 4 else file_path.stem

    if not file_path.exists():
        fail(f"File not found: {file_path}", "FileNotFoundError")

    if not file_path.name.lower().endswith(ALLOWED_EXTENSIONS):
        fail(f"File must be one of {ALLOWED_EXTENSIONS} (got: {file_path.suffix})", "InvalidFileType")

    # A custom objektum key-prefixe org-függő, ezért csak a hosszt ellenőrizzük.
    if len(invoice_id) not in (15, 18) or not invoice_id.isalnum():
        fail(f"Invalid Salesforce record Id format: {invoice_id} (expected 15 or 18 alphanumeric chars)",
             "InvalidRecordId")

    # ---- Credentials ----
    script_dir = Path(__file__).parent
    env_file = script_dir / '.env'
    if not env_file.exists():
        env_file = script_dir / 'creds.env.txt'
    if not env_file.exists():
        fail(f"Credentials file not found. Expected: {script_dir}/.env or {script_dir}/creds.env.txt",
             "CredentialsFileNotFound")

    load_dotenv(env_file)
    sf_username = os.getenv('SF_USERNAME')
    sf_password = os.getenv('SF_PASSWORD')
    sf_token = os.getenv('SF_TOKEN')
    sf_domain = os.getenv('SF_DOMAIN', 'test')

    if not all([sf_username, sf_password, sf_token]):
        fail("Missing one or more credentials (SF_USERNAME, SF_PASSWORD, SF_TOKEN) in env file",
             "MissingCredentials")

    # ---- Login ----
    try:
        t_login_start = time.time()
        sf = Salesforce(username=sf_username, password=sf_password,
                        security_token=sf_token, domain=sf_domain)
        t_login = time.time() - t_login_start
    except Exception as e:
        fail(f"Salesforce login failed: {e}", type(e).__name__, exit_code=2)

    # ---- Read + base64 ----
    try:
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        base64_data = base64.b64encode(file_bytes).decode('utf-8')
        file_size = len(file_bytes)
    except Exception as e:
        fail(f"File read failed: {e}", type(e).__name__)

    # ---- ContentVersion insert + auto-link ----
    try:
        t_upload_start = time.time()
        result = sf.ContentVersion.create({
            'Title': title,
            'PathOnClient': file_path.name,
            'VersionData': base64_data,
            'FirstPublishLocationId': invoice_id
        })
        t_upload = time.time() - t_upload_start
    except Exception as e:
        fail(f"ContentVersion insert failed: {e}", type(e).__name__, exit_code=2)

    content_version_id = result['id']

    try:
        cv_record = sf.query(
            f"SELECT ContentDocumentId FROM ContentVersion WHERE Id = '{content_version_id}'"
        )
        content_document_id = cv_record['records'][0]['ContentDocumentId']
    except Exception:
        content_document_id = None

    print(json.dumps({
        "success": True,
        "contentVersionId": content_version_id,
        "contentDocumentId": content_document_id,
        "loginSeconds": round(t_login, 2),
        "uploadSeconds": round(t_upload, 2),
        "fileSize": file_size,
        "title": title,
        "invoiceId": invoice_id
    }))


if __name__ == "__main__":
    main()
