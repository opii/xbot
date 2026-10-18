# Spajanje vrha i dna: Komanda → Operateri → Voter (kladionice)

**Projekat:** Cacix · **Datum:** Oktobar 2026. · **Izvor:** Postgres `progress` + Neo4j graf

Ovaj dokument spaja tri tačke u jedan lanac i daje **kristalno jasnu heuristiku
odlučivanja** (za ljude i za agente) iza svakog zaključka.

---

## 1. Lanac (sažetak)

```
KOORDINATOR (task-master)  →  OPERATERI (graf)  →  VOTER (kladionice)
 zadaje zadatak za portal     objave komentare       automatski izglasa
 sa direktivom (kvota)        pod deljenim šablonom   komentare za sekunde
 vu_korisnik_id               CO_TEMPLATE / burst     knv_voter_vreme
```

- **Komandni sloj** je mali i odvojen: **135 ljudi kreira SVE zadatke** za portale, od toga **21 su koordinatori**. Oni ne izvršavaju sami — zadaju.
- **Izvršni sloj** su operateri u grafu (centroidi/organizatori) koji unose komentare.
- **Voter sloj** je fizička infrastruktura (terminali u kladionicama, RS + Afrika) koja automatski izglasa komentare — **217.044 glasa padne u 10 s** od objave komentara.

---

## 2. RQ1 — Ko komanduje (task-masteri → koordinatori)

**Nalaz:** 135 kreatora zadataka; 21 koordinator. #1 **Nenad Stamenković —
165.074 zadatka** (okrug+opština+region koordinator, Jablanički). Komandni sloj
je **iznad** grafa: task-masteri uglavnom imaju nizak `tw_org/cc_org` (ne
izvršavaju), ali kreiraju ogroman broj zadataka. Samo 1 task-master je i centroid.

**Heuristika (kako se identifikuje task-master):**
- Task-master = `vu_korisnik_id` iz `arhiva_vesti_unos`, rangiran po broju
  kreiranih zadataka (`count(*)`).
- Koordinatorski status = `true` ako je u `koordinatori_korisnici`
  (`okrug/opstina/region_koordinator` flag) ILI u `okrug_koordinator` /
  `opstina_koordinator` tabeli.
- „Komandni sloj iznad grafa" = task-master sa visokim brojem zadataka ali niskim
  `max(tw_org, cc_org)` (ne izvršava, samo zadaje).
- *Napomena:* `#0` (108.874 zadatka) su automatski kreirani (`vu_automatika_kreirala`).

## 3. RQ2 — Kladionice ↔ centroidi (geografsko preklapanje)

**Nalaz:** Opštine sa uplatnim mestima kladionica imaju i jake operaterske
klastere/centroide. Vrh: Novi Beograd (21 kladionica, centroid, maxOrg 0,69),
Kula (11, maxOrg **1,0**), Požarevac (10), Zrenjanin/Kruševac (9). Po okrugu:
Beograd 🎰45, Sremski 🎰25, Zapadnobački 🎰25, Raški 🎰18.

**Heuristika (kako se kladionica mapira na opštinu):**
- Ime mašine `vr_naziv_ss` → opština: normalizacija dijakritika (ć→c, š→s…),
  pa **match ako je normalizovano ime opštine prefiks imena mašine** na granici
  reči/cifre (npr. „Sombor 3" → Sombor), + mali alias rečnik za kvartove
  (Borča→Palilula, Laćarak→Sremska Mitrovica, Sivac→Kula, Enjub/Roma→Novi Beograd).
- Mapirano je ~16% mašina (266/1.668); ostatak su **regionalni** (CG/BiH: Bar,
  Berane, Brčko, Banjaluka), **afrički** (Brazavil, Bertoua…) ili **brendovi**
  (Scooorebet, Maxi, Joker) bez opštine u imenu.
- „Preklapanje" je **geografsko, ne direktna veza**: voter mašine nemaju
  `korisnik_id`, pa merimo *da li u istoj opštini postoje i kladionice i jaki
  operateri/centroidi*, ne da je konkretni operater vezan za konkretnu mašinu.

## 4. RQ3 — Vremenska sinhronija (dokaz automatizacije)

**Nalaz:** `arhiva_komentari_na_vestima.knv_voter_vreme` nosi **4,5M glasova sa
sekundnim vremenom**. Latencija komentar→voter udar: **medijana 111 s**,
**217.044 glasa u <10 s**, 1,57M u <60 s. Niko ljudski ne izglasa 217k komentara
u 10 s — to je automatsko pojačavanje. (Druga strana lanca, zadatak→komentar, već
je pokrivena *burst* analizom: operateri reaguju u minutima, lideri u sekundama.)

**Heuristika (šta znači „automatizacija" ovde):**
- Latencija = `knv_voter_vreme − knv_vreme_kreiranja` (samo `knv_voter_aktiviran=1`,
  pozitivna razlika).
- Signal automatizacije = **masovni kratki rep**: desetine hiljada glasova u
  sekundama od objave komentara (brzina koju čovek ne može ručno).

---

## 5. Heuristika odlučivanja — zbirno (kristalno jasno)

Svaki prag je **izbor**; rezultate čitati uz njega. Promena praga menja brojeve.

| Pojam | Pravilo (tačno) | Hvata | Ograničenje |
| --- | --- | --- | --- |
| **Task-master** | top po `count(*)` u `arhiva_vesti_unos` po `vu_korisnik_id` | ko kreira zadatke za portale | `#0` = automatika |
| **Koordinator** | flag u `koordinatori_korisnici` ili u `okrug/opstina_koordinator` | formalna komandna uloga | ne pokriva neformalne vođe |
| **Kladionica→opština** | normalizovano ime opštine = prefiks `vr_naziv_ss` (granica reči/cifre) + alias kvartova | RS uplatna mesta | 16% match; strani/brendovi ostaju |
| **Kladionica↔centroid** | ista opština ima i kladionicu i operatera sa `tw/cc_organizer` ili visok `*_org` | geografsko preklapanje vrha i infrastrukture | nije direktna veza (voter nema korisnik_id) |
| **Voter automatizacija** | `knv_voter_vreme − knv_vreme_kreiranja` < 10 s za desetine hiljada glasova | mašinsko izglasavanje | zavisi od tačnosti portalskih timestamp-a |
| **Strana infrastruktura** | GeoIP (iptoasn) ASN/država voter IP-jeva | zakupljeni strani/afrički proksiji | country+ASN (bez grada) |

Ranije definisane bihevioralne heuristike (auto/lead/template/toxicity/
infiltrator/farm/shift…) su u [`AGENTS.md`](../AGENTS.md), sekcija „Heuristike i
definicije".

---

## 6. Ograničenja

- Voter mašine (`voter_racunari`) i glasovi (`knv_voter_*`) **nisu vezani za
  pojedinačne operatere** (`korisnik_id` postoji na glasu, ali mašina nema vezu
  ka operateru) — zato je spoj vrh↔infrastruktura geografski/vremenski, ne 1:1.
- Mapiranje kladionica na opštinu je best-effort (16%); za potpuniju sliku treba
  ručni rečnik uplatnih mesta.
- Reprodukcija: `src/analysis/{task_masters,betting_geo,voter_timing,voter_geoip}.py`;
  rezultati u `data/geo/*.json`.
