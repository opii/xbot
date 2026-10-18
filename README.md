# Cacix 🕵️‍♂️🤖

Cacix je sistem za **mrežnu i bihevioralnu analizu** koordinisane mreže naloga.
Radi nad realnom bazom jedne organizacije koja svojim članovima dodeljuje zadatke
na društvenim mrežama (lajk/retvit/odgovor/citat na tvit, komentarisanje vesti) i
beleži ko je šta uradio.

Umesto da pogađa "da li je nalog bot", Cacix **mapira postojeću koordinaciju** i
meri ponašanje: ko sa kim deli iste mete, ko su organizatori (centralni čvorovi) i
kako izgleda vremenski obrazac aktivnosti (ljudski rad u smenama vs automatizacija).

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

## 🚀 Instalacija i pokretanje

### 1. Baze (Docker)
```bash
cd bot_detector
docker compose up -d        # Postgres :5432, Neo4j :7474/:7687 (perzistentni volumeni)
```

### 2. Python okruženje
```bash
cd bot_detector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # pandas, networkx, fastapi, uvicorn, psycopg2-binary, neo4j
```

### 3. Uvoz baze (jednom)
Ako je `progress` šema prazna, uvezi SQLite u Postgres:
```bash
./venv/bin/python src/import_progress_db.py
```
Idempotentno je (preskače već uvezene tabele; `--force` za ponovni uvoz).

### 4. Gradnja grafa + detekcija organizatora
```bash
./venv/bin/python src/graph/load_graph.py
```
Gradi Neo4j graf (oba sloja) + izvedene tabele (`target_popularity`,
`news_popularity`) i na kraju računa organizatore/zajednice.
Alternativa (kontejnerizovano): `docker compose --profile init up graph_loader --build`.

### 5. Backend (FastAPI)
```bash
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir src
```

### 6. Frontend (React/Vite)
```bash
cd dashboard-ui
npm install
npm run dev
```
👉 Otvori **http://localhost:5173**

---

## 🖥️ Explorer — kako se koristi

Interfejs je **levi meni** (Sloj / Pogled / Bihevioralna analiza / Kampanje /
Filteri / Alatke):

- **Sloj:** *Tviter / Komentari* menja mrežu, bojenje i razlistavanje.
- **Pogled:** Pregled (povezanost) · **Uloge** (Pojačivač/Odgovarač/Mešovit) ·
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
| `/api/behavior_top?metric=&layer=` | rang po metrici: `auto`/`night`/`short_lat`/`dup`/`lead`/`template`/`reg`/`farm`/`pseudonyms`/`toxicity` (+ veze) |
| `/api/behavior_cohort` | decili metrika kroz sve operatere |
| `/api/bursts?limit=&min_ops=` | najsinhronizovanije kampanje (mete) |
| `/api/burst/{tid}` | vremenska linija kampanje po minutu + lideri + operateri |
| `/api/organizers?layer=&only_centroids=` | organizatori/centroidi |
| `/api/crosslayer` | master koordinatori (oba sloja) |
| `/api/path?a=&b=&layer=&max_pop=` | najkraća putanja + spone |
| `/api/target/{handle}`, `/api/account/{id}` | reverzno razlistavanje |
| `/api/regions`, `/api/search?q=`, `/api/stats` | šifarnici, pretraga, brojači |
| `/api/export/operator/{id}` | ceo klaster (JSON) |

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
├── src/
│   ├── import_progress_db.py    # SQLite → Postgres (šema progress)
│   ├── api/main.py              # FastAPI
│   ├── graph/
│   │   ├── load_graph.py        # Postgres → Neo4j + izvedene tabele + poziva donja dva
│   │   ├── detect_organizers.py # zajednice + centralnost (networkx)
│   │   └── behavior_scores.py   # automatizacija, lead-lag, šabloni, uloge, ritam + burstevi
│   └── modules/                 # (legacy) stari PoC moduli nad mock CSV-om
└── dashboard-ui/                # React + Vite explorer
```

> ℹ️ Moduli u `src/modules/` (`temporal_analysis`, `nlp_analysis`,
> `network_analysis`, `ensemble_model`) su iz ranijeg PoC-a nad sintetičkim CSV
> podacima i nisu deo aktuelnog toka.

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
