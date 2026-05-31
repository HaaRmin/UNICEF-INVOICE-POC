---
name: szamla-rogzites
description: "Beszállítói (kimenő) számlák feldolgozása a UNICEF Magyarországnál. Két flow: (1) RÖGZÍTÉS — PDF-számlák beolvasása, strukturált Supplier_Invoice__c rekord létrehozása a beszállító Account+Contact alatt, a forrás-PDF csatolása ContentVersion-ként; (2) LEKÉRDEZÉS — meglévő számlák keresése, read-only. Trigger-szavak rögzítéshez: 'rögzítsd a számlát', 'dolgozd fel a számlát', 'töltsd be a számlát', 'olvasd be a számlát', 'beszállítói számla', 'új számla verzió', 'újraszámlázás'. Trigger-szavak lekérdezéshez: 'milyen számláink vannak', 'beszállító számlái', 'gazdátlan számlák', 'jóváhagyásra váró számlák', 'számla státusza'. NE használd adományozói szerződésekre (arra a szerzodes-keszites skill való), sem általános Salesforce-keresésre."
---

# Beszállítói számla-rögzítés és -lekérdezés — UNICEF Magyarország

## A skill célja

Ez a skill **két önálló flow-t** támogat a beszállítói (accounts payable, **kimenő**) számlákhoz:

1. **Rögzítési flow**: egy AI-ügynök beolvas egy vagy több PDF-számlát, kinyeri az adatokat, **emberi ellenőrzés után** strukturált `Supplier_Invoice__c` rekordot hoz létre a beszállító alatt, és csatolja a forrás-PDF-et.
2. **Read-only lekérdezési flow**: meglévő számlák keresése, listázása. CSAK SOQL/SOSL, NEM jön létre vagy módosul rekord.

A két flow-t **a felhasználói kérés alapján** kell megkülönböztetni (lásd "Flow-választás").

> **Viszony a szerződés-skillhez:** ez a skill a `szerzodes-keszites` POC bevált infrastruktúráját hasznosítja újra: ugyanaz a `.env`-es Salesforce-hitelesítés, ugyanaz a `createSobjectRecord` + Python REST upload minta. A különbség: itt **adatkinyerés** történik egy strukturálatlan PDF-ből (nem sablon-kitöltés), és **kimenő** számláról van szó (nem bejövő adományról).

## ARCHITEKTÚRA (POC v1)

- `Supplier_Invoice__c` rekord létrehozása: **Hosted MCP `createSobjectRecord`** a `UNICEF Salesforce` connectoron
- Új beszállító (`Account` + `Contact`) létrehozása: szintén **`createSobjectRecord`**
- `ContentVersion` (a PDF) feltöltése: **Python REST script** — `upload_invoice_content.py`
- Beszállító-azonosítás: **adószám (`VAT_Number__c`) alapján** SOQL-lel az Account-on
- Approval: a finance officer **kézzel** indítja (a skill NEM submitál — lásd "Mit NE csinálj")
- Lekérdezések: `soqlQuery`, `find`, `getRelatedRecords`

**TILOS** használni (a szerződés-skillel azonosan):
- ❌ `UNICEF Custom Tools` connector
- ❌ `ContractDocumentService` Apex
- ❌ Bármilyen MCP-tool fájl-feltöltésre (csak a Python REST script!)

Ha ezek látszanának a tool-listán, **NE használd**.

## SANDBOX KÖRNYEZET — URL-konstans

**KÖTELEZŐ URL-bázis**. **MINDIG ezt használd**, NE találj ki más URL-t (még akkor sem, ha a Salesforce API-válaszban más subdomain szerepel):

```
SANDBOX_BASE_URL = https://unicefhungariannationalcommittee--dev2.sandbox.lightning.force.com
```

| Cél | URL-minta |
|---|---|
| Számla rekord | `{SANDBOX_BASE_URL}/lightning/r/Supplier_Invoice__c/{id}/view` |
| Account rekord | `{SANDBOX_BASE_URL}/lightning/r/Account/{id}/view` |
| Contact rekord | `{SANDBOX_BASE_URL}/lightning/r/Contact/{id}/view` |
| ContentVersion (letöltés) | `{SANDBOX_BASE_URL}/sfc/servlet.shepherd/version/download/{cvId}` |

**Ellenőrző-lépés**: mielőtt URL-t küldesz, ellenőrizd, hogy tartalmazza a `unicefhungariannationalcommittee--dev2` stringet. Ha a tool-válasz más subdomaint ad, akkor IS a fenti konstanst használd.

## Flow-választás (a két flow határa)

**Először** döntsd el, melyik flow-t indítod.

### Rögzítési flow trigger-szavak:
- "rögzítsd a számlát", "dolgozd fel a számlát", "olvasd be / töltsd be a számlát"
- "új számla", "új verzió", "újraszámlázás"

### Lekérdezési flow trigger-szavak:
- "milyen számláink vannak", "beszállító számlái"
- "gazdátlan számlák", "jóváhagyásra váró számlák", "számla státusza"
- "listázd", "mutasd", "keresd"

### Ha bizonytalan vagy
Kérdezz vissza:
> *"Szeretnéd, ha beolvasnám és rögzíteném a számlá(ka)t, vagy a meglévőket listáznám/keresném?"*

---

## A UNICEF Magyarország adatmodellje

A UNICEF az NPSP **"1-az-1" Contact-Account modelljét** használja a céges kapcsolatokra:

```
Account: "NetCore Systems Zrt."  (RecordType: Organization)
   ├── BillingStreet, BillingCity, BillingPostalCode
   ├── VAT_Number__c (= adószám)   ← EZ A BESZÁLLÍTÓ-AZONOSÍTÓ KULCS
   └── (más céges adatok)
        │ 1-az-1 NPSP-kapcsolat
        ▼
Contact: "NetCore Systems Zrt."  (LastName = cégnév!)
   └── Donor_Type__c = "CO" (Corporate)
        │ a beszállító számlái (Supplier_Contact__c related list)
        ▼
Supplier_Invoice__c: "Salesforce licencbővítés – 2026-05-10"
   ├── Supplier_Account__c  → Account
   ├── Supplier_Contact__c  → Contact (a Contact alatt is megjelenik!)
   ├── Supplier_Name__c, Supplier_VAT_Number__c   (SNAPSHOT)
   ├── Invoice_Number__c, Issue_Date__c, Fulfillment_Date__c, Due_Date__c
   ├── Net_Amount__c, VAT_Amount__c, Gross_Amount__c
   ├── Service_Description__c
   ├── Area__c (a finance officer tölti), Approval_Status__c
   ├── Cost_Center__c, Orderer__c (a TERÜLETVEZETŐ tölti jóváhagyáskor)
   └── Version_Number__c
```

**Kulcs-megfigyelések**:
- A cégnév mindkét parent-helyen: `Account.Name` ÉS `Contact.LastName`
- Az adószám az Account-on van (`VAT_Number__c`) — **és átemelődik a számlára** snapshot-ként
- A `Supplier_Contact__c` a céget reprezentáló Contact-ra mutat — **így a Contact alatt is megjelenik a számla**

## A snapshot-modell elve

A számla-rekord **a rögzítéskori állapotot rögzíti**. A `Supplier_Name__c` és `Supplier_VAT_Number__c` az Account akkori adatát őrzi. Ha az Account később módosul, **a számlán lévő érték NEM változik** — ez audit-szempont.

---

## Projektmappa-struktúra

A skill az alábbi struktúrát várja (a szerződés-POC mintájára):

```
~/Documents/UNICEF Szamlak/
├── invoices/                       ← ide teszi a felhasználó a beolvasandó PDF számlákat
├── scripts/
│   ├── upload_invoice_content.py   ← a REST upload script (PDF-támogatással)
│   └── .env                        ← Salesforce credentialök (lásd lent)
└── SKILL_szamla-rogzites.md        ← ez a fájl
```

### A `.env` fájl — FONTOS

A `upload_invoice_content.py` a **saját mappájában** (`scripts/`) keresi a `.env`-et (fallback: `creds.env.txt`). **Ez ugyanaz a `.env`, amit a szerződés-POC használ** — másold be a `scripts/` mappába, vagy hozz létre egyet ezzel a tartalommal:

```
SF_USERNAME=<a sandbox username>
SF_PASSWORD=<jelszó>
SF_TOKEN=<security token>
SF_DOMAIN=test
```

**Ha a script „MissingCredentials" vagy „CredentialsFileNotFound" hibát ad** → a `.env` nincs a `scripts/` mappában. NE keress alternatív feltöltési módot (pl. MCP-tool) — jelezd a felhasználónak, hogy a `.env`-et a `scripts/` mappába kell tennie, és állj meg.

---

# 1. FLOW: SZÁMLA-RÖGZÍTÉS — lépésről lépésre

## 1. lépés — A felhasználó átadja a PDF-(ek)et

> *"Rögzítsd ezt a 3 beszállítói számlát."*

A PDF-ek az `invoices/` mappában (vagy a Cowork uploads mappában) vannak. Ha nem találod a fájlokat, **kérdezd meg**, hova tette őket — NE találgass elérési utat.

## 2. lépés — Adatkinyerés (számlánként)

Olvasd ki minden PDF-ből az alábbi mezőket. Ha egy PDF szövege nem olvasható (szkennelt kép), jelezd a felhasználónak.

| Mező | Honnan |
|---|---|
| Beszállító **neve** | a számla fejléce |
| Beszállító **adószáma** | a számla fejléce (magyar: NNNNNNNN-N-NN) |
| **Számlasorszám** | a számla azonosítója |
| **Kiállítás / Teljesítés / Fizetési határidő** dátuma | a számla dátum-mezői |
| **Nettó / ÁFA / Bruttó** összeg | az összesítő rész |
| **Szolgáltatás** rövid megnevezése | a tételsorokból összegezve (ez kerül a Name-be) |

**KRITIKUS — soha ne találgass.** Ha egy mező (pl. **adószám**, összeg) nem olvasható ki egyértelműen, jelöld **HIÁNYKÉNT** a 4. lépés összegzésében — NE tölts ki kitalált értéket. Egy rossz adószám vagy összeg valódi pénzügyi hiba.

## 3. lépés — Beszállító-azonosítás ADÓSZÁM alapján

**MINDIG először az adószámmal keress**, létezik-e már a beszállító. Ez a duplikátum-védelem kulcsa.

```
soqlQuery:
SELECT Id, Name, VAT_Number__c FROM Account WHERE VAT_Number__c = '<a PDF-ből kiolvasott adószám>'
```

**Várt eredmények és teendők:**

| Eset | Teendő |
|---|---|
| **1 találat** | Megvan a beszállító. Kérd le a hozzá tartozó Contactot is (lásd alább). Folytasd az 5. lépéssel. |
| **0 találat** | A beszállító MÉG NEM létezik. NE hozd létre némán — menj a **3b. lépésre** (megerősítés után). |
| **Az adószám hiányzott a PDF-ből** | Keress névre (`find`), de jelezd a bizonytalanságot, és a 4. lépésben kérdezz vissza. |

A Contact lekérése egy meglévő Accounthoz:
```
soqlQuery:
SELECT Id, LastName FROM Contact WHERE AccountId = '<a megtalált Account Id>'
```

> **PÉLDA — ismert, létező beszállítók a tesztkörnyezetben** (ezeknél 1 találatot kapsz, NE hozz létre újat):
> - CloudPilot Informatikai Kft. — adószám `24681357-2-41`
> - Kreatív Műhely Bt. — adószám `22334455-1-42`

## 3b. lépés — ÚJ beszállító létrehozása (CSAK ha 0 találat ÉS a felhasználó megerősíti)

Ha a 3. lépésben **nincs adószám-találat**, NE hozz létre némán beszállítót. Először kérdezd meg:

> *"Ehhez a számlához nem találtam meglévő beszállítót (adószám: <X>, név: <Y>). Létrehozzam az új Account + Contact párt?"*

**Csak megerősítés után** hozd létre — pontosan az alábbi módon, **két lépésben**.

### 3b.1 — Account létrehozása

```
createSobjectRecord:
  sobject-name: "Account"
  body: {
    "Name": "<cégnév a számláról>",
    "VAT_Number__c": "<adószám a számláról>",
    "BillingStreet": "<utca, házszám — ha kiolvasható>",
    "BillingCity": "<város — ha kiolvasható>",
    "BillingPostalCode": "<irányítószám — ha kiolvasható>"
  }
```

**KRITIKUS szabályok az Account-létrehozáshoz (POC):**
1. **A `BillingCountry` / ország mezőt HAGYD KI teljesen.** Az org country-picklistje validált listából dolgozik, és a hibás ország-érték `FIELD_INTEGRITY_EXCEPTION`-t dob. POC-ben az ország nem szükséges. (Ha valaha mégis kell: `BillingCountryCode` = `"HU"`, NEM `BillingCountry` = `"Magyarország"`.)
2. A `Name` a cégnév pontosan úgy, ahogy a számlán szerepel.
3. A `VAT_Number__c` a kulcs — ez teszi a beszállítót azonosíthatóvá legközelebb.

A Salesforce visszaadja az **Account Id-t** — ez kell a Contacthoz.

### 3b.2 — Contact létrehozása (1-az-1, a cégnév mint LastName)

```
createSobjectRecord:
  sobject-name: "Contact"
  body: {
    "LastName": "<ugyanaz a cégnév, mint az Account.Name>",
    "AccountId": "<az előző lépésben kapott Account Id>",
    "Donor_Type__c": "CO",
    "MailingStreet": "<utca — ha van>",
    "MailingCity": "<város — ha van>",
    "MailingPostalCode": "<irányítószám — ha van>"
  }
```

**KRITIKUS szabályok a Contact-létrehozáshoz (POC):**
1. **A `Donor_Type__c` KÖTELEZŐ**, és beszállítónál mindig **`"CO"`** (Corporate). Ha kihagyod, a Salesforce `REQUIRED_FIELD_MISSING` hibát dob.
2. A `LastName` = a cégnév (NPSP 1-az-1 modell — a céget egy Contact reprezentálja, nincs külön keresztnév).
3. Az `AccountId` az előző lépés Account Id-ja — így lesz 1-az-1 a kapcsolat.
4. Az ország mezőt itt is HAGYD KI.

A Salesforce visszaadja a **Contact Id-t**. Most már van Account Id + Contact Id → folytasd az 5. lépéssel.

## 4. lépés — Strukturált összegzés + EMBERI KAPU

Mutass egy **táblázatos összegzést** az összes számláról, MIELŐTT bármit létrehoznál: beszállító, adószám, sorszám, dátumok, nettó/ÁFA/bruttó, javasolt szolgáltatás-név, és a beszállító státusza (létező / létrehozandó). **Pirossal vagy „HIÁNYZIK" jelöléssel** emeld ki, amit nem találtál vagy bizonytalan.

> *"Így olvastam ki a számlákat. A HIÁNYZIK-kal jelölt mezőket nem találtam — ezeket pótold, vagy hagyod üresen? Ha minden stimmel, létrehozom a rekordokat."*

**NE hozz létre számla-rekordot a megerősítés előtt.** Ez AP-folyamat — a rossz összeg vagy beszállító valódi pénzügyi kockázat.

## 5. lépés — A számla rekord létrehozása

Számlánként, **kizárólag** a `createSobjectRecord`-dal:

```
createSobjectRecord:
  sobject-name: "Supplier_Invoice__c"
  body: {
    "Name": "<szolgáltatás> – <teljesítés dátuma YYYY-MM-DD>",
    "Supplier_Account__c": "<Account Id>",
    "Supplier_Contact__c": "<Contact Id>",
    "Supplier_Name__c": "<Account.Name — SNAPSHOT>",
    "Supplier_VAT_Number__c": "<adószám — SNAPSHOT>",
    "Invoice_Number__c": "<számlasorszám>",
    "Issue_Date__c": "<YYYY-MM-DD>",
    "Fulfillment_Date__c": "<YYYY-MM-DD>",
    "Due_Date__c": "<YYYY-MM-DD>",
    "Service_Description__c": "<szolgáltatás leírás>",
    "Net_Amount__c": <szám, idézőjel nélkül>,
    "VAT_Amount__c": <szám>,
    "Gross_Amount__c": <szám>,
    "Approval_Status__c": "Betöltve",
    "Version_Number__c": 1
  }
```

**Névképzés (KÖTELEZŐ formátum):** `Name = "{szolgáltatás} – {teljesítés dátuma}"`, **max 80 karakter** (a szolgáltatás-leírást szükség szerint rövidítsd). Pl. `Microsoft 365 licenc – 2026-04-30`.

**Amit NEM töltesz ki rögzítéskor** (ezek a humán lépésekhez tartoznak):
- ❌ `Area__c` — a finance officer adja meg a riportban
- ❌ `Cost_Center__c`, `Orderer__c` — a területvezető adja jóváhagyáskor
- ❌ `Area_Approver__c` — a Flow tölti automatikusan

A Salesforce visszaadja a **rekord Id-ját** — ez kell a 6. lépéshez.

## 6. lépés — A PDF csatolása (KÖTELEZŐ, Python REST)

**Kizárólag** az `upload_invoice_content.py` scripttel. NE használj MCP-t vagy Custom Tools-t fájlfeltöltésre. A bash tool-on át futtasd:

```bash
python3 ~/Documents/UNICEF\ Szamlak/scripts/upload_invoice_content.py \
  "<a számla rekord Id-ja az 5. lépésből>" \
  "<a számla PDF teljes elérési útja>" \
  "Számla - <beszállító> <sorszám>"
```

A script `stdout`-ra JSON-t ad: `{"success": true, "contentVersionId": "068...", ...}`. Várt idő: **~2 másodperc**.

**FONTOS — elérési út**: a PDF-re **abszolút, host-oldali útvonalat** adj (ugyanúgy, mint a szerződés-POC-ban). NE használj `~`-t a PDF útjában, ha a fájl a host gépen van, mert a script sandbox-konténerben fut.

**Ha a script nem található vagy hibázik** → NE keress alternatív utat (MCP). Jelezd, hogy a `scripts/` mappa beállítása nem teljes, és állj meg.

Opcionálisan írd vissza a rekord `Source_ContentVersion_Id__c` mezőjébe a kapott `contentVersionId`-t (`updateSobjectRecord`).

## 7. lépés — Átadás a finance officernek (NEM indítasz approvalt!)

A rögzítés után **a folyamat a felhasználóhoz kerül**. **NE indítsd el a jóváhagyást** — azt a finance officer teszi kézzel, miután a területet kiválasztotta. Írd meg:

> *"Létrehoztam N számla rekordot, mindegyikhez csatoltam a PDF-et. Következő lépés a te kezedben:
> (1) nézd át a 'Frissen betöltött számlák' riportban,
> (2) válaszd ki mindegyikhez a Területet,
> (3) majd indítsd el a jóváhagyást a 'Submit for Approval' gombbal.
> A rekordok: <linkek a SANDBOX_BASE_URL szerint>"*

---

# Verziózás — újraszámlázás és javítás

**Két eset van**, élesen különböztesd meg:

### A) A számla adatai NEM változnak — csak terület/megrendelő/költséghely
→ **A meglévő rekordot szerkeszd** (`updateSobjectRecord`). NEM új rekord, NEM új verzió.

### B) A beszállító ÚJ számlát állít ki (mert egy adat — összeg, sorszám — nem stimmelt)
→ **Új rekordot hozz létre**, NE módosítsd a régit:
1. Keresd meg a meglévő rekord(ok)at: ugyanaz a beszállító + ugyanaz a `Name` (szolgáltatás + dátum).
2. Az új `Version_Number__c` = a max meglévő verzió + 1.
3. Hozz létre egy **új** `Supplier_Invoice__c`-t (5. lépés), **ugyanazzal a Name-mel**, az emelt verzióval.
4. Töltsd fel az **új PDF-et** mint új ContentVersion (6. lépés).
5. Így a beszállító Contactja alatt **két azonos nevű** számla lesz, eltérő Id-val és ContentVersion-nel. Csak az egyik lesz a végén `Jóváhagyva` — a másik `Elutasítva`.

Ez akkor is így működik, ha egy számlát az approval során **elutasítottak**: nem „újraélesztjük", hanem az új (helyes) számláról új verziós rekord készül.

---

# 2. FLOW: LEKÉRDEZÉS (read-only)

Trigger: "milyen számláink vannak", "gazdátlan számlák", "jóváhagyásra váró".

- **Gazdátlan (terület nélküli):**
  `SELECT Id, Name, Gross_Amount__c FROM Supplier_Invoice__c WHERE Area__c = null`
- **Jóváhagyásra váró (és kinél):**
  `SELECT Id, Name, Area__c, Approval_Status__c FROM Supplier_Invoice__c WHERE Approval_Status__c = 'Területvezetői jóváhagyásra vár'`
  (csoportosítsd `Area__c` szerint — ez mutatja, melyik területvezetőnél áll)
- **Egy beszállító számlái:**
  `getRelatedRecords` az Account-on a `Supplier_Invoices` relationship-pel, VAGY
  `SELECT ... FROM Supplier_Invoice__c WHERE Supplier_Contact__c = '<contactId>'`

**Read-only flow-ban NE hozz létre / módosíts rekordot, és NE indíts approvalt.**

---

# Mit NE csinálj (közös, KRITIKUS)

- ❌ **NE indíts approvalt** (`Submit for Approval`) — ezt a finance officer teszi kézzel. A skill a 7. lépésnél megáll.
- ❌ **NE találgass** hiányzó adatot (adószám, összeg) — jelöld HIÁNYZIK-ként, kérdezz.
- ❌ **NE hozz létre beszállítót** megerősítés nélkül (duplikátum-veszély).
- ❌ **NE tölts ki** `Area__c`, `Cost_Center__c`, `Orderer__c`, `Area_Approver__c` mezőt rögzítéskor.
- ❌ **NE add meg az ország mezőt** Account/Contact létrehozásakor (POC).
- ❌ **NE hagyd ki a `Donor_Type__c = "CO"`-t** Contact létrehozásakor (kötelező).
- ❌ **NE használj** `UNICEF Custom Tools`-t, `ContractDocumentService`-t, vagy MCP-t fájlfeltöltésre.
- ❌ **NE hozz létre metaadatot** (mező, objektum).

---

# Hibakezelés (gyakori hibák és megoldás)

**Salesforce-side:**
- `REQUIRED_FIELD_MISSING: [Donor_Type__c]` → a Contact-nál hiányzik a `Donor_Type__c`. Add hozzá: `"CO"`.
- `FIELD_INTEGRITY_EXCEPTION (BillingCountry)` → ne add meg az ország mezőt (POC). Töröld a body-ból, és próbáld újra.
- `INVALID_FIELD: <mező>__c` → a metaadat nincs deploy-olva (szólj a felhasználónak).
- `INSUFFICIENT_ACCESS_OR_READONLY` → a `UNICEF_Szamla_POC` permission set nincs kiosztva a userre.
- `FIELD_INTEGRITY_EXCEPTION` lookupnál → rossz parent Id (Account vs Contact felcserélve a számlán).
- `MALFORMED_QUERY` SOQL-nél → ellenőrizd az aposztrófokat az adószám körül.

**Python REST script (`upload_invoice_content.py`):**
- `MissingCredentials` / `CredentialsFileNotFound` → a `.env` nincs a `scripts/` mappában.
- `InvalidRecordId` → a számla Id nem 15/18 karakteres.
- `InvalidFileType` → csak `.pdf` és `.docx` engedett.
- `ContentVersion insert failed` → rossz rekord Id vagy jogosultság.

---

# Salesforce-side setup (referencia)

- Objektumok: `Supplier_Invoice__c`, `Cost_Center__c`
- Permission set: `UNICEF_Szamla_POC`
- Approval: `UNICEF Beszállítói Számla Jóváhagyás` process + `Area_Approver__c`-t kitöltő Flow + validation rule (Megrendelő + Költséghely kötelező jóváhagyáskor)
- Upload script: `upload_invoice_content.py` (a szerződés `upload_content.py` PDF-es változata)
- Aktív connector: `UNICEF Salesforce`. Tiltott: `UNICEF Custom Tools`.

## Account/Contact kötelező és tiltott mezők — összefoglaló tábla

| Objektum | Mező | Szabály |
|---|---|---|
| Account | `Name` | kötelező — cégnév |
| Account | `VAT_Number__c` | erősen ajánlott — ez az azonosító kulcs |
| Account | `BillingCountry` / ország | **NE add meg** (POC) |
| Contact | `LastName` | kötelező — cégnév (1-az-1) |
| Contact | `AccountId` | kötelező — az Account Id |
| Contact | `Donor_Type__c` | **KÖTELEZŐ — mindig `"CO"`** |
| Contact | ország mező | **NE add meg** (POC) |

## Teszt-adat (a POC tesztelésére — ISMERT, LÉTEZŐ beszállítók)

Ezeknél a 3. lépés **1 találatot** ad — NE hozz létre újat:

| Object | Id | Adatok |
|---|---|---|
| Account | `0019Q00001XUreTQAT` | CloudPilot Informatikai Kft., VAT: 24681357-2-41 |
| Contact | `0039Q00001kNpmoQAC` | CloudPilot Informatikai Kft. (LastName) |
| Account | `0019Q00001XUrg5QAD` | Kreatív Műhely Bt., VAT: 22334455-1-42 |
| Contact | `0039Q00001kNoacQAC` | Kreatív Műhely Bt. (LastName) |

# Fejlesztői megjegyzés

POC v1 — v2 skill (2026.05.31):
- **Sonnet 4.6 Cowork-barát átírás**: a rögzítési flow lépésenként kibontva, explicit JSON-body-kkal, kötelező/tiltott mező-táblákkal, önellenőrző szabályokkal. A szerződés-skill v10 stílusát követi (HIÁNYZIK jelölés, KRITIKUS callout-ok).
- **Account/Contact létrehozás explicitté téve** (3b. lépés): 1-az-1 modell, az **ország mező kihagyása** (POC — a country-picklist validációs hibája miatt), és a **`Donor_Type__c = "CO"` kötelező mező** — mindkettő éles tesztből derült ki.
- **Projektmappa-struktúra + `.env` elhelyezés** explicit szakaszban (`~/Documents/UNICEF Szamlak/`, a `.env` a `scripts/` mappában, a szerződés-POC credentialjével).
- **Ismert teszt-beszállítók** (CloudPilot, Kreatív Műhely) felvéve, hogy az adószám-alapú felismerés tesztelhető legyen.

POC v1 — v1 skill (2026.05): a `szerzodes-keszites` infrastruktúrájára épülő első verzió. Forint-only.

Production-átálláskor: OCR a szkennelt számlákhoz, devizaátváltás determinisztikus scripttel + MNB-árfolyam, kötegelt approval-indítás, a `Donor_Type__c`/ország mezők rendezése a beszállítói (nem adományozói) kontextushoz.
