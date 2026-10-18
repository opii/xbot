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
  (`auto_score`, `lead_score`, `template_frac`, `reg_score`, `dup_ratio`, `role`),
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
  i tabele `target_bursts`/`target_popularity`/`news_popularity`.
  Napomena: `avg`/`stddev_pop` vraćaju Decimal — kastuj u `float()` pre Neo4j upisa.

Napomena: `load_graph.py` na kraju poziva i `detect_organizers` i
`behavior_scores`, pa jedan poziv uradi sve (~85s).

## API endpointi (ključni)
`/api/overview?layer=&okrug=&opstina=`, `/api/expand/{id}?layer=&frm=&to=`,
`/api/operator/{id}`, `/api/target/{handle}`, `/api/account/{id}`, `/api/search`,
`/api/regions`, `/api/organizers?layer=&only_centroids=`, `/api/crosslayer`
(master koordinatori), `/api/behavior/{id}` (ritam/radni dani/latencija/timeline/
miks/duplikati), `/api/behavior_top?metric=&layer=` (metrike: auto/night/short_lat/
dup/lead/template/reg; `template` koristi CO_TEMPLATE), `/api/behavior_cohort`
(decili), `/api/bursts` + `/api/burst/{tid}` (kampanje/nalet po minutu + lideri),
`/api/path?a=&b=&layer=&max_pop=` (putanja + spone), `/api/stats`,
`/api/export/operator/{id}`. Node id šema: `op:<id>`, `acc:<id>`, `tgt:<handle>`,
`portal:<name>`, `news:<vid>`. Operater nosi `auto_score` (+komponente),
`lead_score`, `template_frac`, `reg_score`, `dup_ratio`, `role`, `tw_org`/`cc_org`,
`tw_community`/`cc_community`. Slojevi veza: CO_ACTED, CO_COMMENTED, CO_TEMPLATE.
FE: levi meni; pogledi Pregled/Uloge/Organizatori/Master, bihevioralne metrike,
Kampanje; denoising klizač „min jačina veze" + „sakrij izolovane".

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
(Pregled/Uloge/Organizatori/Master), bihevioralne metrike (auto/night/short_lat/
dup/lead/template/reg) + pun profil, Kampanje (burstevi + timeline), putanje
(+diskriminativne spone), denoising (klizač + sakrij izolovane), izvoz/uvoz.
Jedan `load_graph.py` gradi sve (graf + organizatori + skorovi + burstevi, ~3min).

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
