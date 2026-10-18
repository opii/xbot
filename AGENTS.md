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
dup/lead/template/reg/farm; `template` koristi CO_TEMPLATE), `/api/behavior_cohort`
(decili), `/api/bursts` + `/api/burst/{tid}` (kampanje/nalet po minutu + lideri),
`/api/path?a=&b=&layer=&max_pop=` (putanja + spone), `/api/stats`,
`/api/export/operator/{id}`. Node id šema: `op:<id>`, `acc:<id>`, `tgt:<handle>`,
`portal:<name>`, `news:<vid>`. Operater nosi `auto_score` (+komponente),
`lead_score`, `template_frac`, `reg_score`, `dup_ratio`, `role`, `farm_ratio`/
`farm_machine`, `shift_archetype`/`work_hours_pct`/`weekend_ratio`, `tw_org`/`cc_org`,
`tw_community`/`cc_community`. Slojevi veza: CO_ACTED, CO_COMMENTED, CO_TEMPLATE.
FE: levi meni; pogledi Pregled/Uloge/Smene/Organizatori/Master, bihevioralne
metrike (…/farm), Kampanje; denoising klizač „min jačina veze" + „sakrij izolovane".

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
(klizač + sakrij izolovane), izvoz/uvoz.
Jedan `load_graph.py` gradi sve (graf + organizatori + skorovi + burstevi, ~3min).

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
- **Orkestracija je jaka.** Burstevi: kampanje gde npr. 306 operatera udari metu,
  od čega **262 u prvih 10 min** (sinhronija 0,86), a lideri reaguju u razmaku od
  **sekundi** (0s, 2s, 5s…). Lideri (`lead_score` ~0,72) prvi reaguju na 10–17k meta.
- **Konzervirana poruka.** Duplikati komentara do **96%**; neki operateri imaju
  **100% šablonskog teksta** (`template_frac`); 22k šablona deli ≥3 operatera.
- **Uloge.** Mreža je prvenstveno „Odgovarači" (uputstvo zadataka je „odgovaramo").
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
- `reg_score` = m/(m+s) razmaka između uzastopnih akcija (n≥30). Viši = pravilnije.
- `role` = `Odgovarač` ako (reply+quote)/tot>0,5; `Pojačivač` ako (like+rt)/tot>0,8;
  inače `Mešovit`.
- `farm_ratio` = udeo akcija preko `tuka_program_racunar`; `farm_machine` = mode
  mašine (ili null).
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
- **Denoising**: klizač „min jačina veze" (prag na `shared`, adaptivni max) +
  „sakrij izolovane" — UI, uživo. (Planirano: Serrano disparity filter, vidi dole.)

**Mapiranja/gotcha:** `tuka_akcija` 0=lajk,1=retvit,2=odgovor,3=citat (potvrđeno
vs `izvestaj_dnevni`). `tuka_korisnik_id`→`korisnici.k_id` (akcije pripisane
operateru). Komentari: samo `vkk_simulacija=0` su realni. Handle mete se vadi iz
`tu_link_tvita`. Neo4j Cypher alias traži `AS`. Decimal iz PG → `float()`.

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

- **#3 Serrano disparity filter** (dogovoreno, sledeće): statistički backbone —
  za vezu p_ij = w_ij/s_i, α_ij = (1−p_ij)^(k−1); zadrži α<0,05; upiši
  `backbone:true/false` na `CO_ACTED`/`CO_COMMENTED`; UI prekidač „samo backbone".
  Čisti hairball a čuva male opštinske klastere (bolje od globalnog praga).
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
