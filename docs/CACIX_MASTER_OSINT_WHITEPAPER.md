# CACIX — Master OSINT Whitepaper
## Anatomija koordinisane mreže za manipulaciju javnog mnjenja

**Verzija:** 1.0 · **Datum:** Oktobar 2026.
**Izvor podataka:** interni backend sistema („ground-truth") — SQLite baza
`progress` (`progress_baza_podataka.sqlite3`, ~4,8 GB, 57 tabela; javno dostupna za preuzimanje na [ocisti.net](https://ocisti.net/)) uvezena u PostgreSQL + Neo4j graf + offline GeoIP.
**Namena:** istraživačko novinarstvo, akademska zajednica, pravne/pravosudne institucije.
**Status:** radni analitički dokument. **Fer-play granice atribucije su sastavni deo
svakog nalaza** (vidi §8).

---

## 0. Napomena o metodu i etici

Za razliku od klasičnih OSINT studija astroturfinga (Stanford Internet Observatory,
Graphika, DFRLab), koje mrežu posmatraju **spolja** i *nagađaju* ko je bot, ovde se
analizira **unutrašnji ground-truth samog sistema**: baza beleži tačno ko je operater,
ko mu je dao zadatak, sa koje mašine je radio, koja je bila direktiva i koliko je
poena dobio. Cacix zato **ne nagađa — mapira i meri** stvarnu koordinaciju.

Svi brojevi u ovom dokumentu su **reproducibilni** iz baze. Dosledno se razdvaja:
- **DOKAZ** — eksplicitni primarni/strani ključevi u bazi;
- **KORELACIJA** — vremensko/geografsko poklapanje;
- **HIPOTEZA** — verodostojno tumačenje bez eksplicitne veze u podacima.

Osetljivi podaci (lozinke, telefoni, OAuth tokeni, 2FA kodovi) **se ne izlažu**.
Čvorovi su realni ljudi — imena se tretiraju odgovorno; za javno deljenje preporučuje
se pseudonimizacija u ID-jeve.

---

## 1. Izvršni rezime

Analiza otkriva **organizovanu mrežu ljudskih operatera** (ne AI botova) koja radi u
smenama, po geografskoj komandnoj strukturi, uz sistem bodovanja/kvota, i koja je
političke sajber-operacije sprovodila i preko **komercijalnih kladioničarskih
terminala u Srbiji i Africi** i preko **prekograničnih operacija** u Crnoj Gori i BiH.

**Ključne brojke:**

| Metrika | Vrednost |
|---|---:|
| Operatera (osoba) | 9.314 |
| Tviter akcija (lajk/rt/odgovor/citat) | 11,8M |
| Komentara na vestima (≈4,4M realnih) | 16,3M |
| Automatskih „voter" glasova | 550M+ |
| Voter mašina (terminali) | 1.668 |
| Naloga na 6 društvenih mreža | 51.703 |
| Internih operativnih chat-poruka | 20.232 |
| Dnevnih izveštaja o bodovima | 2,22M |

**Centralni zaključak:** ovo **nisu klasični automatizovani botovi** nego
**organizovani ljudi u smenama** — ali je koordinacija vrlo jaka, merljiva i
institucionalizovana (komanda, kvote, nadzor, kontrola kvaliteta, krizno brisanje).

---

## 2. Anatomija operatera: ljudi u smenama, ne AI

- **Ljudski obrazac, ne automatizacija.** Skor automatizacije (`auto_score`) dostiže
  najviše ~0,45 (nema ekstrema); medijana latencije zadatak→akcija je ~1h (ne sekunde);
  noćna aktivnost blizu nule. Vrh aktivnosti 9–16h, pad vikendom.
- **Rad u smenama / državna služba.** 311 operatera je „Kancelarijski" arhetip
  (pon–pet 08–16h), od toga **131 radi 100% u radno vreme sa 0% vikenda**. Uz to
  „noćna smena" i „vikend" arhetipi.
- **Hardverske farme i razvojni centar u Inđiji.** 1.938 operatera izvršava deo akcija
  preko namenskih serverskih mašina: **KANCELARIJASBB** (1.241 op), **INDJIJA2** (411),
  **INDJIJA1** (286); ukupno ~191.390 akcija. Prema podacima sa `ocisti.net` i korenskim
  admin nalozima u bazi (`k_id=1` `test.admin`, `k_id=3313` `test6.admin.dfs`), tvorac
  i glavni developer platforme još od 2012/2014. (program „Valter") vodi firmu
  **PHPDevs u Inđiji**, što direktno objašnjava naziv i lokaciju serverskih čvorova
  `INDJIJA1` i `INDJIJA2` (vidi [`docs/istorijat_i_arhitektura_platforme.md`](istorijat_i_arhitektura_platforme.md)).
- **Ekonomija bodova (gamifikacija).** Sistem plaća po akciji (Σbodovi/Σcount):
  **quote 4,59 · reply 3,19 · komentar-prijava 3,17 · deljenje 1,85 · retvit 1,59 ·
  lajk 1,49**. Citat vredi ~3× lajk → ekonomija **podstiče aktivan napad/odgovor**,
  ne pasivan lajk. Među top 10 „udarnika" po ukupnim bodovima, **7 su „Jurišnici"**
  (ekstremna toksičnost) — sistem nagrađuje agresiju.
- **Industrija lažnih identiteta.** U komentarima jedan operater piše pod stotinama/
  hiljadama pseudonima: op #7418 = 17.088 komentara pod **2.378** imena; #6206 =
  79.951 komentar pod **1.338** imena; duplikati do 96%, 100% šablonskog teksta.

---

## 3. Komandna struktura i centralni lanac

- **Geografska komanda:** Region (7) → Okrug (26) → Opština (162). Koordinatorske
  pozicije (namenske tabele): **5 region + 15 okrug + 136 opština = 156** (+22 zamenika).
- **Komanda ≠ izvršenje (DOKAZ):** od 156 koordinatora 139 se vidi u grafu, ali
  **0 su mrežni centroidi** (od 16 centroida nijedan nema formalnu titulu). Formalna
  titula i mrežna moć su **razdvojeni slojevi**.
- **Direktive:** 99% tviter smernica je čista akcija; ton napada je u **izboru mete**,
  ne u tekstu (587 eksplicitnih napad-odgovora na opoziciju vs 113.991 pod generičkim
  „odgovaramo"). Postoji **centralni izvor**: „super specijal (SS)" i „Šefov video iz
  četa".
- **SS kaskada (vremenski mehanizam):** centralne (SS) direktive propagiraju **~17,6%
  brže** (medijana prve reakcije 582s vs 707s). **„Vrh koplja"** (prvi reagent):
  **Južnobački okrug (Novi Sad), Beograd, Srednjobanatski (Zrenjanin)** — otvaraju
  kampanju; SS se izvršava **prekoregionalno** (centralni kanal).
- **Dnevnik dežurstava (`chat_twitter_brisanje`, 20.232 poruke):** primopredaja smena
  oko **12h/15h/19h**, aktivna kontrola kvaliteta („vratila sam što nije po pravilima")
  i **krizni nalozi za brisanje** razotkrivajućih tvitova. Vodeći supervizor
  **Mirko Osadkovski** (Tehnički sekretar za Južnobački okrug) — ujedno **#2 udarnik**
  po bodovima i „Jurišnik": komanda, kontrola i produktivnost u istoj osobi.

---

## 4. Fizička infrastruktura glasanja (kladionice u Srbiji i Africi)

- **1.668 voter mašina** (`voter_racunari`): 738 označeno kao Srbija, 930 kao strano.
  Imena mašina (`vr_naziv_ss`) nose **brendove/filijale kladionica**: domaća uplatna
  mesta (Borča, Požarevac Centar, Zrenjanin 3, Roma Novi Beograd 2, Krusevac Bronks 2)
  i afričke lokacije pod brendom **Scooorebet (59), Maxi (92), Joker (16), Casino** u
  Kongu (Brazavil, Nkayi, Dolisie) i Kamerunu (Bertoua, Nkongsamba).
- **Instaliran softver i 12-godišnja evolucija (DOKAZ + OSINT):** Voter je četvrta
  generacija istog programa za automatsko glasanje bez čoveka za tastaturom:
  **Valter (2014, desktop)** → **Tvrđava (2015)** → **Castle / VotR2 (2017–2019,
  mobilna aplikacija)** → **Progress.rs / Voter (2024–2026)**. U koloni `vr_verzija`
  zabeležene su **32 različite verzije** (`1.0.2.149`–`1.0.2.177`, uključujući specijalne
  `hardcode` bildove) u periodu od oktobra 2024. do **9. oktobra 2026.** — dokaz
  kontinuiranog razvoja i održavanja klijenta.
- **GeoIP otisak:** **66% distinct IP** van Srbije; **Kamerun #1 (472 IP)** — ispred
  Srbije (216). Vodeći domaći ASN je **AS8400 TELEKOM-AS (MTS, 251)** (državna
  infrastruktura na koju je sistem prebačen još 2016, a prema snimcima sa `ocisti.net`
  backend se hostuje na MTS-ovom **MCloud.rs**), dok su vodeći strani ASN-ovi CAMNET i
  MTN Kamerun, Orange Kamerun i Congo Telecom.
- **Relay nalozi (`voter_kurir_nalozi`):** od **28. oktobra 2024.** (`vreme_uzimanja`)
  kreće masovno vezivanje **1.514 naloga** (svi aktivni u bazi) preko jednokratnih
  (temp-mail) domena, dodeljenih (FK `racunar_id→vr_id`, DOKAZ) na **114 mašina
  (111 strano)** — infrastruktura za autorizaciju/upis, ne samo anonimno glasanje.
- **Headless injekcija (`voter_glasanje_custom`):** sistem šalje **sirovi JavaScript
  sa XPath selektorima** (`document.evaluate`, `scrollIntoView()`, `el.click()`,
  `FormData`) da emulira ljudski klik na tačno određenim URL-ovima (Kurir, RTCG, Avaz).
- **Tajming:** medijana komentar→glas **111s**, **217.044 glasa <10s** = mašinsko
  pojačavanje. Satnica glasanja ima jasan noćni pad (00–08h = 7,7%) → **nije ravan
  24/7 daemon**; srpske mašine se „bude" u 9h (otvaranje lokala).

---

## 5. Prekogranične hibridne operacije (Crna Gora i BiH)

- Baza (`drzava`) definiše 4 države (Srbija, Crna Gora, Hrvatska, BiH). Voter
  mašinerija nije gađala samo srpske portale:
  - **Crna Gora ~11,5M glasova:** in4s.net (6,66M), vijesti.me (2,85M), rtcg.me (803k),
    cdm.me (795k), pobjeda.me (410k).
  - **BiH ~6,1M glasova:** klix.ba (3,16M), avaz.ba (2,95M).
- **Namenska proxy mreža (DOKAZ):** `proxy_ip_adrese` — **133 proxy endpointa na samo 4
  distinct IP adrese, svih 133 konfigurisano isključivo za `vijesti.me`** (rotacija
  portova za zaobilaženje anti-bot zaštite baš tog portala).

---

## 6. Interna paranoja, nadzor i specijalne divizije

- **Tajni nadzor sopstvenih članova (`otvoren_inspector`):** sistem je slao
  telemetriju **čim operater otvori DevTools/F12 konzolu** — 306 zapisa, 85 operatera,
  svi u **uskom prozoru 21.–27.07.2023** (jedna nedelja). Najpraćeniji: Brankica Rašić
  (38×), Ivana Rajković (25×). Koncentracija u toj nedelji **korelira** sa internim
  događajima (npr. curenje spiska) — korelacija, ne dokaz uzroka.
- **Mobilna armija (`korisnici_uredjaji`, 29.682 uređaja):** Android 22.297, Windows
  4.732, iOS 2.273; praćenje preko trajnih **LocalStorage GUID-ova** i kolačića.
  **1.298 operatera koristi 5+ uređaja.** (Napomena: hipoteza o „farmi telefona" preko
  *deljenog* parametra NIJE potkrepljena — deljeni uređaj 3+ op = 0.)
- **Zvanični SMS gateway „Internet Tim":** 11.627 poruka (2023–2025), ~93% isporučeno —
  2FA verifikacioni kodovi za operatere (profesionalna infrastruktura). Telefoni/kodovi
  maskirani.
- **Taktičke divizije (`korisnici_grupe`, 30 grupa / 1.232 članstva):**
  - **TikTok divizija — abecedna podela:** „Dragana" (A–I, 121), „Nenad" (J–M, 132),
    „Danijela" (N–Z, 133) — ~386 ljudi samo za TikTok.
  - **Voter administracija**, **Nadzor i kontrola** (Kontrolori, Sekretari, protokol),
    i udarni **Hit Tvit** tim (4 operativca za koordinaciju tokom TV emisija).
- **Multi-platformski arsenal:** **51.703 naloga** (Twitter 24.801, Instagram 8.761,
  TikTok 7.957, Facebook 6.176, Threads 3.366, Reddit 642); **7.178 operatera pokriva
  3+ mreže.** 15 formalizovanih kategorija dežurstava (uklj. TELEGRAM, SAJTOVI,
  TWITTER PRINT SCREEN, VOTER).

---

## 7. Pravna kvalifikacija (okvir, ne presuda)

> Nismo pravnici; ovo je okvir za nadležne institucije, uz činjenice iz baze.

- **Budimpeštanska konvencija o sajber kriminalu** — **čl. 5** (ometanje sistema:
  sistemsko zasipanje/manipulacija portala i mehanizama glasanja) i **čl. 6**
  (zloupotreba uređaja: neovlašćeni bot-klijent na komercijalnim terminalima,
  verzionisan softver 1.0.2.x).
- **Zloupotreba licence/koncesije za igre na sreću** — terminali licencirani za igre
  na sreću u Srbiji, Kamerunu i Kongu korišćeni za političke sajber-operacije (mogući
  osnov za oduzimanje koncesije; zahteva proveru u APR / Upravi za igre na sreću).
- **Realna izloženost** je po **domaćim zakonima** svake jurisdikcije (računarska
  krivična dela, izborno/medijsko pravo, propisi o igrama na sreću), ne po
  „međunarodnom krivičnom pravu" u užem smislu.

---

## 8. Granice atribucije (fer-play — obavezno čitati)

Ovo su **najvažnija ograničenja**; svaka tvrdnja van njih je izmišljena:

1. **Mašina ↔ osoba:** NE postoji spojni ključ između `voter_racunari` (mašine/IP,
   uklj. afričke) i `knv_voter_*` (glasovi kreditirani operaterima). Zato se **ne može
   dokazati** da konkretna osoba „pokreće afričke botove" — mehanizam „operater →
   daljinski terminal → glas" je **HIPOTEZA** saglasna s podacima (verzionisan klijent
   + strane IP + srpski kreditirani glasovi), ali ne i dokaz.
2. **Vlasništvo kladionica:** NIJE u bazi. Brend/lokacija su **tragovi** za proveru u
   **APR / Upravi za igre na sreću**, ne dokaz vlasništva. „Scooorebet" (Afrika) se **NE
   izjednačava** sa bilo kojim srpskim lancem bez primarnog izvora; ne imenovati
   pojedince kao vlasnike bez proverljive dokumentacije.
3. **„kurir" ≠ Kurir.rs:** relay nalozi su kurirski/relay nalozi; portal nije vezan u bazi.
4. **Nadzor (F12):** vremensko poklapanje sa julom 2023 je **korelacija**, ne uzrok.
5. **Farma telefona:** preko *deljenog* parametra uređaja **nije potkrepljena**
   (deljeni 3+ op = 0); potvrđen je multi-device obrazac (1.298 op sa 5+ uređaja).
6. **Raspon kontrole koordinatora** = geografska nadležnost, **ne** dokaz pojedinačnog
   naređenja. **Kaskada** (redosled/latencija) = korelacija (inferirana propagacija).
7. **Partijski bodovi** = interna ekonomija koju sistem sam dodeljuje; ne izvode se
   zaključci van zabeleženog.
8. **Broj IP adresa ≠ broj uređaja.** Vodeći strani ASN-ovi su **mobilni operateri**
   (CAMNET 195, MTN Cameroon 172, Orange Cameroon 124 distinct IP). Mobilne mreže
   koriste CGNAT i **rotiraju adrese** — jedan uređaj kroz dan prolazi kroz više IP-ova
   iz pool-a, a istovremeno jedan IP može deliti mnogo korisnika. Zato „Kamerun 472 IP"
   znači **472 različite mrežne adrese**, a ne 472 terminala; broj IP-ova je mera
   mrežne rasutosti, ne broja mašina. Nalaz o stranoj infrastrukturi time ne slabi —
   rasutost kroz **tri operatera i četiri države** (CM 472, CG 155, TZ 49, CI 35) ostaje
   — ali se iz broja IP-ova **ne sme izvoditi broj uplatnih mesta ili uređaja**. Taj broj
   dolazi iz `voter_racunari` (1.668 mašina, 930 stranih), ne iz GeoIP-a.

---

## 9. Reprodukcija i detaljni moduli

Svi nalazi su reproducibilni nakon uvoza baze (`import_progress_db.py`), izgradnje
grafa (`load_graph.py`) i analitičkih skripti u `bot_detector/src/analysis/`.
Interaktivni pregled: FastAPI (`:8000`) + React explorer (`:5173`) sa pogledima
za svaki sloj; generator dosijea: `/api/export/investigation_dossier`.

Detaljni moduli:
`istorijat_i_arhitektura_platforme.md` · `analiza_direktiva.md` · `analiza_koordinatora.md` · `analiza_kaskade.md` ·
`dnevnik_smena_i_kontrola.md` · `gamifikacija_i_kvote.md` ·
`komandna_odgovornost_i_pravni_osnov.md` · `voter_kladionice_infrastruktura.md` ·
`vlasnicki_profil_kladionica.md` · `voter_mehanizam_kurir_custom.md` ·
`regionalne_operacije_cg_bih.md` · `takticke_grupe_i_divizije.md` ·
`nadzor_operatera.md` · `multiplatform_arsenal.md`.

*Cacix · interni ground-truth → mrežna i bihevioralna analiza. Brojke reproducibilne; granice atribucije poštovane.*
