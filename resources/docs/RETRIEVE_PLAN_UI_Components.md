# Retrieve-terv a CLI ügynöknek — UI-ban épített komponensek verziózása

**Cél:** a Salesforce UI-ban kézzel létrehozott három komponenst (approval process,
validation rule, flow) letölteni az `unicef-invoice-poc` sfdx projektbe forrásként,
valamint a skillt és a Python scripteket egy `resources/` mappába menteni.

Célkörnyezet: `unicefhungariannationalcommittee--dev2` sandbox.

---

## 1. Mit töltünk le (metaadat-típusok)

| Komponens | Metaadat-típus | Hova kerül a projektben |
|---|---|---|
| Approval process | `ApprovalProcess` | `force-app/main/default/approvalProcesses/` |
| Validation rule | (az objektum része) | `force-app/main/default/objects/Supplier_Invoice__c/validationRules/` |
| Flow (terület-jóváhagyó) | `Flow` | `force-app/main/default/flows/` |

> A **validation rule nem önálló retrieve-típus** — az objektummal együtt jön le.
> Ha az objektumot újra retrieveled, a validation rule a `validationRules/` almappába kerül.

## 2. Retrieve a `retrieve_metadata` MCP-eszközzel

A pontos API-nevek (ezeket használd a metadata-lekérésnél):

- **ApprovalProcess:** `Supplier_Invoice__c.UNICEF_Besz_ll_t_i_Sz_mla_J_v_hagy_s`
  *(a tényleges unique name a folyamat detail-oldalán, a „Unique Name" mezőben olvasható — másold onnan pontosan, mert az ékezet-eltávolítás miatt nehéz fejből)*
- **Flow:** a Flow API-neve (Setup → Flows → a flow „API Name"-je, pl. `Szamla_terulet_jovahagyo_kitoltes`)
- **ValidationRule:** `Supplier_Invoice__c.Megrendelo_es_Koltseghely_kotelezo_jovahagyashoz`

Hívások (a CLI ügynök a `mcp__Salesforce__retrieve_metadata`-t használja, metadata-komponensekre szűrve):

```
retrieve_metadata
  metadata: ApprovalProcess:Supplier_Invoice__c.UNICEF_Besz_ll_t_i_Sz_mla_J_v_hagy_s
  target-org: <dev2 username>
  output-dir: force-app/main/default

retrieve_metadata
  metadata: Flow:<a flow API neve>
  target-org: <dev2 username>
  output-dir: force-app/main/default

# A validation rule az objektummal jön — retrieveld újra az objektumot,
# vagy célzottan a ValidationRule típust:
retrieve_metadata
  metadata: ValidationRule:Supplier_Invoice__c.Megrendelo_es_Koltseghely_kotelezo_jovahagyashoz
  target-org: <dev2 username>
  output-dir: force-app/main/default
```

> Ha a `retrieve_metadata` egy `package.xml` manifestet vár komponenslista helyett,
> a CLI ügynök állítson össze egy manifestet a fenti három típussal. Alternatíva:
> `sf project retrieve start --metadata ApprovalProcess:... Flow:... ValidationRule:...`

## 3. A field update-ek — fontos megjegyzés

Az approval process státusz-frissítő **field update-jei** (Set Status to TVJV, Jóváhagyva,
Elutasítva, Pénzügyi igazgatói…) klasszikus *workflow field update*-ek. Ezek a
**`WorkflowFieldUpdate`** típusba tartoznak, és az objektum workflow-metaadatában élnek
(`workflows/Supplier_Invoice__c.workflow-meta.xml`). Ha a teljes reprodukálhatóságot akarod,
ezt a típust is retrieveld:

```
retrieve_metadata
  metadata: Workflow:Supplier_Invoice__c
  target-org: <dev2 username>
  output-dir: force-app/main/default
```

Enélkül az approvalProcess hivatkozna olyan field update-ekre, amik nincsenek a projektben —
ezért ezt érdemes vele együtt lehúzni.

## 4. Erős figyelmeztetés — user-hivatkozások

Az `ApprovalProcess` metaadat **konkrét felhasználókra hivatkozik** (az `Approver Finance`
a 2. lépésben, és a submitter). Ez a sandbox verziózásához tökéletes, DE egy másik org-ba
(pl. production) való deploy előtt ezeket a hivatkozásokat **felül kell vizsgálni**, mert a
cél-org-ban más user-ek és Id-k lesznek. A `dev2`-n belüli újra-deployhoz nincs teendő.

A Flow-ban a hardcode-olt user Id-k (`005...`) ugyanígy org-specifikusak — production előtt
ezeket érdemes Custom Metadata / Custom Label alapú kiszervezésre cserélni, de POC-ben jók.

## 5. A `resources/` mappa — skill + scriptek

A projektben a metaadaton kívül érdemes verziózni a futtató-artefaktumokat is. Javasolt
struktúra (a `force-app`-on KÍVÜL, mert ezek nem deployolható Salesforce-metaadatok):

```
unicef-invoice-poc/
├── force-app/main/default/        (deployolható metaadat)
│   ├── objects/
│   ├── approvalProcesses/
│   ├── flows/
│   ├── workflows/
│   └── permissionsets/
├── resources/                      (NEM deployolható — futtató-eszközök, dok)
│   ├── skills/
│   │   └── szamla-rogzites/
│   │       └── SKILL.md
│   ├── scripts/
│   │   ├── upload_invoice_content.py
│   │   └── create_invoice_metadata.py   (fallback)
│   └── docs/
│       ├── DEPLOY_PLAN_Supplier_Invoice.md
│       └── APPROVAL_PROCESS_SETUP_Supplier_Invoice.md
└── sfdx-project.json
```

> A `resources/` mappa tartalma nem kerül deployra (nem Salesforce-metaadat) — pusztán
> a verziókövetés és az átadhatóság miatt él egy helyen a projekttel. A `.forceignore`-ba
> nem kell felvenni, mert a `force-app`-on kívül van, de ha a deploy mégis beszippantaná,
> tedd a `resources/`-t a `.forceignore`-ba.

## 6. Ellenőrzés retrieve után

- A `force-app/main/default/approvalProcesses/` alatt megjelent-e az `.approvalProcess-meta.xml`?
- Az `objects/Supplier_Invoice__c/validationRules/` alatt a validation rule?
- A `flows/` alatt a flow?
- A `workflows/Supplier_Invoice__c.workflow-meta.xml`-ben ott a 4 field update?
- Próbaképp egy **`deploy_metadata --dry-run`** (validate-only) ugyanarra az org-ra: hiba nélkül lefut-e? Ez igazolja, hogy a retrievelt forrás önmagában konzisztens.
