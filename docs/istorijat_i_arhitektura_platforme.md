# Istorijat, evolucija softvera i arhitektura platforme Progress.rs (2012–2026)

**Projekat:** Cacix · **Datum:** Oktobar 2026.  
**Izvor:** Sinteza javno objavljenog konteksta sa platforme [ocisti.net](https://ocisti.net/) i forenzičke verifikacije nad internom SQLite bazom `progress_baza_podataka.sqlite3` (podaci zaključno sa **09.10.2026.**).

> ⚠ **Fer-play i metodološko razgraničenje:** U ovom dokumentu su jasno razdvojeni:
> 1. **DOKAZI IZ BAZE (`progress`)** — egzaktno proverljivi u tabelama (`korisnici`, `voter_racunari`, `voter_kurir_nalozi`, `otvoren_inspector`, `arhiva_twitter_unos_korisnici_akcije`);
> 2. **OSINT / INSAJDERSKI KONTEKST (`ocisti.net` / CINS / BIRN / RSE)** — istorijski razvoj softvera, snimci korisničkog interfejsa i podaci o autoru/hostingu objavljeni na `ocisti.net`. Lični brojevi telefona i lozinke se u skladu sa pravilima projekta Cacix **ne izlažu**.

---

## 1. Genealogija sistema: četiri generacije istog aparata (2012–2026)

Mašinerija koja danas nosi naziv **Progress.rs** nije nastala odjednom — razvija se kontinuirano od **2012. godine** kroz najmanje četiri generacije softvera, dok su organizaciona struktura i ključni ljudi ostajali isti:

| Godina | Generacija / Događaj | Tehnički mehanizam i operativni model | Trag / potvrda u bazi `progress` i OSINT izvorima |
| :--- | :--- | :--- | :--- |
| **2012** | **Prvi Internet tim** | Osnivanje internet tima (7 ljudi + rani skriptovani botovi); obuka preko rumunske marketinške agencije; upisivanje *Saveta za internet i društvene mreže* u Statut stranke. | Istorijski početak centralizovane partijske internet infrastrukture. |
| **2014** | **„Valter" (Walter)** | Prvi namenski desktop program koji je **sam ocenjivao komentare** (plus/minus) na portalima (B92, Blic, Kurir). Instalirao se na **kućne računare aktivista**. | 9. oktobra 2014. *Teleprompter* objavljuje program i uputstva; programeri mu prepravljaju kod i prave „obrnutog bota" (>6.000 pluseva na kritički komentar). |
| **2015** | **„Tvrđava" (Fortress)** | Nasleđuje kompromitovanog Valtera; prelazi na **centralizovani/web model** tako da više ne mora da se instalira na kućne računare svih aktivista. | Aprila 2015. otkrivena u medijima, nakon čega slede hakerski napadi na sajt koji je objavio priču. |
| **2016** | **Državna telekom infrastruktura** | Mreža prelazi na sopstveni blok od **8 statičkih IP adresa** na adresi centrale u Novom Beogradu preko **Telekoma Srbija**. | **Potvrda u Cacix GeoIP analizi:** `AS8400 TELEKOM-AS (MTS)` je i u 2026. godini ubedljivo #1 domaći ASN za voter mašine (251 zapis). |
| **2017–2020** | **„Castle" (#CASTLELEAKS)** | Treća generacija: web-panel + mobilna aplikacija, **formalna dežurstva**, dnevni izveštaji o učinku, bodovanje, integracija sa Telegramom, pravilo *„NE KOPIRAJTE SMERNICE"*. Preko **1.500 operatera dnevno** radi iz javnih preduzeća, opština i škola u radno vreme. | Januara 2019. istraživači ulaze u sistem; aprila 2020. Twitter briše **8.558 naloga** (Meta >5.000 FB i 100 IG); maja 2020. `@XudRobin` i BIRN objavljuju **#CASTLELEAKS** (prijave/odjave i za 10-minutni odlazak do prodavnice). |
| **2019** | **„VotR2" (mobilni voter)** | Septembra 2019. CINS otkriva Android aplikaciju **VotR2** koja sama glasa na **Kuriru, Espresu i Južnim vestima**: na svakih **6 sekundi**, do 5 puta na isti komentar, uz automatsko pokretanje pri restartu telefona (>1M glasova na Južnim vestima). | Direktan tehnički prethodnik današnjeg `Voter` klijenta i headless skripti. |
| **2022–2023** | **Spisak 14.000 naloga i interna istraga** | Avgusta 2022. analiza 100.000 naloga; u **julu 2023.** na Twitteru curi spisak sa **>3.000 imena i >14.000 naloga** (RSE analiza: 58 ljudi iz 20 okruga deli istu sliku za 2 sata). Poslanik Milimir Vujadinović u Skupštini potvrđuje autentičnost (*„Jesmo! Nastavićemo to da radimo"*). | **DOKAZ U BAZI (`otvoren_inspector`):** Upravo u nedelji **21.–27. jula 2023.** u bazi je zabeležen **jedini talas DevTools/F12 nadzora** (306 zapisa na 85 naloga) — interna bezbednosna provera operatera neposredno nakon curenja spiska! |
| **2024–2026** | **„Progress.rs" + novi „Voter"** | Četvrta generacija: **5 glavnih modula** (*Vesti, Komentari za 15 portala, Twitter, Reddit, Voter*), **15 dežurstava**, **162 opštine / 26 okruga / 7 regiona**, i distribuirana mreža od **1.668 voter terminala** u kladionicama u Srbiji i Africi. | **DOKAZ U BAZI:** 9.314 operatera, 51.703 naloga na 6 mreža, 11,8M Twitter akcija, 16,3M komentara, 550M+ voter glasova; poslednji zapis **09.10.2026.** |

---

## 2. Kako radi „Voter" i zašto je centralni stub manipulacije

Na sajtu `ocisti.net` sažeta je suština voter mehanizma koja se u potpunosti poklapa sa našim empirijskim nalazima:

> *„Ispod svake vesti na internetu ljudi ostavljaju komentare i glasaju za tuđe komentare. Komentar sa najviše pluseva ide na vrh, pa ga svi pročitaju prvi. Napravljen je program koji to radi umesto ljudi — sam deli pluseve komentarima koji hvale vlast, a minuse onima koji je kritikuju, sa hiljada računara u isto vreme... **Cilj cele platforme nije da te ubedi. Cilj je da te ućuti.**"*

### Ključni tehnički nalazi o Voter softveru (verifikovano u SQLite bazi):
1. **Potpuna automatizacija bez čoveka za tastaturom:** Za razliku od Twitter i komentatorskog sloja gde ljudski operateri rade u smenama, Voter je **čisto mašinski sloj** — program sam otvara komentar, klikće plus ili minus (ili izvršava XPath/`scrollIntoView`/`click` JS injekciju iz `voter_glasanje_custom`) i prelazi na sledeći.
2. **Kontinuirani razvoj — 32 verzije u dve godine (`voter_racunari.vr_verzija`):**
   - U tabeli `voter_racunari` (1.668 računara, od čega 930 sa `vr_srbija=0`) zabeležene su tačno **32 različite oznake verzija** u rasponu od `1.0.2.149` do `1.0.2.177` (plus status `offline`), sa paralelnim granama:
     - standardne verzije (`1.0.2.149` … `1.0.2.177`), i
     - specijalni **`hardcode` bildovi** (`1.0.2.163 hardcode`, `1.0.2.164 hardcode`, `1.0.2.168 hardcode` … `1.0.2.176 hardcode`).
   - Vremenski raspon check-inova u `voter_racunari` ide sve do **09.10.2026. u 07:44:55**, što potvrđuje da razvojni tim neprekidno ažurira klijenta kako bi zaobilazio izmene na portalima.
3. **Masovna aktivacija Kurir/relay naloga od 28. oktobra 2024. (`voter_kurir_nalozi`):**
   - U tabeli `voter_kurir_nalozi` nalazi se tačno **1.514 naloga** (svi `aktivan=1`), kreiranih preko temp-mail domena (`undeep.xyz`, `smallntm.lol`, `dunkos.xyz`...) i vezanih stranim ključem (`racunar_id → vr_id`) na 114 mašina (111 u inostranstvu/Africi).
   - Kolona `vreme_uzimanja` beleži početak masovnog preuzimanja/aktivacije naloga **28.10.2024. u 09:14:01**.

---

## 3. Tvorac softvera, izvorni kod (`PHPDevs` Inđija) i veza sa serverskim farmama `INDJIJA1` / `INDJIJA2`

Jedno od najznačajnijih unakrsnih otkrića nastaje spajanjem podataka sa `ocisti.net` i bihevioralne analize iz projekta **Cacix**:

1. **Razvoj i koreni admin nalozi:**
   - Prema dokumentaciji i izvornom kodu objavljenom na `ocisti.net` (`#o-tvorcu`, `#izvorni-kod`, `app.js`), tvorac i glavni programer sistema još od programa „Valter" (2012/2014) do današnjeg `Progress.rs` je **Nenad Gledović** (nadimci *„NG 2014"*, *„Gleda"*, *„GledaPro"*), vlasnik programerske firme **PHPDevs** iz **Inđije**.
   - U samoj bazi `progress` (`korisnici`), na samom vrhu tabele nalaze se koreni administratorski/test nalozi:
     - **`k_id = 1`**: `k_nalog = 'test.admin'` (`k_ime = 'TEST'`, `k_prezime = 'ADMIN'`, `k_pozicija = 'ADMIN'`)
     - **`k_id = 3313`**: `k_nalog = 'test6.admin.dfs'`
   - Sama web-platforma `Progress.rs` napisana je u **PHP-u** (kompletan izvorni kod aplikacije `progress-izvorni-kod.tar.gz`, ~150 MB, objavljen je na `ocisti.net/#izvorni-kod`).

2. **Rešena misterija serverskih mašina `INDJIJA1` i `INDJIJA2` (DOKAZ + KORELACIJA):**
   - U našoj bihevioralnoj analizi (`src/graph/behavior_scores.py`), analizom kolone `tuka_program_racunar` u tabeli `arhiva_twitter_unos_korisnici_akcije` nezavisno smo otkrili da **1.938 operatera** izvršava deo svojih Twitter akcija (ukupno **191.390 akcija**) preko tri centralne serverske mašine:
     - **`KANCELARIJASBB`** (1.241 operater)
     - **`INDJIJA2`** (411 operatera)
     - **`INDJIJA1`** (286 operatera)
   - Činjenica da se razvojna firma koja održava platformu (**PHPDevs**) nalazi upravo u **Inđiji** direktno objašnjava zašto dve od tri centralne serverske farme u bazi nose imena **`INDJIJA1`** i **`INDJIJA2`**.

3. **Hosting na državnom MCloud-u (Telekom Srbija / MTS):**
   - Prema insajderskom snimku naplatnog panela objavljenom na `ocisti.net` (`MCLOUD-BILLING.png`), produkciona serverska infrastruktura hostovana je na **MCloud.rs** (cloud platforma Telekoma Srbija / MTS-a), uz prikazanu mesečnu naknadu od **178.660 EUR** (~180.000 EUR mesečno) i akumulirani neplaćeni saldo od **22.332.500 EUR** (>23M EUR).
   - *Fer-play napomena:* Podaci o MCloud fakturama potiču sa snimka ekrana objavljenog na `ocisti.net`, a ne iz tabela SQLite baze `progress`. Međutim, tehnička veza sa Telekomom Srbija (`AS8400 TELEKOM-AS`) je nezavisno potvrđena u samoj bazi kroz GeoIP analizu IP adresa.

---

## 4. Radni tok operatera u interfejsu platforme (`#pregled`)

Snimci ekrana produkcionog interfejsa platforme `Progress.rs` sa `ocisti.net` potvrđuju strukturu tabela koju vidimo u bazi. Nakon prijave na sistem, operater ulazi u **Dnevnik aktivnosti** koji ima 6 celina:

1. **Komentarisanje na vestima** — lista aktivnih vesti sa 15 portala koje treba komentarisati (`arhiva_vesti_unos` → `arhiva_vesti_korisnici_komentari`).
2. **Određeni zadaci na društvenim mrežama** — pojedinačni postovi sa smernicama za lajk/retvit/odgovor/citat (`arhiva_twitter_unos` → `arhiva_twitter_unos_korisnici_akcije`).
3. **Deljenje vesti** — zadaci za deljenje linkova vesti na sopstvenim profilima.
4. **Komentarisanje na svim mrežama** — koordinisani komentari na društvenim mrežama.
5. **Bodovanje i kontrola komentara** — poseban administratorski/koordinatorski panel u kome koordinatori ocenjuju kvalitet komentara i uvreda koje pišu operateri (`izvestaj_dnevni`, `chat_twitter_brisanje`); sakupljeni bodovi direktno utiču na isplatu/zaradu.
6. **Odgovori hejterima** — namenska sekcija za ciljane napade na kritičke naloge i opoziciju (što u našoj analizi direktno odgovara klasi **„Jurišnika"** — 520 operatera sa ekstremnim `toxicity_score`).

Uz to, platforma poseduje:
- **Geografsku statistiku uživo** — broj trenutno aktivnih botova po regionima i okruzima Srbije u realnom vremenu;
- **Lični karton operatera** — gde je svaki operater obavezan da unese lične podatke, broj telefona (za 2FA SMS) i poveže sve svoje lažne naloge na 6 društvenih mreža.

---

## 5. Forenzičke specifičnosti baze (`progress_baza_podataka.sqlite3`)

Iz analize koda i napomena na `ocisti.net` (`app.js`, `#baza-podataka`) potvrđene su i sledeće tehničke pojedinosti bitne za istraživače koji rade nad SQLite bazom:

- **Priroda javnog SQLite fajla (~4,8 GB):** Baza `progress_baza_podataka.sqlite3` sadrži kompletne relacione tabele i metapodatke svih akcija, dok je deo samih tekstova komentara koje su botovi pisali izostavljen/skraćen kako bi fajl bio manji za preuzimanje.
- **Otisak uređaja (`ku_uredjaj_parametar`):** U tabeli `korisnici_uredjaji` (29.682 zapisa), identifikator uređaja se generiše i čuva kao **otisak u `localStorage`-u** pretraživača/aplikacije (`ku_local_storage_gh` / `ku_uredjaj_parametar`).
- **Sentinel datum za Twitter blokadu (`k_twitter_blokada`):** Vrednost `2023-01-01 00:00:00` u koloni `k_twitter_blokada` nije stvarni datum blokade, već podrazumevana (default) vrednost u bazi koja označava da nalog **nije blokiran**.
- **Anomalija u SMS arhivi (`sms_poruke.sp_telefon`):** U delu zapisa tabele `sms_poruke`, u koloni `sp_telefon` je greškom aplikacije upisan sam verifikacijski (2FA) kod umesto broja telefona, pa je pri analizi brojeva potrebno filtrirati zapise po formatu telefonskog broja (`^381\d{8,9}$` ili `^0\d{8,9}$`).

