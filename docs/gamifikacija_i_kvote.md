# Gamifikacija, kvote i partijska ekonomija bodova

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Modul: `src/analysis/gamification_points.py`
→ `data/geo/gamification.json` → `/api/gamification` → UI **„🎯 Kvote & Bodovanje"**.

Izvori: `izvestaj_dnevni` (**2,22M** dnevnih izveštaja po operateru, bodovi po svakom
tipu akcije + geografija; 8.746 operatera, 2023–2025) i `timski_bodovi` (264 zapisa).

> ⚠ **Fer play:** bodovi su **interna partijska ekonomija** koju sistem sam dodeljuje.
> Ne izvode se zaključci o pojedincu van onoga što je sistem zabeležio.

---

## 1. Vrednost po akciji (koliko sistem plaća)

`per_action = Σbodovi / Σcount` nad `izvestaj_dnevni`:

| Akcija | bodova/akcija |
|---|---:|
| **quote (citat)** | **4,59** |
| reply (odgovor) | 3,19 |
| komentar prijavljen | 3,17 |
| deljenje vesti | 1,85 |
| retweet | 1,59 |
| lajk | 1,49 |
| SNS link | 1,34 |
| komentar objavljen | 0,98 |

**Nalaz:** citat (quote) vredi **~3× lajk**, odgovor ~2×. Ekonomija **podstiče
aktivno kvotovanje i odgovaranje** (uključujući napade), ne pasivan lajk — što
objašnjava zašto je mreža dominantno „odgovarač" i zašto su mete opozicije gađane
kvotom/odgovorom.

## 2. Top „udarnici" (bodovi) i njihova uloga

Rang-lista po ukupnim bodovima (`iz_ukupno_bodovi`), sa bihevioralnom ulogom iz grafa:

| # | Operater | Bodovi | Uloga | Toksičnost |
|---|---|---:|---|---|
| 1 | Jasmina Ratković | 1.090.827 | Mešovit | Netoksičan (Pojačivač) |
| 2 | **Mirko Osadkovski** | 1.082.420 | Odgovarač | **Ekstremna (Jurišnik)** |
| 3 | Jasmina Adamović | 1.042.202 | Odgovarač | **Ekstremna (Jurišnik)** |
| 4 | Janko Langura | 874.642 | Mešovit | Netoksičan |
| 5 | Ivana Raković | 862.982 | Pojačivač | **Ekstremna (Jurišnik)** |

**Nalaz:** među top 10 po bodovima, **7 su „Jurišnici" (ekstremna toksičnost)** —
**ekonomija nagrađuje napadače**. #2 (Mirko Osadkovski) je ujedno #1 supervizor u
operativnom chatu ([`dnevnik_smena_i_kontrola.md`](dnevnik_smena_i_kontrola.md)):
komanda, kontrola i vrh produktivnosti u istoj osobi.

## 3. Bodovi po opštini

Opštine sa najviše osvojenih bodova (`izvestaj_dnevni` grupisano po `iz_opstina_id`)
dostupne u JSON/UI (top 25). Pokazuje gde je „proizvodnja" najintenzivnija.

## 4. Timski bodovi i kvote (granica podatka)

`timski_bodovi`: 264 zapisa, ali **samo 2 različita lidera** i `tb_procenat` ima
**samo dve vrednosti (30 i 50)**. Zato `tb_procenat` **NIJE merilo realizacije kvote**
(nema „≥100% ispunjeno") — tretira se kao fiksna težina/kategorija. Tabela daje
timske agregate (bodova, broj aktivista, quote/reply), ali je **preuska za zaključak
o ispunjenosti normi po timovima**; za „proizvodnju" po geografiji koristiti bodove
po opštini iz `izvestaj_dnevni` (§3).

---

Reprodukcija: `./venv/bin/python src/analysis/gamification_points.py`.
