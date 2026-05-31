# Deploy-terv a CLI ügynöknek — `Supplier_Invoice__c` + `Cost_Center__c`

**UNICEF Beszállítói Számla POC — metaadat-deploy**
Célkörnyezet: `unicefhungariannationalcommittee--dev2` sandbox

---

## 0. Mit hozunk létre

Két custom objektum a beszállítói számla POC-hez, a meglévő szerződés-POC mintájára:

| Objektum | Szerep |
|---|---|
| `Supplier_Invoice__c` | A beszállítói számla. A beszállító Account + 1-az-1 Contact alatt jelenik meg. |
| `Cost_Center__c` | A költséghely (a számla parent-je egy lookup-on át). A területvezető tölti ki jóváhagyáskor. |

Plusz egy **permission set** (`UNICEF Számla POC`) az objektum- és mező-hozzáféréshez (FLS).

---

## 1. Deploy-módszer — `deploy_metadata` MCP (elsődleges)

A CLI ügynök rendelkezik a hivatalos **Salesforce DX MCP**-vel. Ez a helyes, megbízható út.

> **FONTOS — miért nem a `UNICEF Salesforce` connector:** az a connector (`createSobjectRecord`, `soqlQuery`, stb.) **rekord-szintű** — adatot hoz létre, **metaadatot nem**. Objektumot/mezőt **csak** a `deploy_metadata` (vagy a fallback Tooling API script) tud létrehozni.

### Lépések

1. **A source tree** készen áll: a `unicef-invoice-poc/` mappa egy teljes sfdx projekt (`sfdx-project.json` + `force-app/main/default/...`). 24 metaadat-fájl: 2 objektum, 20 mező, 1 permission set.

2. **Org-azonosító ellenőrzése** — győződj meg róla, hogy a `dev2` sandboxra mutatsz:
   ```
   mcp__Salesforce__get_username
   mcp__Salesforce__list_all_orgs
   ```
   A target a `unicefhungariannationalcommittee--dev2`. Ha nem ez az alapértelmezett, add meg expliciten a deploynál.

3. **Deploy** — a teljes `force-app` könyvtárat:
   ```
   mcp__Salesforce__deploy_metadata
     source-dir: unicef-invoice-poc/force-app/main/default
     target-org: <a dev2 sandbox username/alias>
   ```
   A platform a deploy-on belül feloldja a függőségi sorrendet (a `Cost_Center__c` objektum előbb jön létre, mint a rá mutató `Supplier_Invoice__c.Cost_Center__c` lookup). Egy deployban mehet az egész.

4. **Permission set kiosztása** a POC-felhasználóknak (finance officer + a 3 approver user):
   ```
   mcp__Salesforce__assign_permission_set
     permission-set-name: UNICEF_Szamla_POC
     on-behalf-of: <usernames>
   ```

5. **Ellenőrzés** — a deploy után:
   ```
   mcp__Salesforce__run_soql_query
     query: SELECT QualifiedApiName FROM EntityDefinition WHERE QualifiedApiName IN ('Supplier_Invoice__c','Cost_Center__c')
   ```
   Illetve a mezők:
   ```
   SELECT QualifiedApiName FROM FieldDefinition WHERE EntityDefinition.QualifiedApiName = 'Supplier_Invoice__c'
   ```

---

## 2. Deploy utáni teendők (NE maradjanak ki)

A metaadat-deploy létrehozza az objektumokat és mezőket, de **két dolgot kézzel kell** rendezni (vagy külön deployban):

1. **Page layout** — a custom mezők nem kerülnek rá automatikusan a layoutra.
   `Setup → Object Manager → Beszállítói számla → Page Layouts` → húzd rá a mezőket.
   A finance officernek látnia kell az összes fejadatot; a `Megrendelő`, `Költséghely`, `Terület` mezőket szerkeszthetően.

2. **A permission set** fedi az FLS-t, de ellenőrizd, hogy a POC-userek tényleg megkapták (1.4 lépés).

3. *(Opcionális)* **Tab** a navigációhoz: `Setup → Tabs → Custom Object Tabs → New` a `Supplier_Invoice__c`-re és `Cost_Center__c`-re.

4. **Az approval-réteg** (Area_Approver__c-t kitöltő Flow, validation rule, approval process) **NEM ebben a deployban van** — azt a `APPROVAL_PROCESS_SETUP_Supplier_Invoice.md` szerint a Salesforce UI-on állítod be, mert konkrét, UI-ban létrehozott User Id-kra hivatkozik.

---

## 3. Mezőspecifikáció (referencia / ellenőrzés)

### `Supplier_Invoice__c`

Névmező: **Text** típusú (`Számla megnevezése`) — szándékosan NEM auto-number, mert két record viselheti ugyanazt a nevet (ugyanaz a szolgáltatás ugyanazon a napon, eltérő verzióval).

| API név | Label | Típus | Megjegyzés |
|---|---|---|---|
| `Supplier_Account__c` | Beszállító (Account) | Lookup(Account) | a beszállító cég |
| `Supplier_Contact__c` | Beszállító (Contact) | Lookup(Contact) | 1-az-1 — ez adja a related listet a Contact alatt |
| `Cost_Center__c` | Költséghely | Lookup(Cost_Center__c) | a területvezető tölti ki |
| `Area_Approver__c` | Terület jóváhagyója | Lookup(User) | a Flow tölti az `Area__c` alapján; az approval ehhez irányít |
| `Invoice_Number__c` | Számlasorszám | Text(80) | a beszállító sorszáma |
| `Issue_Date__c` | Kiállítás kelte | Date | |
| `Fulfillment_Date__c` | Teljesítés kelte | Date | a névképzéshez is |
| `Due_Date__c` | Fizetési határidő | Date | |
| `Service_Description__c` | Szolgáltatás megnevezése | Text(255) | a névképzéshez |
| `Net_Amount__c` | Nettó összeg | Currency(18,2) | |
| `VAT_Amount__c` | ÁFA összeg | Currency(18,2) | |
| `Gross_Amount__c` | Bruttó összeg | Currency(18,2) | **az approval értékhatár ezen dől el (>1 000 000)** |
| `Supplier_Name__c` | Beszállító neve (snapshot) | Text(255) | rögzítéskori állapot |
| `Supplier_VAT_Number__c` | Beszállító adószáma (snapshot) | Text(20) | rögzítéskori állapot |
| `Area__c` | Terület | Picklist | Fundraising, Advocacy, Communications, Finance |
| `Orderer__c` | Megrendelő | Picklist | karbantartott lista (seed-értékekkel) |
| `Approval_Status__c` | Jóváhagyási státusz | Picklist | Betöltve*(default)*, Területvezetői jóváhagyásra vár, Pénzügyi igazgatói jóváhagyásra vár, Jóváhagyva, Elutasítva |
| `Version_Number__c` | Verziószám | Number(3,0) | újrakiállításkor +1 |
| `Source_ContentVersion_Id__c` | Forrás dok. (ContentVersion Id) | Text(18) | opcionális nyomonkövetés |

### `Cost_Center__c`

Névmező: **Text** (`Költséghely neve`).

| API név | Label | Típus |
|---|---|---|
| `Code__c` | Kód | Text(40) |
| `Active__c` | Aktív | Checkbox (default: true) |

---

## 4. Fallback — programatikus Tooling API script

Ha a `deploy_metadata` valamiért nem elérhető vagy hibázik, ott a **`create_invoice_metadata.py`** — ugyanazt a két objektumot és mezőket hozza létre a Tooling API-n keresztül, a `.env`-es `simple-salesforce` hitelesítéssel (ugyanaz a stack, mint az `upload_content.py`). Futtatás:
```
pip install --break-system-packages simple-salesforce python-dotenv requests
python3 create_invoice_metadata.py
```
Idempotens (a meglévő elemeket kihagyja). **Figyelem:** a Tooling API-val létrehozott mezők nem kapnak automatikusan FLS-t és nem kerülnek a layoutra — ott a 2. szakasz teendői hatványozottan érvényesek (nincs permission set deploy).

---

## 5. Névképzési szabály (a skill és a deploy közös megállapodása)

A `Supplier_Invoice__c.Name` = **`{Service_Description__c} – {Fulfillment_Date__c}`**, max 80 karakter (a szolgáltatás-leírás szükség szerint rövidítve). Példa: `Microsoft 365 licenc – 2026-04-30`.

Ez adja az „egyedi szolgáltatás-identitást”: ha a beszállító újraszámláz (mert egy adat nem stimmelt), a beszállító Contactja alatt **két azonos nevű** record listázódik — eltérő `Version_Number__c`-vel, eltérő ContentVersion-nel, és csak az egyik lesz `Jóváhagyva` státuszú.
