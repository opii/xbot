# Cacix Bot Hunter 🕵️‍♂️🤖

Cacix Bot Hunter je sistem za **bihevioralnu i mrežnu analizu (Data Science)** dizajniran za otkrivanje bot farmi, astroturfing kampanja i koordinisanog neautentičnog ponašanja na X-u (Twitter), a da pritom uopšte ne koristi IP adrese korisnika.

Sistem se oslanja isključivo na metapodatke (vreme, tekst, relacije) kako bi izolovao bot mreže koje platforma pokušava da sakrije.

---

## ⚠️ Napomena za "Real-World" upotrebu (I zašto je to trenutno bezveze)

U idealnom svetu, ovaj sistem bi bio direktno povezan na Twitter Stream i hvatao botove uživo. Međutim, **stvarnost je trenutno prilično obeshrabrujuća**. 

Nakon Maskovog preuzimanja i promene politike API-ja (prelazak na *Pay-per-use Credit Model* gde se svako čitanje tvita naplaćuje), slobodno skrejpovanje ili jeftino korišćenje X API-ja je u potpunosti mrtvo. Da biste ovaj sistem koristili na realnim podacima u praksi, bio bi vam potreban **papreno skup Enterprise X API nalog** (koji košta hiljade, pa i desetine hiljada dolara mesečno zavisno od obima). Skrejpovanje "na divlje" bez API-ja (poput Nitter-a) je takođe blokirano.

Zbog ove prilično bezvezne situacije sa monopolizacijom javnih podataka, ovaj projekat funkcioniše kao **Proof of Concept (PoC)**. Opremljen je generatorom koji sintetiše ultra-realistične scenarije (hiljade tvitova, stotine botova, astroturfing kampanje i NLP spam) kako biste mogli da testirate i vizuelizujete detekciju na delu.

---

## 🧠 Arhitektura Sistema (Ensemble Model)

Sistem računa jedinstveni **Bot Skor (0-100%)** kombinujući rezultate tri nezavisna modula:

1. **Modul za Vremensku Analizu (Temporal Analysis):** Koristi Pandas i tehniku "klizećeg prozora" (Rolling window) da pronađe "rafale" retvitova unutar par sekundi (ili milisekundi).
2. **Modul za Mrežni Graf (Network Analysis):** Koristi `NetworkX` za detekciju tzv. *Star Graph* topologije (Astroturfing). Prati ko retvituje koga i flaguje izolovane klastere koji veštački "pumpaju" jednog političara ili influensera.
3. **Modul za Analizu Teksta (NLP):** Koristi *TF-IDF* i kosinusnu sličnost (Cosine Similarity) za prepoznavanje farmi koje tvituju identičan tekst (sa minimalnim varijacijama kako bi izbegle ban).

---

## 🛠️ Tehnološki Stack
* **Jezik:** Python (Data Science i API) & JavaScript (Frontend)
* **Baze:** **PostgreSQL** (za metapodatke i skorove) i **Neo4j** (Graph baza za iscrtavanje bot mreža).
* **Backend API:** FastAPI
* **Frontend:** React + Vite (sa custom Glassmorphism UI)

---

## 🚀 Instalacija i Pokretanje

### 1. Pokretanje Baza Podataka
Projekat koristi Docker za baze podataka. U root folderu pokrenite:
```bash
docker compose up -d
```
*(Ovo će podići Postgres na portu `5432` i Neo4j na portovima `7687`/`7474`)*

### 2. Podešavanje Python Okruženja
```bash
cd bot_detector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt # (pandas, scikit-learn, networkx, fastapi, psycopg2-binary, neo4j)
```

### 3. Generisanje Podataka i Pokretanje Modela
Unutar `src/modules` pokrenite simulaciju i model:
```bash
cd bot_detector/src/modules
# 1. Generiše gigantski realistični dataset (Astroturfing, Kripto Spam, Pravi ljudi)
python simulate_real_world.py 
# 2. Pušta podatke kroz 3 modula i čuva rezultate u Postgres i Neo4j
python ensemble_model.py 
```

### 4. Pokretanje Dashboard-a
**Backend (FastAPI):**
```bash
cd bot_detector
python src/api/main.py
```
**Frontend (React/Vite):**
```bash
cd bot_detector/dashboard-ui
npm install
npm run dev
```
👉 Posetite **http://localhost:5173** da vidite grafički interfejs!

---
*Projekat razvijen u svrhu istraživanja ponašanja bot mreža i analize grafova.*
