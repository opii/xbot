# AGENTS.md — Cacix

Orijentir za agenta koji nastavlja rad na ovom projektu. Kratko: šta je sistem,
gde šta stoji, kako se pokreće i šta se NE radi.

## Šta je ovo
Sistem za **mrežnu i bihevioralnu analizu** koordinisane mreže naloga, nad
realnom bazom jedne organizacije koja svojim članovima dodeljuje zadatke na
društvenim mrežama (lajk/retvit/odgovor/citat na tvit, komentarisanje vesti) i
beleži ko je šta uradio.

Pristup je **operater-centričan**: čvor je *operater* (osoba-`korisnik`), ne
pojedinačni nalog. Razlog: akcije su u bazi pripisane operateru, a ~97% naloga je
obrisano. Mreža je dakle *ground-truth* koordinacije, ne pretpostavljeni botovi.
Ne radimo klasifikaciju "da li je nalog bot" — **mapiramo postojeću koordinaciju
i merimo ponašanje**.

## 🎯 GLAVNI CILJ (Primarni fokus istraživanja)
**Povezivanje fizičke infrastrukture za glasanje (uplatna mesta kladionica u Srbiji i Africi) sa operaterskom mrežom (centroidi, koordinatori, master čvorovi).**
Otkriveno je da je voter mašinerija (550M lažnih glasova) radila direktno sa terminala u uplatnim mestima kladionica u Srbiji (`Borca`, `Pozarevac Centar`, `Zrenjanin 3`, `Roma NBG`...) i njihovih franšiza u Africi (`Scooorebet 13`, Brazavil, Bertoua...).
**Zadatak za agente:** mapirati koji koordinatori iz baze zadaju zadatke za ove portale, koji centroidi zajednica u Neo4j grafu upravljaju tim opštinama/klasterima, i kako se vremenski sinhronizuju komentari operatera sa automatskim voter udarima sa terminala kladionica. Detaljan izveštaj: [`docs/voter_kladionice_infrastruktura.md`](docs/voter_kladionice_infrastruktura.md).

## Značaj dataseta (zašto je jedinstven)

U akademskim/OSINT istraživanjima astroturfinga (Stanford Internet Observatory,
Graphika, DFRLab) mreža se posmatra **spolja** (API/skrejper) i *nagađa* se ko je
bot. Ovde imamo **unutrašnji ground-truth samog sistema**: tačno se zna ko je
operater, ko mu je dao zadatak, sa koje mašine je radio, koja je bila direktiva
(`tu_smernica`) i koliko je poena dobio (`izvestaj_dnevni`). Zato Cacix ne nagađa
— on **mapira i meri** stvarnu koordinaciju. Rukovati u skladu s tim (realni
ljudi, osetljivi podaci — vidi Pravila).

## Podaci
- Izvor: `bot_detector/data/progress_baza_podataka.sqlite3` (~4,8 GB, van gita).
- Uvezeno 1:1 u Postgres šemu `progress` skriptom
  [`bot_detector/src/import_progress_db.py`](bot_detector/src/import_progress_db.py)
  (57 tabela, ~12 GB, idempotentno; `--force` za ponovni uvoz; dekodira `\uXXXX`).
- Ključne tabele: `arhiva_twitter_unos` (zadaci), `arhiva_twitter_unos_korisnici_akcije`
  (11,8M akcija; `tuka_akcija` 0=lajk,1=retvit,2=odgovor,3=citat), `korisnici`
  (operateri), `korisnici_twitter_nalozi` (nalozi), `arhiva_vesti_korisnici_komentari`
  (16,3M; ~4,4M realnih, ostalo `vkk_simulacija=1`).
- **Provera escape-a u Postgresu:** NE koristi `LIKE '%\u%'` (Postgres LIKE tretira
  `\` kao escape → matchuje slovo 'u'); koristi regex `~ '\\u[0-9a-fA-F]{4}'`.

## Arhitektura
- **Postgres** (`progress`): sve tabele + izvedene `target_popularity`,
  `news_popularity`, `target_bursts`.
- **Neo4j**: operaterska mreža. Čvorovi `Operator`, `Account`; veze `CONTROLS`,
  `CO_ACTED` (tviter), `CO_COMMENTED` (komentari), `CO_TEMPLATE` (deljeni tekst).
  Operateri nose: `co_degree`/`cc_degree`, komentar-statistiku, bihevioralne skorove
  (`auto_score`, `lead_score`, `template_frac`, `reg_score`, `dup_ratio`, `role`,
  `farm_ratio`/`farm_machine`, `work_hours_pct`/`weekend_ratio`/`shift_archetype`),
  i po sloju `{tw,cc}_community/_pagerank/_betweenness/_org/_organizer`.
- **Amplifikacija** (operater→meta, 9,4M parova) se NE drži u Neo4j — servira se
  uživo iz Postgresa.
- **API**: FastAPI [`bot_detector/src/api/main.py`](bot_detector/src/api/main.py) na `:8000`.
- **Frontend**: React+Vite [`bot_detector/dashboard-ui/`](bot_detector/dashboard-ui/)
  na `:5173`; glavna komponenta `src/GraphExplorer.jsx`.

## Build skripte
- [`src/graph/load_graph.py`](bot_detector/src/graph/load_graph.py) — gradi Neo4j
  graf iz Postgresa + izvedene tabele; na kraju poziva detektor organizatora.
  Pragovi: `--coact-ceil/min`, `--cocom-ceil/min`.
- [`src/graph/detect_organizers.py`](bot_detector/src/graph/detect_organizers.py) —
  networkx: odsecanje težina p5–p95 (`--lo/--hi`), Louvain zajednice, PageRank +
  betweenness, `organizer_score`, centroid po zajednici; upisuje u Neo4j.
- [`src/graph/behavior_scores.py`](bot_detector/src/graph/behavior_scores.py) —
  cela bihevioralna analiza (upisuje na Operator čvorove + Postgres tabele):
  `auto_score` (night+entropy+short_lat, prigušeno `min(1,akcije/50)`), `lead_score`
  (ko prvi na meti), `template_frac` + `CO_TEMPLATE` veze (deljeni tekst),
  `dup_ratio`, `reg_score` (regularnost ritma), `role` (Pojačivač/Odgovarač/Mešovit),
  `farm_ratio`/`farm_machine` (serverska mašina), `work_hours_pct`/`weekend_ratio`/
  `shift_archetype` (smene), i tabele `target_bursts`/`target_popularity`/`news_popularity`.
  Napomena: `avg`/`stddev_pop`/`extract` vraćaju Decimal — kastuj u `float()` pre Neo4j upisa.

Napomena: `load_graph.py` na kraju poziva i `detect_organizers` i
`behavior_scores`, pa jedan poziv uradi sve (~85s).

## API endpointi (ključni)
`/api/overview?layer=&okrug=&opstina=`, `/api/expand/{id}?layer=&frm=&to=`,
`/api/operator/{id}`, `/api/target/{handle}`, `/api/account/{id}`, `/api/search`,
`/api/regions`, `/api/organizers?layer=&only_centroids=`, `/api/crosslayer`
(master koordinatori), `/api/behavior/{id}` (ritam/radni dani/latencija/timeline/
miks/duplikati), `/api/behavior_top?metric=&layer=` (metrike: auto/night/short_lat/
dup/lead/template/reg/farm/pseudonyms/toxicity/infiltrator; `template` koristi CO_TEMPLATE), `/api/behavior_cohort`
(decili), `/api/bursts` + `/api/burst/{tid}` (kampanje/nalet po minutu + lideri),
`/api/path?a=&b=&layer=&max_pop=` (putanja + spone), `/api/stats`,
`/api/export/operator/{id}`, `/api/taskmasters`, `/api/command_voter`,
`/api/directives?top=` (taksonomija+lanac+SS/ČET izvor), `/api/coordinators`
(hijerarhija Region→Okrug→Opština + raspon kontrole), `/api/cascade` (SS prioritet
+ vrh koplja + ritam + izdavač→okrug), `/api/voter_geoip` (države/ASN voter mašina
+ udeo Afrike + tajming), `/api/voter_timing` (cirkadijalna analiza: satnica po
državi), `/api/export/investigation_dossier` (ceo dosije, Markdown download).
Node id šema: `op:<id>`, `acc:<id>`, `tgt:<handle>`,
`portal:<name>`, `news:<vid>`. Operater nosi `auto_score` (+komponente),
`lead_score`, `template_frac`, `reg_score`, `dup_ratio`, `role`, `farm_ratio`/
`farm_machine`, `shift_archetype`/`work_hours_pct`/`weekend_ratio`, `tw_org`/`cc_org`,
`tw_community`/`cc_community`. Slojevi veza: CO_ACTED, CO_COMMENTED, CO_TEMPLATE.
FE: levi meni; pogledi Pregled/Geografija/Uloge/Smene/Portali/Organizatori/Master, bihevioralne
metrike (…/farm), Kampanje, Komanda (Task-masteri / Komandna odgovornost & Voter /
📋 Direktive / 🏛 Koordinatori / ⏱ Kaskada), Voter infrastruktura (🌍 Voter/GeoIP —
Afrika, sa satnicom mašina Srbija vs strano); denoising klizač „min jačina veze"
+ „sakrij izolovane"; u Alatkama dugme „📑 Istraživački dosije" (download).

## Kako pokrenuti
```bash
cd bot_detector
docker compose up -d                 # postgres + neo4j (perzistentni volumeni)
./venv/bin/python src/import_progress_db.py          # jednom (ako progress prazna)
./venv/bin/python src/graph/load_graph.py            # graf + organizatori
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir src
cd dashboard-ui && npm run dev                        # :5173
```
Alternativa za graf: `docker compose --profile init up graph_loader --build`.

Napomena o okruženju (host): `./venv/bin/python` je venv; `docker` postoji,
`sqlite3` CLI NE. Pri gašenju API-ja NE koristi `pkill -f uvicorn` (ubija i
sopstvenu ljusku jer komanda sadrži reč) — gasi po portu preko `ss`.

## Stanje (2026-10-18)
Kompletno i provereno (backend + frontend, gurnuto na GitHub): uvoz, graf tri
sloja (CO_ACTED/CO_COMMENTED/CO_TEMPLATE), levi meni sa svim pogledima
(Pregled/Uloge/Smene/Organizatori/Master), bihevioralne metrike (auto/night/
short_lat/dup/lead/template/reg/farm) + pun profil sa bedževima (farma, arhetip),
Kampanje (burstevi + timeline), putanje (+diskriminativne spone), denoising
(klizač + sakrij izolovane + Serrano backbone), izvoz/uvoz. Veze nose `backbone`.
Jedan `load_graph.py` gradi sve (graf + organizatori + skorovi + burstevi, ~3min).
Dodatne analize (van `load_graph.py`, svaka piše `data/geo/*.json` i ima UI/API):
voter GeoIP, kladionice↔opštine, task-masteri, komandna odgovornost & voter,
**analiza direktiva** (`directives.py` → „📋 Direktive"), **hijerarhija koordinatora**
(`coordinators.py` → „🏛 Koordinatori"), **vremenska kaskada** (`cascade.py` → „⏱ Kaskada"),
**cirkadijalni režim** (`voter_timing.py` → satnica u GeoIP pogledu), **korporativni
tragovi** (`betting_corporate.py`) i **generator dosijea** (`/api/export/investigation_dossier`).

## Ključni nalazi (zaključci)

Centralni zaključak: **ovo nisu klasični automatizovani botovi nego organizovani
ljudi koji rade u smenama — ali je koordinacija vrlo jaka i merljiva.** Dokazi:

- **Ljudski obrazac, ne automatizacija.** `auto_score` max ~0,45 (nema ekstremnih
  vrednosti); medijana latencije zadatak→akcija ~1h (ne sekunde); noćna aktivnost
  blizu 0 kod većine; regularnost ritma blaga. Vrh aktivnosti 9–16h, pad vikendom.
- **Rad u smenama / državna služba.** 311 operatera je „Kancelarijski" arhetip
  (pon–pet 08–16h), od toga **131 radi 100% u radno vreme sa 0% vikenda**. Uz to
  21 „Noćna smena" i 251 „Vikend".
- **Hardverska farma.** 1.938 operatera izvršava deo akcija preko namenskih
  serverskih mašina: **KANCELARIJASBB** (1.241 op), **INDJIJA2** (411), **INDJIJA1**
  (286). Ukupno 191.390 akcija (09/2024–06/2025).
- **Orkestracija je jaka (vojnička sinhronija).** U **12% kampanja (~4.800 od
  39.143)** preko **85% operatera reaguje u prvih 10 min** (medijana sinhronije je
  niža, ~0,18 — nisu sve kampanje jednako tesne). U najtešnjim lideri reaguju u
  razmaku od **sekundi** (0s, 2s, 5s…). Lideri (`lead_score` ~0,72) prvi na 10–17k meta.
- **Industrija lažnih identiteta (astroturfing).** U komentarima na vestima jedan
  operater piše pod stotinama/hiljadama pseudonima (kolona `vkk_autor`): npr. op
  **#7418** = 17.088 komentara pod **2.378** imena; op **#6206** = 79.951 komentar
  pod **1.338** imena. Uz to duplikati do **96%** i **100% šablonskog teksta**
  (`template_frac`); 22k identičnih šablona vrti cela mreža.
- **Uloge.** Mreža je prvenstveno „Odgovarači" (uputstvo zadataka je „odgovaramo").
- **Jurišni odredi (toksičnost).** Mreža ne napada sve jednako: stranačke mete
  (`sns_srbija`, `avucic`, `milos_vucevic`) dobijaju quote/like (hvalospevi), a
  opozicija/kritički mediji (`onlinedanas`, `n1srbija`, `kpromeni`, `novarsonline`,
  `slobageorgiev`…) isključivo napadačke odgovore pod direktivama „brutalno/zezamo/
  pukli". 520 operatera je „Jurišnik"; npr. #2656 ima 3.882 napada, a top mete su
  baš kritički mediji. Preko 150k napadačkih odgovora ukupno.
- **Tretman portala (Infiltrator vs Podrška).** Kritički mediji dobijaju 1M+
  komentara uz ~0,9% prolaznosti (moderacija seče 99%), a mreža ih i dalje zasipa;
  tabloidi ~32% prolaznosti. Npr. #6206 je poslao 31.653 komentara na kritičke
  medije od kojih je prošao **1**. 302 operatera su „Infiltratori".
- **Kladioničarska i strana/afrička voter infrastruktura.** Automatsko glasanje
  (`voter_racunari`, 550M klikova) radilo je sa terminala **uplatnih mesta kladionica
  u Srbiji i Africi** (kolona `vr_naziv_ss`): domaća uplatna mesta (`Borca`,
  `Pozarevac Centar`, `Zrenjanin 3`, `Roma NBG`, `Krusevac Bronks 2`, `Enjub Blok 45`...)
  i afričke franšize pod brendom **`Scooorebet 13`**, `Casino`, `Joker` u Kongu
  (Brazavil/Rue Mbochis, Nkayi) i Kamerunu (Bertoua, Nkongsamba). **63% zapisa / 80%
  distinct IP van Srbije**. Najveći domaći ASN je AS8400 TELEKOM-AS (MTS, 251), ali
  najveći strani otisak su **afrički mobilni provajderi**: CAMNET Kamerun (472 IP!),
  MTN, Orange Cameroon, Congo Telecom, Tanzanija, Obala Slonovače. Detaljna studija:
  [`docs/voter_kladionice_infrastruktura.md`](docs/voter_kladionice_infrastruktura.md).
  Offline GeoIP: `src/analysis/voter_geoip.py` → `data/geo/voter_geoip.json`;
  u UI pogled „🌍 Voter/GeoIP (Afrika)" preko `/api/voter_geoip` (Afrika 66% IP,
  Kamerun #1 sa 472 — ispred Srbije 216).
- **Cirkadijalni režim (radno vreme vs 24/7).** Glavni tok glasanja
  (`knv_voter_vreme`, 4,49M) ima jasan noćni pad (00–08h = 7,7%, min 3–4h) = **nije
  ravan 24/7 daemon**, prati dnevni ritam uz rep do ~22h. Srpske mašine se javljaju
  naglo u **9h** (otvaranje lokala → ljudski start), strane (afričke) raspoređenije
  sa jačim večernjim/noćnim repom (pre ostaju online). Granica: podela po državi
  koristi `vr_vreme`/`vrgc` (glavni tok nema državu). `src/analysis/voter_timing.py`.
- **Korporativni tragovi kladionica (bez vlasništva).** 182 mašine nose brend u
  `vr_naziv_ss` (Maxi 92/87 strano, Scooorebet 59 sve strano, Joker, Roma, Casino).
  Vlasništvo NIJE u bazi → APR/UIS; „Scooorebet"(Afrika)≠„Soccerbet"(Srbija) bez
  primarnog izvora. `src/analysis/betting_corporate.py`,
  [`docs/vlasnicki_profil_kladionica.md`](docs/vlasnicki_profil_kladionica.md).
- **Direktive (šta se naređuje).** 99% tviter smernica je čista akcija
  (`odgovaramo`/`fv`/`kv`/`rt`); eksplicitno napadačkih samo 2.712, odbrambenih
  1.446. Ton napada se vidi u IZBORU METE, ne u tekstu: 587 eksplicitnih
  napad-odgovora na opoziciju vs **113.991** odgovora na iste opozicione mete pod
  generičkim „odgovaramo". Najtešnja sinhronija je **pro-režim amplifikacija**
  (`neutral→režim` burst10=0,304, duplo iznad proseka). Moderacija: kritički mediji
  propuštaju ~3%, tabloidi 33–49% (napad-ton na tabloidu 40,8%). Postoji **centralni
  komandni izvor**: 1.099 „super specijal (SS)" + 70 „iz četa" direktiva, 30
  izdavača; većina izdavača SS-a NIJE jaka u grafu (org≈0) = zaseban administrativni
  komandni sloj. **Fer play:** kreator = ko je UNEO smernicu; „Šef/čet" u tekstu
  referišu na uzvodnog lidera koji NIJE nužno red u bazi. Detalji:
  [`docs/analiza_direktiva.md`](docs/analiza_direktiva.md).
- **Koordinatori: komanda ≠ izvršenje.** Komandna struktura je geografska (Region
  7 → Okrug 26 → Opština 162); 156 koordinatorskih pozicija (5+15+136) + 22
  zamenika. **Od 156 koordinatora, 139 se vidi u grafu ali 0 su grafni centroidi**
  (od 16 centroida nijedan nema titulu); samo 4 izdaju SS direktive. Formalna
  komanda (geografska nadležnost) i izvršna moć (centralnost u mreži) su RAZDVOJENI
  slojevi — dosledno nalazu da su i SS-izdavači org≈0. Centroidi i 🎰 koncentrisani
  u Vojvodini/Beogradu. Detalji: [`docs/analiza_koordinatora.md`](docs/analiza_koordinatora.md).
- **Kaskada: SS ima prioritet + vrh koplja.** Centralni (SS/ČET) zadaci propagiraju
  **17,6% brže** (medijana prve reakcije 582s vs 707s baseline). „Vrh koplja" (prvi
  reagent) su **Južnobački (Novi Sad), Beograd, Srednjobanatski (Zrenjanin)** —
  otvaraju kampanju. SS direktive se izvršavaju **prekoregionalno** (izdavač u
  jednom okrugu, izvršenje u Beogradu/Vojvodini) = centralni kanal, ne lokalna
  stvar. Detalji: [`docs/analiza_kaskade.md`](docs/analiza_kaskade.md).
- **Mete.** Masovne mete (npr. `@sns_srbija` — dira je 3.608 operatera) su šum za
  povezivanje; prava koordinacija se vidi na retkim, deljenim metama.

Sve brojke su reproducibilne iz Postgresa/Neo4j nakon `load_graph.py`.

## Heuristike i definicije (sve metrike i veze)

Svi pragovi su izbori — menjaju gustinu/osetljivost; čitati rezultate uz njih.

**Veze (slojevi koordinacije), svi operater–operater, težina = broj deljenog:**
- `CO_ACTED` (tviter): dele **diskriminativne mete** — tvitove koje dira 2–30
  operatera (ceil izbacuje mase); prag ≥4 deljene mete. `--coact-ceil/min`.
- `CO_COMMENTED` (komentari): dele vesti koje komentariše 2–20 operatera; prag ≥5.
  `--cocom-ceil/min`. Gust sloj (prosečan stepen ~113).
- `CO_TEMPLATE` (tekst): dele isti **normalizovan** komentar (lower + collapse
  whitespace, dužina ≥15) koji koristi 3–60 operatera; prag ≥3 deljena šablona.

**Bihevioralne metrike na operateru (sve 0..1 osim role/machine/archetype):**
- `auto_score` = (0,4·night + 0,3·entropy + 0,3·shortLat) · min(1, akcije/50).
  night = udeo akcija 00–05h; entropy = ravnomernost rasporeda po satu (1 = 24/7);
  shortLat = udeo akcija <2 min od zadatka. Prigušenje sprečava lažno visok skor
  kod malo akcija. Viši = sličnije botu.
- `lead_score` = po meti (5–500 operatera) rang po vremenu prve akcije, prosek
  udela ko-aktera koje je operater pretekao; prag n≥20 meta. 1 = stalno prvi.
- `dup_ratio` = 1 − distinct/ukupno komentara (exact). `template_frac` = udeo
  komentara čiji tekst koristi ≥3 operatera (deljeni, near-exact).
- `pseudonyms` = count(distinct `vkk_autor`) (vkk_simulacija=0, autor≠''): broj
  lažnih identiteta pod kojima operater komentariše. Raspodela: medijana 9, p90
  134, max 2.378.
- `reg_score` = m/(m+s) razmaka između uzastopnih akcija (n≥30). Viši = pravilnije.
- `role` = `Odgovarač` ako (reply+quote)/tot>0,5; `Pojačivač` ako (like+rt)/tot>0,8;
  inače `Mešovit`.
- `farm_ratio` = udeo akcija preko `tuka_program_racunar`; `farm_machine` = mode
  mašine (ili null).
- `toxic_attacks` = odgovori (akcija=2) na opozicione mete ILI uz agresivnu
  direktivu (`tu_smernica ~* brutalno|zezamo|sprdamo|hejt|lazov|resavamo|pukli`;
  generičko „odgovaramo" se NE broji) + komentari na kritičkim portalima
  (n1info/danas/nova/juznevesti/vreme/radar). `toxicity_score` = (toxic_attacks/
  total)·min(1, toxic_attacks/40). `toxicity_level`: Ekstremna (Jurišnik) [score≥0,4
  ili attacks≥300] → Visoka [≥0,2] → Umerena [≥0,08] → Netoksičan (Pojačivač).
  520 operatera je „Jurišnik". Opozicioni handle-set je kurirani (vidi kod).
- `infiltrator_ratio` = kritički / (kritički+tabloid) komentari (prag ≥20 komentara).
  `portal_role`: Infiltrator (≥0,6) / Podrška (≤0,3) / Mešovit. Kritički mediji
  (n1info/nova/danas/juznevesti/vreme/radar) imaju ~0,9% prolaznosti moderacije,
  tabloidi (informer/alo/kurir/novosti) ~32%. 302 Infiltratora.
- `work_hours_pct` = pon–pet 08–15h; `weekend_ratio` = sub/ned. `shift_archetype`
  (redosled provere): `Kancelarijski` (work≥0,75 i weekend<0,1) → `Noćna smena`
  (night≥0,25) → `Vikend` (weekend≥0,40) → `Mešovit / 24-7`.

**Graf-analiza:**
- **Zajednice**: Louvain (težinski) po sloju, nad grafom odsečenim na p5–p95 težina
  (izbacuje „svi-sa-svima" i najslabije). `--lo/--hi`.
- **Organizator/centroid**: `organizer_score` = 0,5·norm(PageRank)+0,5·norm(betweenness);
  centroid = max u svojoj zajednici.
- **Master**: `master = √(tw_org · cc_org)` — jak u OBA sloja.
- **Putanja**: `shortestPath` nad izabranim slojem; spone = konkretne deljene
  mete/vesti po skoku; `max_pop` filtrira masovne mete (diskriminativne spone).
- **Burst**: po meti (≥8 op), nalet u prvih 10 min; sinhronija = peak10/ukupno.
- **Denoising**: (a) klizač „min jačina veze" (prag na `shared`, adaptivni max) +
  „sakrij izolovane" — UI, uživo; (b) **Serrano disparity filter** (backbone):
  za čvor i stepena k, p_ij=w_ij/s_i, α_ij=(1−p_ij)^(k−1); veza je `backbone=true`
  ako je α<0,05 iz BAR JEDNOG kraja (OR pravilo; stepen 1 se čuva). Računa se u
  `detect_organizers.disparity_backbone()` za CO_ACTED/CO_COMMENTED/CO_TEMPLATE;
  UI prekidač „samo backbone". Čuva male opštinske klastere, seče hairball
  (CO_COMMENTED 131k→~12k značajnih).

**Mapiranja/gotcha:** `tuka_akcija` 0=lajk,1=retvit,2=odgovor,3=citat (potvrđeno
vs `izvestaj_dnevni`). `tuka_korisnik_id`→`korisnici.k_id` (akcije pripisane
operateru). Komentari: samo `vkk_simulacija=0` su realni. Handle mete se vadi iz
`tu_link_tvita`. Neo4j Cypher alias traži `AS`. Decimal iz PG → `float()`.

**Direktive (`tu_smernica`/`vu_smernica`) — taksonomija + lanac — heuristike:**
- **Taksonomija** (na NORMALIZOVANOM tekstu: lower + ćirilica→latinica + bez
  dijakritika): 4 dimenzije — `action` (tviter pouzdano iz `tu_akcija` 0/1/2/3,
  inače iz teksta), `tone` (napad=`brutalno|zezamo|sprdamo|hejt|resavamo|pukli|
  lazov|razbij|rafal`, odbrana=`branim|hvalim|podrsk|slavim|cestit|cuvamo`, inače
  neutral), `source` (SS=`super ?spec|iz ss`, ČET=`iz cet|video iz cet`,
  ŠEF=`sef|sefov`, automatika=`vu_automatika_kreirala`), `cross` (deljenje na
  mrežama). Generičko „odgovaramo" NIJE napad (isto kao toksičnost).
- **Lanac**: ton × klasa mete (`tu_link_tvita` handle → opozicija/režim/ostalo) +
  reakcija (medijana latencije `tuka_vreme−tu_kreirano_vreme`, `burst10`=udeo <10min).
  Za vesti: klasa portala × prolaznost moderacije (`objavljeno/prijavljeno`). Ton/
  lanac koriste RAW AGG/SUP regex (konzistentno sa toksičnošću); taksonomija radi
  na normalizovanom tekstu — mala neslaganja u brojevima su očekivana.
- **Centralni izvor**: izdavač = `tu_kreirano_korisnik_id`/`vu_korisnik_id` sa
  SS/ČET oznakom; spoj na `korisnici`+koordinatore+graf (org). **GRANICA (fer
  play):** kreator = ko je UNEO; „Šef/čet" referišu na uzvodnog lidera koji NIJE
  nužno u bazi — NE izjednačavati kreatora sa „Šefom".

**Koordinatori (hijerarhija + raspon kontrole) — heuristike:**
- **Struktura**: geografska Region→Okrug→Opština (`region`/`okrug`/`opstina`,
  povezane preko `o_region_id`/`op_okrug_id`). Pozicije iz namenskih tabela
  (autoritativne): `region_koordinator`/`okrug_koordinator`/`opstina_koordinator`
  (5/15/136) + `*_zamenici` (22). NE koristiti `koordinatori_korisnici` flagove za
  broj (uglavnom 0; to je membership mapiranje + region-zamenik flag).
- **Raspon kontrole** po čvoru (agregira se naviše): `operators` (korisnici po
  `k_opstina`), `centroids` (Neo4j `tw_organizer`/`cc_organizer` po imenu opštine),
  `command` (distinct `tu_kreirano_korisnik_id ∪ vu_korisnik_id` po opštini),
  `ss_issuers` (kreatori SS/ČET po opštini), `shops` (betting_geo po imenu).
- **Komanda vs izvršenje**: za svih 156 koordinatora proveri `in_graph`,
  `centroid`, `ss_issuer` preko id → Neo4j/SS-set. Nalaz: presek koord×centroid=0.
- **GRANICA (fer play):** raspon = geografska nadležnost, NE dokaz pojedinačnog
  naređenja. Imena koordinatora su realni ljudi — rukovati odgovorno.

**Komanda ↔ voter ↔ kladionice (Faza A/B/C + odgovornost) — heuristike:**
- **Task-master**: `vu_korisnik_id` iz `arhiva_vesti_unos`, rang po `count(*)`.
  Koordinator = flag u `koordinatori_korisnici`/`okrug/opstina_koordinator`.
  Komandni sloj = puno zadataka + nizak `max(tw_org,cc_org)` (zadaje, ne izvršava).
  `#0` = automatika (`vu_automatika_kreirala`). `vu_voter_prioritet` je BINARNO (0/1).
- **Kladionica→opština**: normalizovano ime opštine = prefiks `vr_naziv_ss` (granica
  reči/cifre) + alias kvartova; ~16% match (ostalo CG/BiH/Afrika/brendovi).
- **Kladionica↔centroid**: GEOGRAFSKO preklapanje (ista opština ima i terminal i
  jakog operatera/centroida) — NIJE direktna veza.
- **Voter automatizacija**: `knv_voter_vreme − knv_vreme_kreiranja`; medijana 111s,
  217k glasova <10s = mašinsko pojačavanje.
- **VOTER privilegije**: `korisnici_privilegije` ILIKE '%voter%' (IZVEŠTAJI_VOTER/
  VOTER_DODATAK/VOTER_KOMENTARI); 61 osoba (109 dodela). Kreditirani glasovi =
  `knv_voter_korisnik_id`.
- **GRANICA ATRIBUCIJE (fer play, obavezno):** `voter_racunari` (mašine, uklj.
  afričke) NEMA `korisnik_id`, a `knv_voter_*` nema referencu na mašinu/IP →
  **NE postoji veza osoba↔mašina/IP**. Zato se „osoba pokreće afričke botove" NE
  sme tvrditi. Atribucija = dodeljena prava + uloge + kreditirani glasovi +
  ko-lokacija (vidi `docs/komandna_odgovornost_i_pravni_osnov.md`), NE pravna presuda.

## Kako proširiti (da naslednik nastavi)

**Nova bihevioralna metrika** (obrazac, ~15 min):
1. U `behavior_scores.py` izračunaj vrednost po operateru (SQL nad `progress`) i
   upiši na Operator čvor (`SET o.<polje>=...`); dodaj reset na vrhu write bloka.
2. U `main.py`: dodaj polje u `op_node(...)` i ključ u `BEHAV_METRIC` (metric→polje).
3. U `GraphExplorer.jsx`: dodaj stavku u `METRICS` ({field, base, norm, label}) —
   automatski se pojavi u meniju „Bihevioralna analiza", boji graf i rang-listu.

**Nov kategorijalni pogled** (kao Uloge/Smene): dodaj boje (npr. `XXX_COLOR`),
granu u `nodeColor` (`view==='xxx'`), `NavItem` u sekciji POGLED, i granu u
`colorLegend`. Podaci idu kroz `overview` (čvorovi već nose polje).

**Nov sloj veza** (kao CO_TEMPLATE): izgradi veze u Neo4j (MERGE), dodaj u
`LINK_STYLE` + `CO_TYPES` (FE) i po potrebi granu u `behavior_top` (rel po metrici).

**Rebuild**: svaka promena skorova/veza = ponovo `behavior_scores.py` (ili ceo
`load_graph.py`). Idempotentno (resetuje na početku).

## Roadmap (otvoreno / sledeće)

- 🎯 **#1 PRIORITET: Povezivanje centroida grafa i koordinatora sa Voter infrastrukturom**:
  - Povezivanje kreatora vesti (`vu_korisnik_id`, `vu_zatvorio_korisnik_id`) sa koordinatorskim strukturama (`koordinatori_korisnici`, `okrug_koordinator`, `opstina_koordinator`).
  - Korelacija centroida zajednica u Neo4j grafu (visoki `cc_org`/`tw_org`) sa geografskim lokacijama gde se nalaze uplatna mesta (npr. Požarevac, Novi Beograd, Kruševac, Zrenjanin).
  - Vremenska sinhronija: zadavanje vesti sa direktivom (`vu_smernica` npr. "500", "max") → objava prvih šablonskih komentara (`CO_TEMPLATE`) → automatski talas glasanja sa afričkih i domaćih terminala kladionica.
- **Pseudonimi kao metrika** (lako, jako): `pseudonyms` = distinct `vkk_autor` po
  operateru (astroturfing identiteti). Već verifikovano: #7418→2.378, #6206→1.338.
  Dodati kao bihevioralnu metriku (obrazac u „Kako proširiti").
- ✅ **Direktive u zadacima** (URAĐENO): taksonomija + lanac direktiva→meta→reakcija
  + centralni izvor SS/ČET. `src/analysis/directives.py`, `/api/directives`, UI
  „📋 Direktive", [`docs/analiza_direktiva.md`](docs/analiza_direktiva.md).
- ✅ **Dublja analiza koordinatora** (URAĐENO): hijerarhija Region→Okrug→Opština +
  raspon kontrole + nalaz „komanda ≠ izvršenje" (0 koordinatora su centroidi).
  `src/analysis/coordinators.py`, `/api/coordinators`, UI „🏛 Koordinatori",
  [`docs/analiza_koordinatora.md`](docs/analiza_koordinatora.md).
- ✅ **Vremenska kaskada** (URAĐENO): SS prioritet (17,6% brže), vrh koplja (prvi
  reagent po okrugu), ritam po satu, izdavač→okrug (prekoregionalni tok).
  `src/analysis/cascade.py`, `/api/cascade`, UI „⏱ Kaskada",
  [`docs/analiza_kaskade.md`](docs/analiza_kaskade.md).
  Sledeće (dublje): kaskada na nivou OPERATERA (lead→follower lanci unutar kampanje,
  ne samo okrug), i veza SS-talasa sa voter udarima sa terminala kroz vreme.
- **Tretman portala**: razlika u ponašanju prema opozicionim portalima vs tabloidi
  (`arhiva_vesti_unos.vu_portal` + glasanje `voter`/`izvestaj_voter`).
- Sinhroni start/stop: preklopljeni dnevni timeline-ovi više operatera (kampanje
  kroz vreme).
- Životni ciklus naloga: kad se nalozi prave/brišu u odnosu na kampanje.
- Deljene mašine kao eksplicitne `SHARED_MACHINE` veze (uz prag; inače hairball).
- Mreža sličnosti teksta preko MinHash/LSH (near-duplicate, ne samo exact-normalized).

## Pravila (važno)
- Čvorovi su **realni ljudi** (operateri), ne anonimni botovi — rukuj imenima
  odgovorno; za deljenje van tima pseudonimizuj u ID-jeve.
- Baza sadrži lozinke, telefone, OAuth tokene (`twitter_kljucevi`),
  `voter_kurir_nalozi` (email+lozinka). Oni se **ne koriste**; NE gradi ništa što
  pristupa tuđim nalozima tim kredencijalima.
- `*.sqlite3` je u `.gitignore` — ne commituj bazu.

## Dokumentacija
Živa dokumentacija (grafovi + bihevioralna analiza) je Claude doc:
https://claude.ai/code/artifact/f44e1f1b-8ec4-4b85-bb11-19f820042143
