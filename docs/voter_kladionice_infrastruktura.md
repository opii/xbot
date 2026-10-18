# Razotkrivanje Voter Infrastrukture: Sprega Industrija Kladionica i Bot Mašinerije

**Datum:** Oktobar 2026.  
**Projekat:** Cacix (Mrežna i bihevioralna analiza koordinisane mreže)  
**Izvor podataka:** Baza `progress`, tabele `voter_racunari` (1.668 mašina, 1.087 IP) i `izvestaj_voter` (550+ miliona glasova).

---

## 1. Uvod i Sažetak Otkrića

Tokom analize mehanizma za automatsko glasanje na komentarima vesti (lupanje stotina miliona pluseva i minusa na portalima Blic, Kurir, Alo, Novosti, Klix, Vijesti), GeoIP i ASN analiza je otkrila da je **63% zapisa i 80% unikatnih IP adresa locirano van Srbije**, sa ogromnom koncentracijom u afričkim državama: **Kamerun (472 IP), Kongo (155 IP), Tanzanija (49 IP), Obala Slonovače (35 IP)**.

Postavilo se ključno istraživačko pitanje: *Da li iza ovih afričkih proksija stoje strane sile (npr. ruske ili kineske operacije uticaja) ili komercijalni botnet?*

Detaljnom analizom kolone `vr_naziv_ss` u tabeli `progress.voter_racunari`, razotkriven je stvarni izvor: **infrastruktura pripada domaćem lancu sportskih kladionica i slot klubova sa razvijenim franšiznim poslovanjem u Africi (brendovi *Scooorebet*, *Casino*, *Joker*, *Maxi*)**.

Računari u uplatnim mestima kladionica u Srbiji (od Borče, Požarevca i Zrenjanina do Kruševca i Novog Beograda), kao i terminali u njihovim uplatnim mestima u Africi (Kamerun, Kongo), imali su instaliran klijentski softver bota koji je u pozadini 24/7 generisao stotine miliona lažnih glasova za potrebe vladajuće stranke.

---

## 2. Empirijski Dokazi iz Baze Podataka

### 2.1. Značenje skraćenice `vr_naziv_ss`
U internoj terminologiji industrije igara na sreću i samog sistema, `ss` označava **Slot Salon / Sportsko Sedište / Uplatno mesto**. Svaki računar u tabeli `voter_racunari` nosi naziv konkretne poslovnice.

### 2.2. Uplatna mesta u Srbiji
U bazi su precizno navedena domaća uplatna mesta:
- `Borca Ivana Milutinovica` (Borča, Beograd)
- `Borca Centar` (Borča, Beograd)
- `Roma Novi Beograd 2` (Novi Beograd)
- `Enjub` (TC Enjub, Blok 45, Novi Beograd)
- `Pozarevac Centar` (Požarevac)
- `Zrenjanin 3` (Zrenjanin)
- `Krusevac Bronks 2` (Kruševac)
- `Sivac` (Kula / Zapadnobački okrug)

### 2.3. Uplatna mesta i gradovi u Africi
Paralelno sa srpskim gradovima, u istoj koloni se nalaze nazivi ulica, trgova, pijaca i gradova u Centralnoj Africi gde domaće kladionice vode franšize:
- **Kongo (Brazavil i unutrašnjost):**
  - `Rue Mbochis` (Glavna trgovačka ulica u centru Brazavila)
  - `Nkayi Marche Mabombo` (Grad Nkayi, centralna pijaca)
  - `Kisoundi` (Naselje u Brazavilu)
  - `Chateau Deau` (Naselje / vodotoranj u Brazavilu)
  - `Bouetabongo`, `Avenue Reine Ngalifourou`, `Ceinture Commission`
  - `Dolisie Baloumbou`, `Kinkala`, `Owando`, `Mpita` (Pointe-Noire)
- **Kamerun:**
  - `Bertoua Bodomo` (Grad Bertoua)
  - `Nkongsamba Marche` i `Nkonsamba 1` (Grad Nkongsamba)
  - `Abong Mbang Carrefour` (Grad Abong Mbang)

### 2.4. Zabeleženi brendovi kladionica
Među imenima mašina direktno se pojavljuju komercijalni nazivi uplatnih mesta:
- **`Scooorebet 13`** (Kladioničarski brend aktivan na afričkom tržištu)
- **`Casino`**
- **`Joker`**
- **`Maxi 36`**, **`Maxi 79`**, **`Maxi 80`**

### 2.5. Verzija klijentskog bot-softvera
Svi ovi računari imali su instaliran namenski klijent zabeležen u koloni `vr_verzija`:
- Verzije u rasponu od `1.0.2.149` do `1.0.2.163`.
- Aplikacija je radila tiho kao pozadinski servis (daemon) na terminalu uplatnog mesta.

---

## 3. Tehnički i Operativni Mehanizam

1. **Zašto baš uplatna mesta kladionica?**
   - **Postojeći hardver i nulti trošak:** Nije bilo potrebe za iznajmljivanjem servera ili kupovinom botnet servisa. Kladionice već poseduju hiljade računara sa stalnim napajanjem i fiksnom internet vezom.
   - **Izbegavanje IP blokada (Rate-Limiting evazija):** Domaći portali (Blic, Kurir, Novosti) poseduju mehanizme zaštite od spama. Ako 100.000 glasova dođe sa nekoliko IP adresa iz Beograda, alarm se pali i IP se blokira. Međutim, kada glasovi dolaze sa **472 različite IP adrese iz Kameruna** (provajderi Camnet, MTN, Orange) i **155 iz Konga**, zaštitni algoritmi portala ih vide kao nezavisne korisnike („čitaoci iz inostranstva”).

2. **Obim Voter Operacije (preko 550 miliona klikova):**
   Tabela `progress.izvestaj_voter` dokumentuje zapanjujući obim lažiranja javnog mnjenja:
   - **Blic.rs:** 185.014.665 glasova (12.809 vesti)
   - **Alo.rs:** 130.195.029 glasova (26.020 vesti)
   - **Kurir.rs:** 129.436.781 glas (16.960 vesti)
   - **Novosti.rs:** 50.844.377 glasova (13.764 vesti)
   - **Telegraf.rs:** 25.482.204 glasova
   - **B92.net:** 23.922.453 glasova
   - **Regionalne operacije:**
     - Klix.ba (BiH): 3.168.000 glasova
     - Avaz.ba (BiH): 2.959.655 glasova
     - Vijesti.me (Crna Gora): 2.856.817 glasova
     - In4s.net (Crna Gora): 6.660.198 glasova

---

## 4. Novi Istraživački Fokus: Povezivanje Grafa i Voter Infrastrukture

Ovo otkriće uspostavlja novu stratešku osu istraživanja u projektu Cacix. Više se ne posmatraju samo odvojeni operateri na Tviteru, već **veza između centara moći u mreži (centroida i koordinatora) i ove fizičke mašinerije**.

### Ključna istraživačka pitanja (Novi Glavni Cilj):
1. **Ko kontroliše zadatke za portale?**
   Povezati tabelu `progress.arhiva_vesti_unos` (kolone `vu_korisnik_id`, `vu_zatvorio_korisnik_id`) sa tabelama koordinatora (`progress.koordinatori_korisnici`, `progress.okrug_koordinator`, `progress.opstina_koordinator`).
2. **Korelacija centroida u grafu sa Voterom:**
   Da li su vodeći organizatori i centroidi zajednica u Neo4j grafu (`Operator` čvorovi sa visokim `tw_org` i `cc_org`) povezani sa opštinama gde se nalaze ključna uplatna mesta (npr. Požarevac, Novi Beograd, Kruševac, Zrenjanin)?
3. **Vremenska ko-sinhronija (Zadatak → Komentari → Voter udar):**
   Uskladiti vremenske linije: kada koordinator zada vest sa kvotom (npr. smernica *"500"* ili *"max"*), koliko sekundi kasnije uplatna mesta iz Kameruna i Borče kreću sa automatskim glasanjem, i koji operateri pod deljenim šablonima teksta (`CO_TEMPLATE`) unose prve komentare koje voter zatim pumpa u vrh?
