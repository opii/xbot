# Analiza kaskade — centralna direktiva (SS) → teren kroz vreme

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Reprodukcija:
`src/analysis/cascade.py` → `data/geo/cascade.json` → `/api/cascade` → UI
pogled **„⏱ Kaskada (SS → teren)"**.

Rekonstruiše kako se zadatak sa oznakom **centralnog izvora** (SS = „super
specijal", ČET = „Šefov video iz četa") širi od kreiranja (izdavač) do izvršenja
(operateri na terenu), sa geografskim lead-lag obrascem.

> ⚠ **Fer play:** redosled i latencija su **korelacija** (ko obično reaguje ubrzo
> posle kreiranja zadatka) — **inferirana propagacija**, NE dokaz da je pojedinac
> lično prosledio poruku konkretnom operateru. Nema eksplicitne „forward" veze u bazi.

---

## 1. SS ima prioritet (headline)

Medijana vremena do **prve reakcije** na zadatak:

| Tip zadatka | zadataka | medijana prve reakcije |
|---|---:|---:|
| **SS/ČET** (centralni) | 724 | **582,5 s** (~9,7 min) |
| baseline (obični) | 139.795 | 707,0 s (~11,8 min) |

**SS zadaci propagiraju ~17,6% brže** — centralne direktive dobijaju prioritet na
terenu. Obim SS akcija je mali (4.970 na 724 zadatka, ~7 po zadatku) = to su
**specijalizovani zadaci užoj grupi**, ne masovne kampanje.

## 2. Vrh koplja — ko reaguje prvi

„Prvi reagent" = operater sa najranijim vremenom akcije na datom zadatku; gledamo
iz kog je okruga. Preko SVIH zadataka:

| # | Okrug | prvih reakcija | SS-stopa (prvi/učešće) |
|---|---|---:|---:|
| 🏆 | Južnobački (Novi Sad) | 28.771 | 0,29 |
| 2 | Beograd | 16.537 | **0,35** |
| 3 | Srednjobanatski (Zrenjanin) | 11.463 | **0,34** |
| 4 | Mačvanski | 8.274 | — |
| 5 | Raški | 7.556 | — |

**Vojvodina (Južnobački + Srednjobanatski) i Beograd su „vrh koplja"** — otvaraju
kampanju. Poklapa se sa koncentracijom operatera, centroida i kladionica (🎰) u
tim oblastima (vidi [`analiza_koordinatora.md`](analiza_koordinatora.md)).

## 3. Ritam po satu

SS zadaci se **kreiraju** i **izvršavaju** u radnom ritmu (vrh 9–16h), isti dnevni
obrazac kao cela mreža (kancelarijske smene) — ne 24/7 automatika. Grafikon u UI
poredi krivu kreiranja (izdavač) i izvršenja (teren).

## 4. Izdavač SS → okrug koji izvršava (prekoregionalni tok)

Top SS izdavači i okruzi koji najviše izvršavaju njihove direktive:

| Izdavač (okrug izdavača) | → izvršava okrug | akcija |
|---|---|---:|
| Lidija Milićević (Rasinski) | → **Beograd** | 236 |
| Ivana Ranković (Mačvanski) | → **Beograd** | 199 |

**Nalaz:** SS direktive se izvršavaju **prekoregionalno** — izdavač je u jednom
okrugu, a njegove smernice „padaju" u drugi (najčešće Beograd/Vojvodina). To znači
da SS nije lokalna stvar okruga izdavača nego **centralni kanal** koji aktivira
teren po celoj zemlji. Dosledno nalazu da su izdavači SS-a administrativni sloj
odvojen od geografije (vidi [`analiza_direktiva.md`](analiza_direktiva.md)).

---

## 5. Lanac (koliko podaci nose)

```
IZDAVAČ (SS kreira zadatak)   →  [+582s medijana]  →  TEREN (prvi reagent → ostali)
tu_kreirano_korisnik_id          ✔ latencija           tuka_korisnik_id → k_okrug
tu_kreirano_vreme, SS oznaka     ✔ redosled okruga     tuka_vreme
✘ „prosledio poruku osobi X": NEMA eksplicitne veze (inferirano iz vremena)
```

Sve brojke reproducibilne: `./venv/bin/python src/analysis/cascade.py`.
