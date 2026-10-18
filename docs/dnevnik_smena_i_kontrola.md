# Dnevnik dežurstava i kontrola kvaliteta (operativni chat)

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Modul: `src/analysis/shift_chat.py`
→ `data/geo/shift_chat.json` → `/api/shift_chat` → UI **„💬 Dnevnik dežurstava"**.

Tabela `chat_twitter_brisanje` (**20.232 poruke**) je interni operativni chat mreže:
dnevnici smena, primopredaje, kontrola kvaliteta i krizni nalozi za brisanje
tvitova. Poruke sadrže HTML (čisti se), vreme i `ctb_korisnik` (operater).

> ⚠ **Fer play:** poruke su interni operativni logovi **realnih ljudi** (dežurni/
> supervizori — operateri sistema). Iznosi se **operativni** sadržaj (smena,
> kontrola, brisanje), ne privatni lični podaci. Imena se tretiraju kao i drugde
> u sistemu (za deljenje van tima pseudonimizovati).

---

## 1. Kako smo klasifikovali (heuristika)

| Tip poruke | Regex (ci) | Broj |
|---|---|---:|
| **Primopredaja smene** | `smena\|primopredaj\|odjava\|preuzima\|koleg\|laku noć` | 8.811 |
| **Kontrola / vraćanje** | `vratila\|nije po pravil\|ispravite\|ponovite\|analiz\|proveri` | 846 |
| **Krizno brisanje** | `obriši\|obrisan\|brisanje\|pogrešan link\|greška` | 694 |

## 2. Ko vodi smene (supervizori)

Najviše poruka (= dežurni oficiri koji vode smenu i kontrolišu kvalitet):

| Poruka | Ime | Funkcija / okrug |
|---:|---|---|
| 5.045 | **Mirko Osadkovski** | Tehnički sekretar za Južnobački okrug |
| 3.336 | Aleksandra Munćan | Južnobanatski okrug |
| 2.159 | Olivera Savićević | Južnobački okrug |
| 1.039 | Jasmina Adamović | Severnobanatski okrug |
| 869 | Nataša Sušić | Severnobački okrug |
| 768 | Biljana Kirov | Koo opštine |

**Veza sa drugim modulima:** Mirko Osadkovski je istovremeno **#2 „udarnik" po
partijskim bodovima** (vidi [`gamifikacija_i_kvote.md`](gamifikacija_i_kvote.md)) i
„Jurišnik" (ekstremna toksičnost). Južnobački okrug je i **„vrh koplja"** u kaskadi
([`analiza_kaskade.md`](analiza_kaskade.md)) — isti centar operativne kontrole.

## 3. Vremenski profil (predaja smena)

Pikovi poruka po satu: **12h, 15h, 19h** (+ jutarnja 8h i kasna 23h) — tri-četiri
dnevne smene. Potvrđuje organizovan rad u smenama (nije 24/7 automatika).

## 4. Šta rade dežurni (verbatim raporti)

Primopredaje su strukturirani raporti smene, npr.:
- *„Smena je protekla radno. Na početku smene kvotovalo se smanjenim intenzitetom
  i to uglavnom tvitovi SNS Srbije i Detektora. Vesti sa portala su se povremeno
  delile…"*
- *„Smena je protekla radno. Smenu je obeležilo uključenje šefa, sa otvaranja nove
  fabrike… Pisalo se smanjenim intenzitetom…"*

Kontrola kvaliteta (vraćanje zadataka):
- *„Radmila R. — Smederevska Palanka. Uporno potvrđuje da je uradila, a nije.
  Vratila sam je ponovo."*

Krizni nalozi za brisanje:
- *„Obrisano … — Beograd-Lazarevac"*, *„Molim Vas obrisite zadnja dva"*,
  *„pogrešan menšn, mnogo slovnih grešaka… link koji je ostao kada podele vest."*

**Nalaz:** chat pokazuje **aktivnu kontrolu kvaliteta i sanaciju grešaka** (brisanje
pogrešnih/razotkrivajućih tvitova) — ljudski vođena operacija sa primopredajom
smene, ne autonomni botovi.

---

Reprodukcija: `./venv/bin/python src/analysis/shift_chat.py`. Granice: ovo je
sadržaj chata kakav sistem čuva; ne izvode se zaključci van zabeleženog.
