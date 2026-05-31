---
name: szamla-rogzites
description: "Beszállítói (kimenő) számlák feldolgozása a UNICEF Magyarországnál: PDF-számlák beolvasása, strukturált Supplier_Invoice__c rekord létrehozása Salesforce-ban a beszállító Account+Contact alatt, a forrás-PDF csatolása ContentVersion-ként, majd a finance officer általi terület-kiválasztás és jóváhagyás-indítás előkészítése. Trigger-szavak: 'rögzítsd a számlát', 'dolgozd fel a számlát', 'számla feldolgozás', 'töltsd be a számlát', 'beszállítói számla', 'új számla verzió', 'újraszámlázás'. Lekérdezéshez: 'milyen számláink vannak', 'beszállító számlái', 'gazdátlan számlák', 'jóváhagyásra váró számlák'. NE használd adományozói szerződésekre (arra a szerzodes-keszites skill való), sem általános Salesforce-keresésre."
---

# Beszállítói számla-rögzítés — UNICEF Magyarország

## A skill célja

Beszállítói (accounts payable, **kimenő**) számlák feldolgozása. Egy AI-ügynök
beolvas egy vagy több PDF-számlát, kinyeri az adatokat, **emberi ellenőrzés után**
strukturált `Supplier_Invoice__c` rekordot hoz létre a Salesforce-ban a beszállító
alatt, és csatolja a forrás-PDF-et. Az approval-folyamatot a finance officer
indítja kézzel (lásd "Mit NE csinálj").

> **Viszony a szerződés-skillhez:** ez a skill a `szerzodes-keszites` POC v2.5
> bevált infrastruktúráját hasznosítja újra: ugyanaz a `SANDBOX_BASE_URL`, ugyanaz
> a `.env`-es Salesforce-hitelesítés, ugyanaz a `createSobjectRecord` + Python REST
> upload minta. A különbség: itt **adatkinyerés** történik egy strukturálatlan
> PDF-ből (nem sablon-kitöltés), és **kimenő** számláról van szó (nem bejövő
> adományról).

## ARCHITEKTÚRA (POC v1)

- `Supplier_Invoice__c` rekord létrehozása: **Hosted MCP `createSobjectRecord`** a `UNICEF Salesforce` connectoron
- `ContentVersion` (a PDF) feltöltés: **Python REST script** — `upload_invoice_content.py` (PDF-támogatás!)
- Beszállító-azonosítás: **adószám (VAT) alapján** SOQL/`find`, az Account-on
- Approval: a finance officer **kézzel** indítja, miután a területet kiválasztotta — a skill NEM submitál
- Lekérdezések: `soqlQuery`, `find`, `getRelatedRecords`

**TILOS** (a szerződés-skillel azonosan): `UNICEF Custom Tools` connector, `ContractDocumentService` Apex. Ha látszanának a tool-listán, NE használd.

## SANDBOX KÖRNYEZET — URL-konstans

```
SANDBOX_BASE_URL = https://unicefhungariannationalcommittee--dev2.sandbox.lightning.force.com
```

| Cél | URL-minta |
|---|---|
| Számla rekord | `{SANDBOX_BASE_URL}/lightning/r/Supplier_Invoice__c/{id}/view` |
| Account | `{SANDBOX_BASE_URL}/lightning/r/Account/{id}/view` |
| Contact | `{SANDBOX_BASE_URL}/lightning/r/Contact/{id}/view` |
| ContentVersion letöltés | `{SANDBOX_BASE_URL}/sfc/servlet.shepherd/version/download/{cvId}` |

Mielőtt URL-t küldesz: ellenőrizd, hogy tartalmazza a `unicefhungariannationalcommittee--dev2` stringet. Ha a tool-válasz más subdomaint ad, akkor is a fenti konstanst használd.

## Adatmodell

```
Account: "NetCore Systems Zrt." (RecordType: Organization)
   ├── VAT_Number__c (= adószám)  ← EZ A BESZÁLLÍTÓ-AZONOSÍTÓ KULCS
   └── Billing-mezők
        │ 1-az-1 NPSP-kapcsolat
        ▼
Contact: "NetCore Systems Zrt." (LastName = cégnév)
        │ a beszállító számlái (Supplier_Contact__c related list)
        ▼
Supplier_Invoice__c: "Salesforce licencbővítés – 2026-05-10"
   ├── Supplier_Account__c  → Account
   ├── Supplier_Contact__c  → Contact (a Contact alatt is megjelenik)
   ├── Supplier_Name__c, Supplier_VAT_Number__c  (SNAPSHOT)
   ├── Invoice_Number__c, Issue_Date__c, Fulfillment_Date__c, Due_Date__c
   ├── Net_Amount__c, VAT_Amount__c, Gross_Amount__c
   ├── Service_Description__c
   ├── Area__c (a finance officer tölti), Approval_Status__c
   ├── Cost_Center__c, Orderer__c (a TERÜLETVEZETŐ tölti jóváhagyáskor)
   └── Version_Number__c
```

**Snapshot-elv:** a `Supplier_Name__c` és `Supplier_VAT_Number__c` a számla rögzítéskori
állapotát rögzíti. Ha a beszállító adata később változik, a számlán az eredeti marad (audit).

---

# FLOW: SZÁMLA-RÖGZÍTÉS — lépésről lépésre

## 1. lépés — A felhasználó átadja a PDF-(ek)et

> *"Rögzítsd ezt a 3 beszállítói számlát."*

A PDF-ek a Cowork uploads mappában vannak. Ha nincs fájl, kérdezd meg, hova tette.

## 2. lépés — Adatkinyerés (számlánként)

Olvasd ki minden PDF-ből:
- beszállító **neve** és **adószáma**
- **számlasorszám**
- **kiállítás / teljesítés / fizetési határidő** dátuma
- **nettó / ÁFA / bruttó** összeg
- **szolgáltatás** rövid megnevezése (a tételsorokból összegezve — ez kerül a Name-be)

**KRITIKUS — soha ne találgass.** Ha egy mező (pl. adószám, összeg) nem olvasható
ki egyértelműen, jelöld **hiányként/bizonytalanként** — NE tölts ki kitalált értéket.
(A demón a 4-es számlán pl. hiányzott az adószám.)

## 3. lépés — Beszállító-azonosítás ADÓSZÁM alapján

**Először az adószámmal** keresd, létezik-e már a beszállító:

```
soqlQuery: SELECT Id, Name, VAT_Number__c, RecordType.Name FROM Account WHERE VAT_Number__c = '<adószám>'
```

- **Ha van találat** → ahhoz kötöd a számlát (kell az Account Id + a hozzá tartozó 1-az-1 Contact Id).
  A Contact lekérése:
  ```
  soqlQuery: SELECT Id, LastName FROM Contact WHERE AccountId = '<accountId>'
  ```
- **Ha NINCS találat** → **NE hozd létre némán.** Mutasd meg a felhasználónak:
  > *"Ehhez a számlához nem találtam meglévő beszállítót (adószám: …, név: …). Létrehozzam az új Account + Contact párt?"*
  Csak megerősítés után hozd létre (lásd "Beszállító-létrehozás" szakasz).

Ha az adószám hiányzott a PDF-ből, **névre** is kereshetsz (`find`), de jelezd a bizonytalanságot, és kérdezz vissza.

## 4. lépés — Strukturált összegzés + emberi kapu

Mutass egy **táblázatos összegzést** az összes számláról: beszállító, adószám, sorszám,
dátumok, nettó/ÁFA/bruttó, javasolt szolgáltatás-név, és a beszállító státusza
(létező / létrehozandó). **Külön jelöld**, amit nem találtál vagy bizonytalan.

> *"Így olvastam ki a számlákat. A pirossal jelölt mezőket nem találtam — ezeket pótold, vagy hagyod üresen? Ha minden stimmel, létrehozom a rekordokat."*

**NE hozz létre rekordot a megerősítés előtt.** Ez AP-folyamat — a rossz összeg vagy beszállító valódi pénzügyi kockázat.

## 5. lépés — A számla rekord létrehozása

Számlánként, **kizárólag** a `createSobjectRecord` MCP-vel a `UNICEF Salesforce` connectoron:

```json
{
  "sobject-name": "Supplier_Invoice__c",
  "body": {
    "Name": "<szolgáltatás> – <teljesítés dátuma>",
    "Supplier_Account__c": "<Account Id>",
    "Supplier_Contact__c": "<Contact Id>",
    "Supplier_Name__c": "<Account.Name — SNAPSHOT>",
    "Supplier_VAT_Number__c": "<adószám — SNAPSHOT>",
    "Invoice_Number__c": "<számlasorszám>",
    "Issue_Date__c": "<YYYY-MM-DD>",
    "Fulfillment_Date__c": "<YYYY-MM-DD>",
    "Due_Date__c": "<YYYY-MM-DD>",
    "Service_Description__c": "<szolgáltatás leírás>",
    "Net_Amount__c": <szám>,
    "VAT_Amount__c": <szám>,
    "Gross_Amount__c": <szám>,
    "Approval_Status__c": "Betöltve",
    "Version_Number__c": 1
  }
}
```

**Névképzés:** `Name = "{Service_Description__c} – {Fulfillment_Date__c}"`, **max 80 karakter**
(a szolgáltatás-leírást szükség szerint rövidítsd). Pl. `Microsoft 365 licenc – 2026-04-30`.

**Amit NEM töltesz ki rögzítéskor:** `Area__c` (a finance officer adja a riportban),
`Cost_Center__c`, `Orderer__c` (a területvezető adja jóváhagyáskor), `Area_Approver__c` (a Flow tölti).

A Salesforce visszaadja a rekord Id-ját — ez kell a 6. lépéshez.

## 6. lépés — A PDF csatolása (KÖTELEZŐ, Python REST)

**Kizárólag** az `upload_invoice_content.py` scripttel (PDF-támogatással). NE használj MCP-t vagy Custom Tools-t fájlfeltöltésre.

```bash
python3 <scripts könyvtár>/upload_invoice_content.py \
  "<supplier_invoice_id_az_5_lépésből>" \
  "<a számla PDF teljes elérési útja>" \
  "Számla - <beszállító> <sorszám>"
```

A script JSON-t ad vissza a `contentVersionId`-vel. Opcionálisan írd vissza a rekord
`Source_ContentVersion_Id__c` mezőjébe (`updateSobjectRecord`).

## 7. lépés — Átadás a finance officernek

A rögzítés után **a folyamat a felhasználóhoz kerül**, NEM indítasz approvalt. Írd meg:

> *"Létrehoztam N számla rekordot, mindegyikhez csatoltam a PDF-et. Következő lépés a te kezedben:
> (1) nézd át a 'Frissen betöltött számlák' riportban, (2) válaszd ki mindegyikhez a **Területet**,
> (3) majd indítsd el a jóváhagyást a 'Submit for Approval' gombbal. A linkek: …"*

Adj rekord-linkeket a `SANDBOX_BASE_URL` szerint.

---

# Beszállító-létrehozás (al-flow, csak megerősítés után)

Ha a 3. lépésben nincs adószám-találat ÉS a felhasználó kéri:

1. **Account** (`createSobjectRecord`, `sobject-name: "Account"`): `Name` = cégnév,
   `VAT_Number__c` = adószám, RecordType: Organization, Billing-mezők ha kiolvashatók.
2. **Contact** (`sobject-name: "Contact"`): `LastName` = cégnév, `AccountId` = az új Account Id.
   (A UNICEF 1-az-1 modell — a céget egy Contact reprezentálja.)
3. Ezután térj vissza az 5. lépéshez a számla létrehozásához.

NE hozz létre beszállítót automatikusan, megerősítés nélkül — a duplikátum (ugyanaz a
cég kétszer) tönkreteszi a riportokat. Az adószám a duplikátum-kulcs.

---

# Verziózás — újraszámlázás és javítás

A szerződés-flow mintáját követi. **Két eset van**, és élesen meg kell különböztetni:

### A) A számla adatai NEM változnak — csak terület/megrendelő/költséghely
→ **A meglévő rekordot szerkeszd** (`updateSobjectRecord`). NEM új rekord, NEM új verzió.
Ez a tipikus eset, ha pl. csak a területet pontosítják.

### B) A beszállító ÚJ számlát állít ki (mert egy adat — összeg, sorszám — nem stimmelt)
→ **Új rekordot hozz létre**, NE módosítsd a régit:
1. Keresd meg a meglévő rekord(ok)at: ugyanaz a beszállító + ugyanaz a `Name` (szolgáltatás + dátum).
2. Az új `Version_Number__c` = a max meglévő verzió + 1.
3. Hozz létre egy **új** `Supplier_Invoice__c`-t (5. lépés), **ugyanazzal a Name-mel**, az emelt verzióval.
4. Töltsd fel az **új PDF-et** mint új ContentVersion (6. lépés).
5. Így a beszállító Contactja alatt **két azonos nevű** számla lesz, eltérő Id-val és ContentVersion-nel.
   Csak az egyik lesz a végén `Jóváhagyva` — a másik `Elutasítva` marad.

Ez akkor is így működik, ha egy számlát az approval során **elutasítottak**: nem
„újraélesztjük" a rekordot, hanem az új (helyes) számláról új verziós rekord készül.

---

# Lekérdezési flow (read-only)

Trigger: "milyen számláink vannak", "gazdátlan számlák", "jóváhagyásra váró".

- **Gazdátlan (terület nélküli):** `SELECT Id, Name, Gross_Amount__c FROM Supplier_Invoice__c WHERE Area__c = null`
- **Jóváhagyásra váró:** `... WHERE Approval_Status__c = 'Területvezetői jóváhagyásra vár'` (csoportosítva `Area__c` szerint — ez mutatja, kinél áll)
- **Egy beszállító számlái:** `getRelatedRecords` az Account-on a `Supplier_Invoices` relationship-pel, vagy SOQL `WHERE Supplier_Contact__c = '<contactId>'`

Read-only flow-ban NE hozz létre / módosíts rekordot.

---

# Mit NE csinálj

- ❌ **NE indíts approvalt** (`Submit for Approval`) — ezt a finance officer teszi kézzel, miután a területet kiválasztotta. A skill itt megáll.
- ❌ **NE találgass** hiányzó adatot (adószám, összeg) — jelöld hiányként, kérdezz.
- ❌ **NE hozz létre beszállítót** megerősítés nélkül.
- ❌ **NE tölts ki** `Area__c`, `Cost_Center__c`, `Orderer__c` mezőt rögzítéskor — ezek a humán lépésekhez tartoznak.
- ❌ **NE használj** `UNICEF Custom Tools`-t vagy `ContractDocumentService`-t.
- ❌ **NE hozz létre metaadatot** (mező, objektum) — az a deploy-terv és a CLI ügynök dolga.

# Hibakezelés

- `INVALID_FIELD: <mező>__c` → a metaadat nincs deploy-olva (lásd DEPLOY_PLAN).
- `INSUFFICIENT_ACCESS_OR_READONLY` → a `UNICEF_Szamla_POC` permission set nincs kiosztva.
- `FIELD_INTEGRITY_EXCEPTION` lookupnál → rossz parent Id (Account vs Contact felcserélve).
- `upload_invoice_content.py` hibák: `MissingCredentials`, `InvalidRecordId`, `InvalidFileType` (csak .pdf/.docx), `ContentVersion insert failed`.

# Salesforce-side setup (referencia)

- Objektumok: `Supplier_Invoice__c`, `Cost_Center__c` (lásd DEPLOY_PLAN)
- Permission set: `UNICEF_Szamla_POC`
- Approval: `UNICEF Beszállítói Számla Jóváhagyás` process + `Area_Approver__c`-t kitöltő Flow + validation rule (lásd APPROVAL_PROCESS_SETUP)
- Upload script: `upload_invoice_content.py` (a szerződés `upload_content.py` PDF-es változata)
- Aktív connector: `UNICEF Salesforce`. Tiltott: `UNICEF Custom Tools`.

# Fejlesztői megjegyzés

POC v1 (2026.05): a `szerzodes-keszites` v10 infrastruktúrájára épül. Forint-only
(devizát nem kezel). Az approvalt a finance officer kézzel indítja. Production-átálláskor:
OCR a szkennelt számlákhoz, devizaátváltás determinisztikus scripttel + MNB-árfolyam,
kötegelt approval-indítás.
