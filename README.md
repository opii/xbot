# Cacix 🕵️‍♂️🤖

Cacix je sistem za **mrežnu i bihevioralnu analizu** koordinisane mreže naloga.
Radi nad realnom bazom jedne organizacije koja svojim članovima dodeljuje zadatke
na društvenim mrežama (lajk/retvit/odgovor/citat na tvit, komentarisanje vesti) i
beleži ko je šta uradio.

Umesto da pogađa "da li je nalog bot", Cacix **mapira postojeću koordinaciju** i
meri ponašanje: ko sa kim deli iste mete, ko su organizatori (centralni čvorovi) i
kako izgleda vremenski obrazac aktivnosti (ljudski rad u smenama vs automatizacija).

📄 **Master OSINT Whitepaper (sveobuhvatna sinteza, publikabilno):**
[`docs/CACIX_MASTER_OSINT_WHITEPAPER.md`](docs/CACIX_MASTER_OSINT_WHITEPAPER.md)
📄 **Detaljna dokumentacija (grafovi + bihevioralna analiza):**
<https://claude.ai/code/artifact/f44e1f1b-8ec4-4b85-bb11-19f820042143>
🤖 Orijentir za AI agente: [`AGENTS.md`](AGENTS.md)

---

## 🔑 Ključni nalazi

Za razliku od spoljne OSINT analize koja *nagađa* ko je bot, ovde postoji
**unutrašnji ground-truth** (ko, kome, sa koje mašine, po kojoj direktivi, za
koliko poena). Podaci pokazuju:

- **Ljudi u javnom sektoru, ne AI botovi:** 311 operatera radi pon–pet 08–16h;
  131 ima 100% aktivnosti u radno vreme (0% vikend/noć).
- **Fizička farma mašina:** 191.390 akcija preko servera KANCELARIJASBB /
  INDJIJA1 / INDJIJA2 (~1.938 operatera).
- **Industrija lažnih identiteta:** jedan operater pod hiljadama pseudonima
  (#7418 → 2.378 imena na 17k komentara); do 96% duplikata, 100% šablonskog teksta.
- **Vojnička sinhronija:** u 12% kampanja >85% operatera reaguje u prvih 10 min;
  lideri u razmaku od sekundi.
- **Jurišni odredi:** 520 operatera specijalizovano za napade — opozicija i
  kritički mediji dobijaju isključivo napadačke odgovore (#2656 = 3.882 napada),
  dok stranačke mete dobijaju hvalospeve (quote/like).
- **Tretman portala:** 302 „Infiltratora" zasipaju kritičke medije (0,9%
  prolaznosti, 99% blokade) — #6206 poslao 31.653 komentara, prošao 1 — dok
  tabloidi puštaju ~32%.
- **Strana voter infrastruktura:** automatsko glasanje (550M klikova) ide iz
  inostranstva — 63% zapisa van Srbije; najjači ASN je Telekom/MTS, ali odmah iza
  slede afrički provajderi (CAMNET Kamerun 472 IP, MTN, Orange, Congo Telecom…).
  Afrika je **66% distinct IP** (Kamerun #1, ispred Srbije). Offline GeoIP:
  [`src/analysis/voter_geoip.py`](bot_detector/src/analysis/voter_geoip.py); u
  exploreru: pogled **„🌍 Voter / GeoIP (Afrika)"**.
- **Kladionice = voter terminali:** voter mašine su terminali u uplatnim mestima
  kladionica (Scooorebet/Maxi/Joker) u Srbiji i Africi; opštine sa terminalima
  imaju i jake operaterske klastere ([`docs/analiza_komanda_i_voter.md`](docs/analiza_komanda_i_voter.md)).
- **Komanda:** 135 ljudi kreira sve portal-zadatke (21 koordinator); 61 ima
  eksplicitne VOTER privilegije. **Fer play:** podaci NE vezuju osobu za konkretnu
  (afričku) mašinu — atribucija je prava+uloge+ko-lokacija, ne pravna presuda
  ([`docs/komandna_odgovornost_i_pravni_osnov.md`](docs/komandna_odgovornost_i_pravni_osnov.md)).
- **Direktive:** 99% smernica je čista akcija; ton napada je u IZBORU METE, ne u
  tekstu (587 eksplicitnih napad-odgovora na opoziciju vs 113.991 pod generičkim
  „odgovaramo"). Najtešnja sinhronija = pro-režim amplifikacija. Postoji centralni
  izvor „super specijal / Šefov video iz četa" (30 izdavača), odvojen od izvršnih
  centroida ([`docs/analiza_direktiva.md`](docs/analiza_direktiva.md)).
- **Koordinatori — komanda ≠ izvršenje:** komanda je geografska (Region→Okrug→Opština,
  156 koordinatora + 22 zamenika), ali **nijedan od 156 koordinatora nije grafni
  centroid** (od 16 habova nijedan nema titulu). Formalna komanda i mrežna izvršna
  moć su razdvojeni slojevi ([`docs/analiza_koordinatora.md`](docs/analiza_koordinatora.md)).
- **Kaskada (SS → teren):** centralne direktive propagiraju **17,6% brže** (582s vs
  707s do prve reakcije); „vrh koplja" (prvi reagent) su Novi Sad, Beograd, Zrenjanin;
  SS se izvršava **prekoregionalno** (centralni kanal) ([`docs/analiza_kaskade.md`](docs/analiza_kaskade.md)).
- **Cirkadijalni režim:** glasanje ima jasan noćni pad (00–08h = 7,7%) — **nije ravan
  24/7 daemon**; srpske mašine „se bude" u 9h (otvaranje lokala), strane raspoređenije
  sa noćnim repom (`src/analysis/voter_timing.py`, satnica u „🌍 Voter / GeoIP").
- **Korporativni tragovi kladionica:** 182 mašine sa brendom (Maxi/Scooorebet/Joker)
  — vlasništvo NIJE u bazi, zahteva APR/Upravu za igre na sreću; brend ≠ dokaz
  ([`docs/vlasnicki_profil_kladionica.md`](docs/vlasnicki_profil_kladionica.md)).
- **📑 Istraživački dosije:** jedan klik u „Alatke" generiše ceo formalni izveštaj
  (Markdown) sa fer-play granicama (`/api/export/investigation_dossier`).
- **Dnevnik dežurstava:** interni chat (20.232 poruke) pokazuje smene (predaja oko
  12/15/19h), kontrolu kvaliteta i krizna brisanja; vodeći supervizor je i #2
  „udarnik" ([`docs/dnevnik_smena_i_kontrola.md`](docs/dnevnik_smena_i_kontrola.md)).
- **Partijska ekonomija:** quote 4,59 > reply 3,19 > lajk 1,49 bodova — ekonomija
  nagrađuje napad; **7 od 10 top „udarnika" su jurišnici**
  ([`docs/gamifikacija_i_kvote.md`](docs/gamifikacija_i_kvote.md)).
- **Širina operacije (8 slojeva):** prekogranično (CG 11,5M + BiH 6,1M glasova, proxy
  mreža za vijesti.me), relay nalozi na afričkim mašinama, headless JS/XPath injekcija,
  taktičke divizije (TikTok/Voter/Hit-Tvit/Nadzor), nadzor operatera (F12 telemetrija,
  29.682 uređaja, SMS 2FA gateway) i **51.703 naloga na 6 platformi** (7.178 op na 3+).
  Vidi `docs/regionalne_operacije_cg_bih.md`, `voter_mehanizam_kurir_custom.md`,
  `takticke_grupe_i_divizije.md`, `nadzor_operatera.md`, `multiplatform_arsenal.md`.
  **Sve uz stroga pravila:** kredencijali/telefoni se nikad ne izlažu; FK=dokaz,
  vremensko poklapanje=korelacija.

## 🌍 Voter infrastruktura — GeoIP nalazi

Automatsko glasanje (plus/minus na komentare, ~550M klikova; tabela
`voter_racunari`, 1.668 zapisa / 1.087 distinct IP) radi uglavnom iz
**inostranstva**: **63% zapisa i 80% distinct IP-jeva je van Srbije**. GeoIP je
rađen **offline** (iptoasn, IP-jevi se ne šalju nikuda) — skripta
[`src/analysis/voter_geoip.py`](bot_detector/src/analysis/voter_geoip.py).

**Top države (po zapisima / distinct IP):**

| Država | Zapisa | IP |
| --- | --- | --- |
| 🇷🇸 Srbija | 619 | 216 |
| 🇨🇲 Kamerun | 503 | **472** |
| 🇨🇬 Kongo | 162 | 155 |
| 🇹🇿 Tanzanija | 93 | 49 |
| 🇨🇮 Obala Slonovače | 68 | 35 |
| 🇧🇦 BiH | 60 | 51 |
| 🇲🇪 Crna Gora | 59 | 50 |
| 🇮🇹 Italija | 42 | 1 |
| 🇵🇪 Peru | 14 | 13 |
| 🇨🇾 Kipar | 14 | 13 |
| 🇺🇸 SAD | 9 | 9 |
| 🇲🇹 Malta | 8 | 7 |

**Top ASN / provajderi:**

| # | ASN · provajder | Zapisa |
| --- | --- | --- |
| 1 | AS8400 TELEKOM-AS (MTS, 🇷🇸) | 251 |
| 2 | AS15964 CAMNET (🇨🇲 Kamerun) | 195 |
| 3 | AS30992 MTN Cameroon | 172 |
| 4 | AS9125 Orion Telekom (🇷🇸) | 140 |
| 5 | AS36912 Orange Cameroon | 124 |
| 6 | AS198370 JG-ASN (🇷🇸) | 107 |
| 7 | AS37451 Congo Telecom | 93 |
| 8 | AS36924 GVA-Canalbox (🇨🇮) | 68 |
| 9 | AS328436 Flashnet (🇹🇿) | 68 |
| 10 | AS31042 SBB — Serbia BroadBand (🇷🇸) | 54 |
| 11 | AS25144 Telekom Srpske (🇧🇦) | 53 |

**Zaključak:** voter mašinerija kombinuje domaće ISP-jeve (Telekom/MTS, Orion, SBB)
sa **zakupljenim stranim proksijima**, pre svega **afričkim mobilnim/ISP opsezima**
(Kamerun masovno — 472 IP, Kongo, Tanzanija, Obala Slonovače) — klasična proxy
taktika za zaobilaženje geo-detekcije i moderacije srpskih portala.

## 🧭 Pristup: operater-centričan

Čvor nije pojedinačni nalog nego **operater** (osoba-`korisnik` koja upravlja
nalozima). Razlog:

- akcije su u bazi pripisane operateru, ne nalogu;
- ~97% registrovanih naloga je obrisano.

Zato je operater stabilna, pouzdana jedinica, a sama mreža predstavlja
*ground-truth* oznake koordinacije — ne pretpostavljene botove.

---

## 🧠 Šta sistem radi

| Analiza | Opis |
| --- | --- |
| **Dva sloja koordinacije** | `CO_ACTED` (zajedničko delovanje na iste tvitove) i `CO_COMMENTED` (komentarisanje istih vesti po portalima) |
| **Diskriminativne veze** | veze se grade preko *retkih* deljenih meta; masovne mete koje gura cela mreža (npr. `@sns_srbija`) se izostavljaju |
| **Detekcija organizatora** | odsecanje težina p5–p95, Louvain zajednice, PageRank + betweenness → centroid po zajednici |
| **Master koordinatori** | operateri jaki u OBA sloja: `master = √(tw_org · cc_org)` |
| **Putanje** | najkraća veza između dva operatera + konkretne spone (mete/vesti) po skoku |
| **Bihevioralni profil** | ritam po satu, radni dani, latencija zadatak→akcija, miks akcija, dnevni timeline, duplikati komentara |
| **Skor automatizacije** | noćna aktivnost + ravnomernost (24/7) + kratke latencije (prigušeno po količini) |
| **Lead-lag + burstevi** | ko prvi reaguje na metu (`lead_score`) i nalet operatera u prvih 10 min po meti (kampanje) |
| **Mreža šablona teksta** | treći sloj `CO_TEMPLATE`: operateri koji dele isti konzervirani komentar |
| **Uloge** | Pojačivač / Odgovarač / Mešovit po dominantnom tipu akcije |
| **Regularnost ritma** | pravilnost razmaka između akcija (viši = bot-like) |

---

## 🗄️ Podaci

Izvor je `bot_detector/data/progress_baza_podataka.sqlite3` (~4,8 GB), uvezen 1:1
u PostgreSQL šemu `progress` (57 tabela, ~12 GB sa indeksima). Baza se **ne drži
u gitu** (`*.sqlite3` je u `.gitignore`).

Ključne tabele:

| Tabela | Sadržaj | Redova |
| --- | --- | --- |
| `arhiva_twitter_unos` | zadaci (link ciljnog tvita + uputstvo) | 532.098 |
| `arhiva_twitter_unos_korisnici_akcije` | akcije (0=lajk,1=retvit,2=odgovor,3=citat) | 11.792.266 |
| `arhiva_vesti_korisnici_komentari` | komentari na vestima po portalima | 16.328.946 |
| `korisnici` | operateri (ime, okrug/opština, pozicija) | 9.314 |
| `korisnici_twitter_nalozi` | nalozi pod kontrolom operatera | 24.801 |

---

## 🛠️ Tehnološki stack

- **Jezik:** Python (uvoz, graf, API) + JavaScript (frontend)
- **Baze:** PostgreSQL (`progress` šema) + Neo4j (operaterska mreža)
- **Backend:** FastAPI
- **Graf/analiza:** NetworkX (zajednice, centralnost)
- **Frontend:** React + Vite + `react-force-graph-2d`

---

## 🚀 Izgradnja od nule (samo kod + `progress_baza_podataka.sqlite3`)

Ovaj vodič pretpostavlja da imaš **isključivo ovaj repozitorijum i SQLite bazu**.
Sve ostalo (Postgres, Neo4j graf, analitički JSON-ovi, UI) se gradi lokalno.

> ⚡ **Prečica:** posle koraka 0–2 (baza, Docker, venv), koraci **3–5 se rade jednim
> pozivom**: [`bot_detector/rebuild.sh`](bot_detector/rebuild.sh) (`./rebuild.sh`;
> `--help` za opcije). Preostaju samo backend (6) i frontend (7).

### 0. Preduslovi
- **Docker** + **Docker Compose** (za Postgres i Neo4j).
- **Python 3.11+** (testirano 3.13) i **Node.js 18+** (testirano 22) + `npm`.
- **Baza `progress_baza_podataka.sqlite3`** (~4,8 GB). **NIJE u repo-u** (`.gitignore`) —
  postaviti je ručno u `bot_detector/data/`:
  ```bash
  cp /putanja/do/progress_baza_podataka.sqlite3 bot_detector/data/
  ```

### 1. Baze (Docker)
```bash
cd bot_detector
docker compose up -d        # Postgres :5432, Neo4j :7474 (HTTP) / :7687 (Bolt)
docker compose ps           # sačekaj da su "healthy" (Neo4j start_period ~30s)
```
Kredencijali (compose): Postgres `bot_user`/`bot_password`/`bot_detector_db`;
Neo4j `neo4j`/`bot_password` (browser login na http://localhost:7474). Volumeni su
perzistentni.

### 2. Python okruženje
```bash
cd bot_detector
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 3. Uvoz SQLite → Postgres (jednom, ~12 GB, ~10–20 min)
```bash
./venv/bin/python src/import_progress_db.py
```
Učita svih 57 tabela u šemu `progress`. **Idempotentno** (preskače uvezene; `--force`
za ponovni uvoz; `--sqlite PUTANJA` ako baza nije na podrazumevanoj lokaciji;
dekodira `\uXXXX` ćirilicu).

### 4. Gradnja grafa + skorovi (~3 min)
```bash
./venv/bin/python src/graph/load_graph.py
```
Gradi Neo4j graf (slojevi CO_ACTED / CO_COMMENTED / CO_TEMPLATE), izvedene Postgres
tabele i na kraju računa **organizatore, zajednice, bihevioralne skorove i burstove**.
Alternativa (kontejnerizovano): `docker compose --profile init up graph_loader --build`.

### 5. (Opciono) GeoIP + regeneracija analitičkih JSON-ova
Analitički izlazi (`data/geo/*.json`) **jesu u repo-u**, pa koraci 6–7 rade i bez ovoga.
Ovaj korak ih **osvežava sa tvoje baze** i potreban je samo za GeoIP (dataset nije u repo-u):
```bash
# GeoIP referentni dataset za voter_geoip.py (~7 MB) — NIJE u repo-u (.gitignore)
curl -L https://iptoasn.com/data/ip2asn-v4.tsv.gz -o data/geo/ip2asn-v4.tsv.gz

# (re)generiši sve analitičke JSON-ove (traži učitan Postgres + Neo4j iz koraka 3–4)
for m in voter_geoip betting_geo task_masters voter_timing command_responsibility \
         directives coordinators cascade betting_corporate shift_chat gamification_points \
         regional_operations voter_kurir_links voter_custom_actions tactical_groups \
         system_surveillance multiplatform; do
  ./venv/bin/python src/analysis/$m.py
done
```

### 6. Backend (FastAPI)
```bash
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir src
```
Provera: `curl -s localhost:8000/api/stats` treba da vrati JSON (HTTP 200).
Gašenje: po portu (NE `pkill -f uvicorn` — ubija i sopstvenu ljusku).

### 7. Frontend (React/Vite)
```bash
cd dashboard-ui
npm install
npm run dev
```
👉 Otvori **http://localhost:5173**. UI gađa API na `http://localhost:8000`
(konstanta `API` u [`src/GraphExplorer.jsx`](bot_detector/dashboard-ui/src/GraphExplorer.jsx)
— promeniti ako je backend drugde).

### Šta NIJE u repo-u (mora se obezbediti/generisati)
`*.sqlite3` (ti je daješ) · `data/geo/*.gz` (GeoIP, korak 5) · `venv/` (korak 2) ·
`dashboard-ui/node_modules/` i `dist/` (korak 7). Sve ostalo (uklj. analitičke
`data/geo/*.json`) je u repo-u.

### Env varijable (podrazumevano = gornji compose)
`PROGRESS_PG_DSN` ili `PG_HOST`/`PG_DB`/`PG_USER`/`PG_PASSWORD`;
`NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`. Podrazumevano gađaju `localhost` sa
compose kredencijalima — menjati samo ako baze nisu lokalne.

---

## 🖥️ Explorer — kako se koristi

Interfejs je **levi meni** (Sloj / Pogled / Bihevioralna analiza / Kampanje /
Filteri / Alatke):

- **Sloj:** *Tviter / Komentari* menja mrežu, bojenje i razlistavanje — `CO_ACTED`
  (dele iste tvitove-mete) nasuprot `CO_COMMENTED` (komentarišu iste vesti). Objašnjenje
  sa pragovima i tumačenjem: [`docs/slojevi_koordinacije.md`](docs/slojevi_koordinacije.md),
  dostupno i iz aplikacije preko „ⓘ šta je razlika?“ uz sam prekidač.
- **Pogled:** Pregled (povezanost) · **Geografija** (okruzi) · **Uloge** (Pojačivač/Odgovarač/Mešovit) ·
  **★ Organizatori** (zajednice, centroidi) · **⚑ Master** (oba sloja).
- **Bihevioralna analiza** (boji i rangira graf po): skor automatizacije · noćna
  aktivnost · kratke latencije · duplikati komentara · **Lider — prvi na meti** ·
  **Deljeni šabloni** · **Regularnost ritma**.
- **Kampanje:** **⚡ Burstevi** — najsinhronizovaniji udari; klik → vremenska linija
  po minutu + lideri (ofset u sekundama).
- **Filteri:** okrug / opština · period (mete/profil/izvoz) · tipovi čvorova ·
  **klizač „min jačina veze"**, **„sakrij izolovane"** i **„samo backbone
  (disparity)"** — Serrano multiscale filter koji ostavlja samo statistički
  značajne veze (čist graf, čuva male klastere).
- **Alatke:** pretraga · **Putanja** (klik na dva operatera, + diskriminativne
  spone) · Reset · izvoz JSON/CSV/klaster · učitaj.
- **📚 Dokumentacija:** čitač svih studija iz [`docs/`](docs/) direktno u aplikaciji
  (pretraga po naslovu/opisu, automatski sadržaj dokumenta, međusobni linkovi,
  preuzimanje `.md`, štampa). Otvara se i kao **zasebna stranica** na
  [`#/docs`](http://localhost:5173/#/docs) — zgodno za čitanje u drugom tabu ili
  slanje linka na konkretan dokument (`#/docs/docs/analiza_direktiva.md`).
- **Bihevioralni panel** (klik na operatera): skor automatizacije sa percentilom,
  komponente, ritam po satu, radni dani, histogram latencije, dnevni timeline,
  miks akcija i (za komentatore) duplikati + portali.

---

## 📡 API (ključni endpointi)

| Endpoint | Vraća |
| --- | --- |
| `/api/overview?layer=&okrug=&opstina=` | najpovezaniji operateri + veze |
| `/api/expand/{id}?layer=&frm=&to=` | susedi (nalozi/ko-akteri/mete ili ko-komentatori/portali) |
| `/api/operator/{id}` | detalji + top mete |
| `/api/behavior/{id}` | bihevioralni profil (ritam, radni dani, latencija, timeline, miks, duplikati) |
| `/api/behavior_top?metric=&layer=` | rang po metrici: `auto`/`night`/`short_lat`/`dup`/`lead`/`template`/`reg`/`farm`/`pseudonyms`/`toxicity`/`infiltrator` (+ veze) |
| `/api/behavior_cohort` | decili metrika kroz sve operatere |
| `/api/bursts?limit=&min_ops=` | najsinhronizovanije kampanje (mete) |
| `/api/burst/{tid}` | vremenska linija kampanje po minutu + lideri + operateri |
| `/api/organizers?layer=&only_centroids=` | organizatori/centroidi |
| `/api/crosslayer` | master koordinatori (oba sloja) |
| `/api/path?a=&b=&layer=&max_pop=` | najkraća putanja + spone |
| `/api/target/{handle}`, `/api/account/{id}` | reverzno razlistavanje |
| `/api/regions`, `/api/search?q=`, `/api/stats` | šifarnici, pretraga, brojači |
| `/api/export/operator/{id}` | ceo klaster (JSON) |
| `/api/docs`, `/api/docs/{id}` | indeks dokumentacije i sirov Markdown iz `docs/` |

Node id šema: `op:<id>`, `acc:<id>`, `tgt:<handle>`, `portal:<name>`, `news:<vid>`.
Polja operatera: `co_degree`/`cc_degree`, `tw_org`/`cc_org`, `tw_community`/`cc_community`,
`auto_score` (+ `night_ratio`, `hour_entropy`, `short_lat_frac`), `lead_score`,
`template_frac`, `reg_score`, `dup_ratio`, `role`. Slojevi veza: `CO_ACTED`,
`CO_COMMENTED`, `CO_TEMPLATE`.

---

## 📁 Struktura

```
bot_detector/
├── docker-compose.yml           # Postgres + Neo4j + graph_loader (profil "init")
├── rebuild.sh                   # uvoz + graf + geoip + analize jednim pozivom
├── requirements.txt
├── data/                        # progress_baza_podataka.sqlite3 (van gita) + data/geo/*.json
├── src/
│   ├── import_progress_db.py    # SQLite → Postgres (šema progress)
│   ├── api/main.py              # FastAPI (svi endpointi + dosije)
│   ├── graph/
│   │   ├── load_graph.py        # Postgres → Neo4j + izvedene tabele + poziva donja dva
│   │   ├── detect_organizers.py # zajednice + centralnost (networkx)
│   │   └── behavior_scores.py   # automatizacija, lead-lag, šabloni, uloge, ritam + burstevi
│   └── analysis/                # 17 modula (voter GeoIP, kaskada, direktive, grupe, nadzor…)
└── dashboard-ui/                # React + Vite explorer
```

---

## ⚖️ Ograničenja, etika i privatnost

- **Realni ljudi.** Čvorovi su stvarni operateri, ne anonimni botovi. Imena i
  lokacije pripadaju realnim osobama — koristiti odgovorno; za deljenje van tima
  pseudonimizovati u ID-jeve.
- **Ne "da li je bot".** Sistem meri koordinaciju i ponašanje; vremenski obrasci
  (rad u smenama) pokazuju organizovane ljude, ne nužno automatizaciju.
- **Osetljivi podaci.** Baza sadrži lozinke, telefone, OAuth tokene i sl. Oni se
  **ne koriste**; sistem ne gradi ništa što bi pristupalo tuđim nalozima.
- **Pragovi su izbor.** Gustina grafa, zajednice i centroidi zavise od pragova
  (`ceil/min`, `p5–p95`) — rezultate čitati uz te parametre.

---
*Projekat za istraživanje koordinisanog ponašanja mreža naloga i analizu grafova.*
