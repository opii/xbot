# Vlasnički profil uplatnih mesta — tragovi, metodologija i granice

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Modul: `src/analysis/betting_corporate.py`
→ `data/geo/betting_corporate.json`.

> ⚠ **Fer play (pročitati prvo):** baza `progress` **NE sadrži** vlasničke ni
> registarske podatke. Ovaj dokument iznosi (a) **tragove iz baze** (brendovi,
> lokacije, broj mašina), (b) **metodologiju** za rezoluciju vlasništva protiv
> primarnih registara, i (c) **javno proverljiv kontekst sa izvorom**. On
> **NE** tvrdi ko su vlasnici, niti imenuje pojedince kao krivce — to zahteva
> primarni izvor (APR / Uprava za igre na sreću) koji nije u našim podacima.

---

## 1. Tragovi iz baze (data-backed)

`voter_racunari`: **1.668 mašina** — 738 označeno kao Srbija, 930 kao strano.
Polje `vr_naziv_ss` (labela mašine) nosi brend/lokaciju. Mašine sa prepoznatim
brend-tokenom (**182**):

| Brend (token) | mašina | Srbija | strano |
|---|---:|---:|---:|
| Maxi | 92 | 5 | **87** |
| Scooorebet | 59 | 0 | **59** |
| Joker | 16 | 0 | 16 |
| Roma | 8 | 7 | 1 |
| Casino | 7 | 3 | 4 |

**Obrazac:** brendovi `Scooorebet`, `Maxi`, `Joker` su skoro isključivo na
**stranim (afričkim)** mašinama; srpske mašine nose nazive **filijala/lokacija**.

**Srpske lokacije (mete za APR/UIS):** Borca Ivana Milutinovica, Borca Centar
(Palilula), Roma Novi Beograd 2, Enjub (Blok 45, N. Beograd), Pozarevac Centar,
Zrenjanin 3, Krusevac Bronks 2, Sivac, Sombor 1, Čačak Solid 2, Bačka Palanka 2…
(+ generički „Tehnika" ×85 — nije kladionica).

**Afričke lokacije (Kongo/Kamerun):** Nkayi Marche Mabombo, Bertoua Bodomo,
Nkongsamba 1, Dolisie Baloumbou, Kinkala, Owando, Rue Mbochis, Nganga Lingolo…

**Dokaz instaliranog softvera:** `vr_verzija` = verzionisan klijent
(`1.0.2.172`–`177`, + „hardcode") na mašinama.

---

## 2. Metodologija rezolucije vlasništva (protiv primarnih registara)

Baza daje **naziv/lokaciju**; vlasništvo se dobija spajanjem sa registrima:

1. **APR — Agencija za privredne registre** (<https://www.apr.gov.rs/>):
   pretraga privrednog društva po nazivu/adresi uplatnog mesta → osnivači, sedište,
   povezana lica, godišnji izveštaji.
2. **Uprava za igre na sreću, Ministarstvo finansija RS** (<https://uis.gov.rs/>):
   registar **licenci/odobrenja** za priređivanje igara na sreću i spisak
   **uplatnih mesta** po priređivaču → koja firma drži konkretnu lokaciju.
3. **Prekogranična veza (Afrika):** brend `Scooorebet`/`Maxi` u Kamerunu/Kongu →
   lokalni regulatori igara na sreću + franšizni/ugovorni tragovi; povezana lica
   tražiti samo kroz **javno dostupne, citabilne** izvore.

Korak-po-korak: `vr_naziv_ss` → adresa uplatnog mesta → APR/UIS → privredno
društvo → osnivači/povezana lica. **Svaki korak zahteva primarni izvor.**

---

## 3. Javno proverljiv kontekst (sa izvorom, uz ogradu)

- Srpske kladionice posluju po **licenci Uprave za igre na sreću**; lanci imaju
  stotine uplatnih mesta (npr. jedan lanac navodi 280–300+ lokala). Primer kako se
  brend mapira na pravno lice: **„Soccerbet"** se javno vodi kao vlasništvo
  **Phuket d.o.o., Beograd** (PIB 107132843), licenca MF RS. *(izvor: javne
  recenzije/zvanični sajt — vidi dole.)*
- **KRITIČNA OGRADA:** javne pretrage **NE potvrđuju** da je brend **„Scooorebet"**
  (iz baze, afričke mašine) isto što i **„Soccerbet"**, niti da je bilo koji srpski
  lanac povezan sa afričkom operacijom. Sličnost imena **nije dokaz**. Ne
  izjednačavati i ne pripisivati bez primarnog izvora.

## 4. Regulatorna izloženost (okvir, ne presuda)

Ako se primarnim izvorom utvrdi da licencirani priređivač drži ove terminale, a
terminali su korišćeni za **nelicencirane političke sajber aktivnosti** (generisanje
550M+ glasova, bot-klijent), moguć je osnov za:
- **zloupotrebu koncesije/licence** za igre na sreću (domaći propisi RS i lokalni
  propisi Kameruna/Konga),
- povezivanje sa već citiranim osnovom: Budimpeštanska konvencija čl. 5/6
  (vidi [`komandna_odgovornost_i_pravni_osnov.md`](komandna_odgovornost_i_pravni_osnov.md)).

## 5. Šta se NE sme tvrditi (rekapitulacija)

- Da konkretno privredno društvo/osoba poseduje ove terminale — **dok se ne potvrdi u APR/UIS**.
- Da je „Scooorebet" (Afrika) = „Soccerbet" (Srbija) ili bilo koji imenovani lanac.
- Da je mašina↔operater veza utvrđena (nije — vidi
  [`voter_kladionice_infrastruktura.md`](voter_kladionice_infrastruktura.md) §5).

**Izvori (javni, za proveru):**
- APR: <https://www.apr.gov.rs/> · Uprava za igre na sreću: <https://uis.gov.rs/>
- Soccerbet/Phuket d.o.o. (primer mapiranja brend→pravno lice): javne recenzije
  (helloworld.rs, legalbet.rs, zvanični soccerbet.rs) — proveriti u APR-u pre upotrebe.
