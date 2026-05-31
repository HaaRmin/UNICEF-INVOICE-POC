# CLAUDE.md — UNICEF Beszállítói Számla POC

Útmutató a Claude Code (és bármely AI-ügynök) számára ehhez a projekthez.

## A projekt célja

**Beszállítói (accounts payable, kimenő) számlák feldolgozása a UNICEF Magyarországnál.**
Egy AI-ügynök beolvas PDF-számlákat, kinyeri az adatokat, **emberi ellenőrzés után**
strukturált `Supplier_Invoice__c` rekordot hoz létre a Salesforce-ban a beszállító
(Account + 1-az-1 Contact) alatt, és csatolja a forrás-PDF-et ContentVersion-ként.
A terület-kiválasztást és a jóváhagyás indítását **ember** (finance officer) végzi.

A repo a Salesforce **metaadatot** (objektumok, mezők, approval-réteg, permission set)
és a **futtató-artefaktumokat** (skill, Python scriptek, dokumentáció) verziózza.
A POC a meglévő `szerzodes-keszites` (adományozói szerződés) POC bevált infrastruktúrájára épül.

- **Célkörnyezet:** `unicefhungariannationalcommittee--dev2` sandbox
- **Org alias / username:** `Dev2` / `armin.horvath@unicef.hu.dev.dev2`
- **Pénznem:** kizárólag HUF (a POC devizát nem kezel)

## Projektstruktúra

```
unicef-invoice-poc/
├── sfdx-project.json              # sfdx projekt (package dir: force-app, API v60.0)
├── CLAUDE.md                      # ez a fájl
├── manifest/
│   └── retrieve-ui-components.xml # a UI-ban épített komponensek retrieve-manifestje
│
├── force-app/main/default/        # DEPLOYOLHATÓ Salesforce-metaadat
│   ├── objects/
│   │   ├── Supplier_Invoice__c/   # objektum + 19 mező + validationRules/
│   │   └── Cost_Center__c/        # objektum + 2 mező (Code__c, Active__c)
│   ├── approvalProcesses/         # UNICEF Beszállítói Számla Jóváhagyás (2 lépcsős)
│   ├── flows/                     # Sz_mla_ter_let_j_v_hagy_kit_lt_s (Area_Approver__c-t tölti)
│   ├── workflows/                 # Supplier_Invoice__c.workflow — 4 field update (státusz)
│   └── permissionsets/            # UNICEF_Szamla_POC (objektum- és mező-FLS)
│
└── resources/                     # NEM deployolható (force-app-on kívül)
    ├── docs/                      # DEPLOY_PLAN, RETRIEVE_PLAN, APPROVAL_PROCESS_SETUP
    ├── scripts/                   # upload_invoice_content.py, create_invoice_metadata.py
    └── skills/szamla-rogzites/    # SKILL.md — az ügynök futtatókönyve
```

> A `resources/` szándékosan a `force-app`-on **kívül** van, ezért a deploy nem érinti.
> Ha bármelyik deploy mégis beszippantaná, vedd fel a `.forceignore`-ba.

## Adatmodell

```
Account ("NetCore Systems Zrt.")
   ├── VAT_Number__c  ← A BESZÁLLÍTÓ-AZONOSÍTÓ KULCS (adószám, duplikátum-kulcs)
   └── 1-az-1 NPSP-kapcsolat
        ▼
Contact (LastName = cégnév) — itt jelennek meg a beszállító számlái
        ▼
Supplier_Invoice__c ("{Service_Description__c} – {Fulfillment_Date__c}", max 80 kar.)
   ├── Supplier_Account__c → Account,  Supplier_Contact__c → Contact
   ├── Supplier_Name__c, Supplier_VAT_Number__c        (SNAPSHOT — rögzítéskori állapot)
   ├── Invoice_Number__c, Issue_Date__c, Fulfillment_Date__c, Due_Date__c
   ├── Net_Amount__c, VAT_Amount__c, Gross_Amount__c   (Gross dönt a >1M HUF approvalról)
   ├── Service_Description__c
   ├── Area__c (picklist) — a finance officer tölti
   ├── Cost_Center__c → Cost_Center__c,  Orderer__c (picklist) — a TERÜLETVEZETŐ tölti jóváhagyáskor
   ├── Area_Approver__c → User — a Flow tölti az Area__c alapján
   ├── Approval_Status__c (default: "Betöltve")
   └── Version_Number__c (újraszámlázáskor +1)
```

- **Névmező:** Text (nem auto-number) — két rekord viselheti ugyanazt a nevet (újraszámlázás).
- **Snapshot-elv:** `Supplier_Name__c` / `Supplier_VAT_Number__c` a rögzítéskori állapotot őrzi (audit).

## Jóváhagyási folyamat

`UNICEF Beszállítói Számla Jóváhagyás` (ApprovalProcess), belépés: `Area__c` ki van töltve.

1. **Területvezetői jóváhagyás** — approver dinamikusan a `Area_Approver__c` related user mező
   (a Flow tölti az `Area__c` alapján). Belépéskor a státusz → "Területvezetői jóváhagyásra vár".
2. **Pénzügyi igazgatói jóváhagyás** — csak ha `Gross_Amount__c >= 1 000 000 HUF`;
   approver: `finance.unicef@unicefhungariannationalcommittee.hu`.

Státusz-mozgások (workflow field update-ek): Set Status to TVJV → Jóváhagyva / Elutasítva /
Pénzügyi igazgatói jóváhagyásra vár. Validation rule: jóváhagyás előtt a `Cost_Center__c`
és `Orderer__c` kötelező.

> **Org-specifikus hivatkozások:** a Flow-ban hardcode-olt user Id-k (`0059Q…`) és az
> approval konkrét approvere a `dev2`-höz kötöttek. **Production-deploy előtt felülvizsgálandók.**

## Gyakori parancsok

```bash
# Deploy a dev2-re (teljes metaadat)
sf project deploy start --source-dir force-app/main/default --target-org Dev2

# Validate-only (dry-run) — konzisztencia-ellenőrzés deploy nélkül
sf project deploy start --dry-run --manifest manifest/retrieve-ui-components.xml --target-org Dev2

# A UI-ban épített komponensek visszahúzása forrásként
sf project retrieve start --manifest manifest/retrieve-ui-components.xml --target-org Dev2

# Permission set kiosztása
sf org assign permset --name UNICEF_Szamla_POC --target-org Dev2
```

A CLI ügynök a **Salesforce DX MCP**-t használja (`deploy_metadata`, `retrieve_metadata`,
`run_soql_query`, `assign_permission_set`). Metaadatot (objektum/mező) **csak** ez tud
létrehozni — a `UNICEF Salesforce` connector rekord-szintű.

## Konvenciók és tiltások (a skillből)

- **Soha ne találgass** hiányzó számlaadatot (adószám, összeg) — jelöld hiányként, kérdezz vissza.
- **Emberi kapu:** rekord létrehozása előtt mutass táblázatos összegzést és kérj megerősítést (AP = pénzügyi kockázat).
- **NE indíts approvalt** az ügynökből — a finance officer teszi kézzel, miután a területet kiválasztotta.
- **NE hozz létre beszállítót** megerősítés nélkül (adószám a duplikátum-kulcs).
- **Rögzítéskor üresen hagyandó:** `Area__c`, `Cost_Center__c`, `Orderer__c`, `Area_Approver__c` (humán/Flow lépések).
- **PDF-feltöltés:** kizárólag `resources/scripts/upload_invoice_content.py` (REST), nem MCP/Custom Tools.
- **Tiltott:** `UNICEF Custom Tools` connector, `ContractDocumentService` Apex.
- **Verziózás:** adat-változás nélkül → meglévő rekord szerkesztése; új (javított) számla → új rekord, `Version_Number__c` +1, ugyanaz a Name.

## Hibakezelés-gyorsreferencia

| Hiba | Ok |
|---|---|
| `INVALID_FIELD: <mező>__c` | a metaadat nincs deployolva (lásd `resources/docs/DEPLOY_PLAN…`) |
| `INSUFFICIENT_ACCESS_OR_READONLY` | a `UNICEF_Szamla_POC` permission set nincs kiosztva |
| `FIELD_INTEGRITY_EXCEPTION` lookupnál | Account/Contact parent Id felcserélve |

## További dokumentáció

- `resources/docs/DEPLOY_PLAN_Supplier_Invoice.md` — a metaadat-deploy terve és mezőspecifikáció
- `resources/docs/APPROVAL_PROCESS_SETUP_Supplier_Invoice.md` — az approval-réteg UI-beállítása
- `resources/docs/RETRIEVE_PLAN_UI_Components.md` — a UI-komponensek forrásba húzásának terve
- `resources/skills/szamla-rogzites/SKILL.md` — az ügynök teljes futtatókönyve
