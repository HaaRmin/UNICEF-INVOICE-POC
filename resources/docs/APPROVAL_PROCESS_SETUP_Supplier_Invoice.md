# Approval Process beállítása — `Supplier_Invoice__c`

**Lépésről-lépésre, a Salesforce UI-on.** Cél: a számla a területe alapján a megfelelő
területvezetőhöz kerüljön, aki kitölti a megrendelőt és a költséghelyet, majd 1 000 000 Ft
felett a pénzügyi igazgató is jóváhagyja. A státusz végig a számla rekordon látszik.

> A pontos menü-feliratok release-enként kissé eltérhetnek. Ahol „Setup → keresőbe írd be: X",
> ott a Setup jobb felső nagyítóját / Quick Find dobozát használd.

---

## Előfeltételek

1. A `Supplier_Invoice__c` + `Cost_Center__c` objektumok deploy-olva (lásd DEPLOY_PLAN).
2. **Felhasználók** (Setup → Users):
   - `Approver Finance` — **már létezik** (a szerződés-POC-ból). Itt **kettős szerep**: ő a Finance terület vezetője ÉS a pénzügyi igazgató (a 2. szintű jóváhagyó). POC-ben ez elég.
   - `Approver Fundraising` — **hozd létre**.
   - `Approver Advocacy` — **hozd létre**.
   > POC-egyszerűsítés: 4 terület helyett 2 területvezetővel demonstrálunk (Fundraising, Advocacy), így látszik, hogy más területhez más jóváhagyó tartozik. A Communications és Finance terület a POC-ben a Finance approverre eshet (fallback).
3. Mindhárom usernek és a finance officernek ki van osztva a `UNICEF_Szamla_POC` permission set.

---

## A. lépés — A jóváhagyókat eldöntő logika (Flow)

Az approval az `Area_Approver__c` (Lookup User) mezőhöz fog irányítani. Ezt egy Flow tölti ki
az `Area__c` alapján. **Először** szerezd meg a 3 user Salesforce-Id-ját:

- Setup → Users → kattints a userre → az URL-ben a `005…`-tel kezdődő Id. Jegyezd fel mindhármat.

Majd:

1. **Setup → keresőbe: `Flows` → New Flow.**
2. Típus: **Record-Triggered Flow** → Create.
3. **Object:** `Beszállítói számla` (`Supplier_Invoice__c`).
4. **Trigger:** *A record is created or updated.*
5. **Entry Conditions:** `Area__c` **Is Null** = **False** (azaz csak ha van terület). Opcionálisan: `Area__c` Is Changed = True.
6. **Optimize for:** *Actions and Related Records* (azaz „after save" is jó, de mivel ugyanazon a rekordon írunk mezőt, válaszd a **Fast Field Update / before-save** opciót: „Optimize the Flow for: Fast Field Updates").
7. A canvas-on adj hozzá egy **Decision** elemet (`Terület szerinti jóváhagyó`):
   - Outcome `Fundraising`: `Area__c` Equals `Fundraising`
   - Outcome `Advocacy`: `Area__c` Equals `Advocacy`
   - Outcome `Finance`: `Area__c` Equals `Finance`
   - Default outcome: `Communications` (vagy bármi egyéb) → ide a Finance approver jut (POC-fallback).
8. Minden ághoz egy **Assignment** elem, ami beállítja: `{!$Record.Area_Approver__c}` = a megfelelő user Id:
   - Fundraising ág → `Area_Approver__c` = *(Approver Fundraising user Id)*
   - Advocacy ág → `Area_Approver__c` = *(Approver Advocacy user Id)*
   - Finance ág és Default → `Area_Approver__c` = *(Approver Finance user Id)*
   > Before-save Flow-ban közvetlenül a `$Record.Area_Approver__c`-be írsz, mentés nem kell.
9. **Save** (`Számla terület-jóváhagyó kitöltés`) → **Activate**.

**Teszt:** nyiss egy számlát, állítsd `Area__c = Fundraising`, mentsd → a `Terület jóváhagyója`
mezőben az Approver Fundraising usernek kell megjelennie.

---

## B. lépés — Validation rule (a kötelező mezők jóváhagyáskor)

A `Megrendelő` és `Költséghely` rögzítéskor opcionális, de a **területvezetői jóváhagyáshoz
kötelező**. Ezt egy validation rule biztosítja, ami akkor csap le, amikor a státusz a
„Pénzügyi igazgatói jóváhagyásra vár"-ra vált (ezt az 1. jóváhagyási lépés állítja be — lásd D).

1. **Setup → Object Manager → Beszállítói számla → Validation Rules → New.**
2. Rule Name: `Megrendelo_es_Koltseghely_kotelezo_jovahagyashoz`
3. Error Condition Formula:
   ```
   AND(
     ISPICKVAL(Approval_Status__c, "Pénzügyi igazgatói jóváhagyásra vár"),
     OR(
       ISBLANK(Cost_Center__c),
       ISBLANK(TEXT(Orderer__c))
     )
   )
   ```
4. Error Message: `Jóváhagyás előtt kötelező kitölteni a Megrendelőt és a Költséghelyet.`
5. Error Location: Top of Page. **Save.**

**Hogyan hat:** amikor a területvezető jóváhagyja az 1. lépést, a folyamat field-update-tel
„Pénzügyi igazgatói jóváhagyásra vár"-ra állítja a státuszt. Ha ekkor a Megrendelő vagy a
Költséghely üres, a validation rule meghiúsítja a jóváhagyást — a területvezető kénytelen
előbb kitölteni (a rekordot szerkesztve), majd újra jóváhagyni.

> A területvezető a gyakorlatban megnyitja a számlát, kitölti a Megrendelő (picklist) és
> Költséghely (lookup — ha új, előbb létrehozza a Költséghely rekordot) mezőt, **menti**,
> és csak utána kattint a jóváhagyásra.

---

## C. lépés — Az Approval Process létrehozása

1. **Setup → keresőbe: `Approval Processes`.**
2. *Manage Approval Processes For:* válaszd a **Beszállítói számla** objektumot.
3. *Create New Approval Process* → **Use Standard Setup Wizard.**

### C.1 — Process Information
- Name: `UNICEF Beszállítói Számla Jóváhagyás`
- Unique Name: `UNICEF_Beszallitoi_Szamla_Jovahagyas`

### C.2 — Entry Criteria
- *criteria are met* → `Area__c` **not equal to** *(üres)*.
  (Csak terület-tel rendelkező számla léphet be — a „gazdátlan" számla nem indítható.)

### C.3 — Next Automated Approver Determined By
- Válaszd a **`Terület jóváhagyója` (`Area_Approver__c`)** mezőt.
  Ez teszi lehetővé, hogy az 1. lépés dinamikusan ehhez a userhez irányítson.

### C.4 — Record Editability
- *Administrators OR the currently assigned approver can edit records during the approval process.*
  (Kell, hogy a területvezető szerkeszthesse a Megrendelő/Költséghely mezőt jóváhagyás közben.)

### C.5 — (Email template) — POC-ben kihagyható / alapértelmezett.

### C.6 — Initial Submission Actions
- Add → **Field Update**:
  - Name: `Statusz - Teruletvezetoi jovahagyasra var`
  - Field: `Approval_Status__c` → értéke: `Területvezetői jóváhagyásra vár`
- (A „Record Lock" alapból bekapcsol — hagyd.)

Mentsd a folyamatot. Most jönnek a **lépések** és a **végső akciók**.

---

## D. lépés — 1. jóváhagyási lépés (területvezető)

1. A folyamat oldalán: *Approval Steps* → **New Approval Step.**
2. Name: `1. Teruletvezetoi jovahagyas` — Step Number: 1.
3. **Criteria:** *All records should enter this step.* (Minden számla ide lép.)
4. **Assigned Approver:** *Automatically assign using the user field selected earlier*
   (= az `Area_Approver__c`). → Ezzel a Fundraising számla az Approver Fundraisinghez, az
   Advocacy az Approver Advocacyhez kerül.
5. **Approval Actions** (a lépés jóváhagyásakor) → **Field Update**:
   - Name: `Statusz - Penzugyi igazgatoi jovahagyasra var`
   - Field: `Approval_Status__c` → `Pénzügyi igazgatói jóváhagyásra vár`
   > Ez triggereli a B. lépés validation rule-ját — ha üres a Megrendelő/Költséghely, a jóváhagyás elakad. ≤1M számlánál ez a státusz csak átmeneti (a végső akció felülírja).
6. **Rejection Actions** → hagyd üresen (a végső elutasítás kezeli — lásd F).

---

## E. lépés — 2. jóváhagyási lépés (pénzügyi igazgató, csak >1M)

1. *Approval Steps* → **New Approval Step.** Name: `2. Penzugyi igazgatoi jovahagyas` — Step Number: 2.
2. **Criteria:** *Enter this step if the following...* →
   `Gross_Amount__c` **greater than** `1000000`.
   - Az „else" ágnál válaszd: *approve the record* (azaz ≤1M esetén a rekord jóváhagyottá válik a lépés kihagyásával).
3. **Assigned Approver:** *Automatically assign to approver(s)* → **User:** `Approver Finance`
   (ő a pénzügyi igazgató szerepben).
4. **Approval / Rejection Actions:** hagyd üresen — a végső akciók kezelik.

---

## F. lépés — Végső akciók (Final Approval / Rejection)

A folyamat oldalán:

1. **Final Approval Actions** → Field Update:
   - Name: `Statusz - Jovahagyva`
   - Field: `Approval_Status__c` → `Jóváhagyva`
   - (A „Record Lock"-ot állítsd *Unlock*-ra, ha szeretnéd, hogy a jóváhagyott számla még szerkeszthető legyen; POC-ben maradhat lock is.)
2. **Final Rejection Actions** → Field Update:
   - Name: `Statusz - Elutasitva`
   - Field: `Approval_Status__c` → `Elutasítva`
   - Record Lock: *Unlock* (hogy az elutasított rekord kezelhető legyen).

---

## G. lépés — Aktiválás

A folyamat oldalán: **Activate.** (Aktiválás után az entry criteria és a lépés-kritériumok már nem szerkeszthetők szabadon — előbb ellenőrizz.)

---

## H. lépés — Teszt-forgatókönyv (a demóhoz)

A korábban legenerált demo-PDF-ekkel:

| Számla | Állítsd be `Area__c` | Bruttó | Várt útvonal |
|---|---|---|---|
| Kreatív Műhely (marketing) | **Fundraising** | 916 940 Ft | 1. lépés → **Approver Fundraising** → ≤1M → **Jóváhagyva** |
| NetCore (Salesforce) | **Advocacy** | ~3,3 M Ft | 1. lépés → **Approver Advocacy** → >1M → 2. lépés → **Approver Finance** → Jóváhagyva |

Lépések:
1. A finance officer (vagy te) a számla rekordon kiválasztja a `Terület`-et → a Flow kitölti a `Terület jóváhagyója` mezőt.
2. **Submit for Approval** a rekordon. Státusz → „Területvezetői jóváhagyásra vár".
3. Jelentkezz be (vagy válts) az adott területvezetőként → nyisd a számlát → töltsd ki **Megrendelő + Költséghely** → mentsd → **Approve**.
   - Ha üresen hagyod és approve-olsz: a validation rule megállít. (Ezt érdemes a demón megmutatni!)
4. ≤1M: a státusz „Jóváhagyva". >1M: „Pénzügyi igazgatói jóváhagyásra vár" → az Approver Finance approve-ol → „Jóváhagyva".
5. **A „hol akad el" riport:** `Approval_Status__c` + `Area__c` csoportosítva — megmutatja, melyik területvezetőnél vár számla.

---

## Megjegyzések / buktatók

- **Field-update által triggerelt validation rule:** ez a kötelezőség-kikényszerítés szándékolt mechanizmusa. Ha a demón „elsőre" elakadna egy jóváhagyás, az jó — mutatja, hogy a kontroll működik.
- **A 2 user kettős szerepe:** ha az `Area = Finance` számlát tesztelsz, az 1. és 2. jóváhagyó ugyanaz (Approver Finance) lehet — POC-ben elfogadható; éles rendszerben külön pénzügyi igazgató user.
- **`Gross_Amount__c` az értékhatár alapja** — forint-only POC-ben ez közvetlenül a bruttó. (Devizát a POC nem kezel.)
- Ha a „Next Automated Approver Determined By" legördülőben nem látod az `Area_Approver__c`-t: ellenőrizd, hogy a mező **Lookup(User)** típusú és deploy-olva van.
