# Istraživački dosije — koordinisana astroturfing mreža (Cacix)

**Generisano:** 2026-10-18T14:59:55  
**Izvor:** interna baza `progress` (ground-truth sistema), Neo4j graf, offline GeoIP.  
**Status:** radni dokument. Fer-play granice atribucije su sastavni deo svakog nalaza.

---

## 1. Izvršni rezime

Reč je o **unutrašnjem ground-truth sistemu** koordinisane mreže naloga koja svojim članovima zadaje zadatke na društvenim mrežama i portalima i beleži ko je šta uradio. Analiza pokazuje:

- **Organizovani ljudi u smenama**, ne klasična automatizacija (auto_score max ~0,45; vrh aktivnosti 9–16h; pad vikendom).
- **Komanda je odvojena od izvršenja:** 156 formalnih koordinatora, ali **0** su mrežni centroidi.
- **550M+ automatskih glasova** sa terminala u uplatnim mestima kladionica u Srbiji i Africi; **66% distinct IP iz Afrike**.
- **Centralne direktive (SS) imaju prioritet** i propagiraju ~17.6% brže; vrh koplja je Vojvodina/Beograd.
- **Granica (fer play):** NE postoji veza mašina↔operater; vlasništvo kladionica NIJE u bazi. Zaključci o mehanizmu i vlasništvu su hipoteze/metodologija, ne dokaz.

## 2. Komandna struktura

- **Task-masteri (ko zadaje):** 135 ljudi kreira sve portal-zadatke; 21 su koordinatori.
- **Nosioci VOTER privilegija:** 61 lica (eksplicitne privilegije), 13 koordinatora, 25 u opštini sa terminalima.
- **Hijerarhija koordinatora (geografska):** region 5, okrug 15, opština 136 (+22 zamenika).
- **Komanda ≠ izvršenje:** od 156 koordinatora u grafu 139, centroida **0**, SS-izdavača 4. Formalna titula i mrežna moć su razdvojeni slojevi.

  Istaknuti (prava + uloge + kreditirani glasovi — NE dokaz pokretanja mašina):
  - Jelena Lavrnić: 387.488 glasova · koordinator · Šabac
  - Miloš Jovanović: 7.698 glasova · koordinator · Beograd-Čukarica
  - Tatjana Benak: 142.504 glasova · koordinator · Beograd-Zvezdara
  - Jasmina Batoćanin: 43.620 glasova · koordinator · Aleksinac
  - Nenad Stamenković: 0 glasova · koordinator · Bojnik
- **Dežurstva (operativni chat, 20.232 poruka):** smene se vode i kontrolišu kroz interni chat (primopredaja 8.811, kontrola 846, nalozi za brisanje 694). Vodeći supervizor: Mirko Osadkovski (Tehnički sekretar za Južnobački okrug).
- **Partijska ekonomija (bodovi):** sistem najviše plaća quote (~4.587) i reply (~3.185) vs lajk (~1.489) — podsticaj za napad/odgovor, ne za pasivan lajk.
  Među top 10 „udarnika“ po bodovima, 7 su jurišnici (ekstremna toksičnost) — ekonomija nagrađuje napadače. Vrh: Jasmina Ratković (1.090.827 bodova).

## 3. Infrastruktura uplatnih mesta i Afrika

- **Mašine:** 1.668 ukupno — 738 Srbija, 930 strano.
- **Brendovi (iz labele mašine `vr_naziv_ss`, tragovi):** Maxi 92 (strano 87), Scooorebet 59 (strano 59), Joker 16 (strano 16), Roma 8 (strano 1), Casino 7 (strano 4).
- **GeoIP:** 1.049/1.668 mašina strano; Afrika 66% distinct IP.
  - Afričke države (IP): Kamerun 472, Kongo (Brazavil) 155, Tanzanija 49, Obala Slonovače 35, DR Kongo 5, Lesoto 2.
  - Vodeći ASN: AS8400=251, AS15964=195, AS30992=172, AS9125=140, AS36912=124.
- **Instaliran softver:** verzionisan klijent (`vr_verzija` 1.0.2.172–177).
- **Regulatorna izloženost (okvir, ne presuda):** ako primarni registar (APR / Uprava za igre na sreću) potvrdi da licencirani priređivač drži terminale korišćene za političke sajber aktivnosti → osnov za zloupotrebu koncesije. **Brend/lokacija su tragovi, ne dokaz vlasništva; „Scooorebet“ (Afrika) se NE izjednačava sa srpskim lancima bez primarnog izvora.**

## 4. Vremenski mehanizam

- **SS kaskada:** centralne direktive propagiraju ~17.6% brže (medijana prve reakcije 582.5s vs 707.0s).
- **Vrh koplja (prvi reagent):** Južnobački (28.771), Beograd (16.537), Srednjobanatski (11.463).
- **Satnica mašina:** Glavni tok glasanja ima jasan noćni pad (00–08h = 7.7%; minimum oko 3–4h), dakle NIJE ravan 24/7 daemon — prati dnevni ritam, uz dug rep do kasno uveče (~22h). Srpske mašine se najčešće javljaju u 9h (otvaranje lokala → ljudski start); strane (afričke) su raspoređenije, sa jačim večernjim/noćnim repom (pre ostaju upaljene i umrežene). Napomena: podela po državi koristi check-in mašina (vr_vreme) i custom glasanje (vrgc) — glavni tok knv nema državu/mašinu (granica podatka).

## 5. Pravni osnov i fer-play atribucija

**Citirani osnov (okvir, ne pravna presuda — nismo pravnici):**
- Budimpeštanska konvencija o sajber kriminalu — čl. 5 (ometanje sistema) i čl. 6 (zloupotreba uređaja: neovlašćeni bot-klijent na komercijalnim terminalima).
- Zloupotreba kockarske licence/koncesije (terminali za igre na sreću korišćeni za političke sajber operacije u Srbiji i Africi).
- Realna izloženost je po **domaćim zakonima** svake jurisdikcije.

**Granice atribucije (obavezno):**
- NE postoji spojni ključ `voter_racunari` (mašina/IP) ↔ `knv_voter_*` (glas kreditiran operateru) → mehanizam „operater → daljinski terminal → glas“ je **hipoteza**, ne dokaz.
- Vlasništvo uplatnih mesta NIJE u bazi → zahteva APR/UIS; ne imenovati pojedince bez primarnog izvora.
- Raspon kontrole koordinatora = geografska nadležnost, ne dokaz pojedinačnog naređenja.
- Kaskada (redosled/latencija) = korelacija (inferirana propagacija).

---

*Detaljni moduli: `docs/analiza_direktiva.md`, `docs/analiza_koordinatora.md`, `docs/analiza_kaskade.md`, `docs/komandna_odgovornost_i_pravni_osnov.md`, `docs/voter_kladionice_infrastruktura.md`, `docs/vlasnicki_profil_kladionica.md`.*