# Komandna odgovornost & pravni osnov (fer play)

**Projekat:** Cacix · **Datum:** Oktobar 2026.

Ovaj dokument iznosi **samo ono što podaci dokazuju** i jasno razdvaja
(a) činjenice iz baze, (b) citirani pravni osnov, (c) ono što se NE može tvrditi.

---

## 1. Granica atribucije (najvažnije, fer play)

**Podaci NE povezuju pojedinačne operatere sa afričkim (ni bilo kojim) voter
mašinama.** Provereno:
- `voter_racunari` (mašine, uklj. afričke) ima IP i ime kladionice, ali **nema
  `korisnik_id`**.
- Glasovi `knv_voter_*` imaju kreditiranog korisnika, ali **nemaju referencu na
  mašinu/IP/državu**.
- Ne postoji spojni ključ između to dvoje.

**Zaključak:** tvrdnja „osoba X pokreće botove u Africi" se **ne može** potkrepiti
ovim podacima. Svako ko to tvrdi izmišlja vezu koje nema. Zato ovde ne pravimo
listu „optuženih za afričke mašine".

## 2. Šta podaci STVARNO nose (atribucija)

Najjača atribucija koju baza dozvoljava su **dodeljena prava + uloge + kreditirani
glasovi + ko-lokacija**:

- **61 korisnik ima eksplicitne VOTER privilegije** (`korisnici_privilegije`):
  `IZVEŠTAJI_VOTER` (15), `VOTER_DODATAK` (35), `VOTER_KOMENTARI` (59) — ukupno 109
  dodela, 61 različita osoba. Od toga **13 su koordinatori**, **25 u opštini sa
  terminalima kladionica**.
- **Kreditirani glasovi** (`knv_voter_korisnik_id`): samo 90 ljudi nosi 4,5M
  automatskih glasova; vrh: Žarko Popović 849.162, Milica Radovanović 537.705.
- **Dvostruka uloga:** Nenad Stamenković — #1 task-master (165.074 zadatka),
  koordinator (okrug+opština+region), i nosilac **sve tri** VOTER privilegije.
- **Ko-lokacija sa terminalima:** koordinatori u opštinama sa kladionicama
  (Aleksandar Ljubinković — Subotica 🎰14; Srđan Gašić — Kruševac 🎰9).

Ovo je faktička odgovornost (prava + uloge + izvršeni glasovi), vidljiva u
exploreru: pogled **„⚖ Komandna odgovornost & Voter"**.

## 3. Citirani pravni osnov (nije pravna presuda)

> Napomena: autor projekta navodi ove osnove; nismo pravnici i ne donosimo
> presude. Ovde ih beležimo kao okvir, uz činjenice iz baze.

- **Budimpeštanska konvencija o sajber kriminalu** — čl. 5 (ometanje sistema:
  sistemsko zasipanje/manipulacija portala) i čl. 6 (zloupotreba uređaja:
  instalacija neovlašćenog bot-softvera na komercijalnim terminalima; verzije
  klijenta `1.0.2.149`–`1.0.2.163`).
- **Zloupotreba kockarske licence** — terminali licencirani za igre na sreću
  (Scooorebet/Maxi/Joker/Casino) u Srbiji, Kamerunu i Kongu korišćeni za političke
  sajber operacije (mogući osnov za oduzimanje koncesije).

**Realna izloženost** je po **domaćim zakonima** svake jurisdikcije (računarska
krivična dela, izborno/medijsko pravo, propisi o igrama na sreću), ne po
„međunarodnom krivičnom pravu" u užem smislu.

## 4. Lanac (koliko podaci nose)

```
KOORDINATOR (VOTER privilegija, zadaje)  →  OPERATERI (komentari, burst)  →  VOTER (glasanje)
 korisnici_privilegije + vu_korisnik_id      CO_TEMPLATE / knv_vreme          knv_voter_vreme
 ✔ dokazano                                   ✔ dokazano                       ✔ dokazano (sekundno)
                                                                               ✘ mašina/IP ↔ osoba: NEMA veze
```

Reprodukcija: `src/analysis/command_responsibility.py` → `data/geo/command_voter.json`.
Heuristike odlučivanja: [`AGENTS.md`](../AGENTS.md) i
[`docs/analiza_komanda_i_voter.md`](analiza_komanda_i_voter.md).
