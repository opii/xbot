# Analiza direktiva (smernica) — šta se tačno naređuje

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Reprodukcija:
`src/analysis/directives.py` → `data/geo/directives.json` → `/api/directives` →
UI pogled **„📋 Direktive"**.

Direktiva = tekst naloga koji operater dobija uz zadatak. Dve kolone:
- **tviter**: `arhiva_twitter_unos.tu_smernica` (498.648 nepraznih, 2.195 distinct)
- **vesti/komentari**: `arhiva_vesti_unos.vu_smernica` (61.775 nepraznih, 3.578 distinct)

---

## 1. Heuristika odlučivanja (kristalno jasno)

Svaka direktiva se klasifikuje po 4 nezavisne dimenzije. Taksonomija radi na
**normalizovanom** tekstu (lowercase + ćirilica→latinica + skidanje dijakritika),
pa „Одговарамо", „odgovaramo" i „ODGOVARAMO!" padaju u istu kantu.

| Dimenzija | Vrednosti | Pravilo (na normalizovanom tekstu) |
|---|---|---|
| **action** (akcija) | lajk / retvit / citat / odgovor / komentar / deljenje | Za tviter: POUZDANO iz `tu_akcija` (0=lajk,1=rt,2=odgovor,3=citat). Inače iz teksta: `kv/kvot/quote`→citat, `rt/retvit`→retvit, `fv/lajk/like`→lajk, `odgovor/reply`→odgovor, `deli/seruj/story`→deljenje. |
| **tone** (ton) | napad / odbrana / neutral | **napad** ako sadrži `brutalno\|zezamo\|sprdamo\|hejt\|resavamo\|pukli\|lazov\|razbij\|rafal\|napad\|unist`; **odbrana** ako `branim\|hvalim\|podrsk\|slavim\|cestit\|cuvamo`; inače **neutral** (čista akcija bez tona). |
| **source** (izvor) | SS / ČET / ŠEF / automatika / bez | **SS** = „super specijal" / „iz ss" (centralni spec); **ČET** = „iz četa / video iz četa"; **ŠEF** = pominje „šef/šefov"; **automatika** = `vu_automatika_kreirala=1`; inače **bez**. |
| **cross** (cross-platform) | da / ne | `delim\|seruj\|na svim mrezama\|story\|okacite link\|kopirajte link\|potvrdite da ste podelili`. |

> **Zašto baš ovi pragovi:** ton koristi ISTI agresivni regex kao metrika
> toksičnosti (jurišni odredi) — generičko „odgovaramo" se NAMERNO ne broji kao
> napad, inače bi skoro svi odgovori bili „napad". Ton napada se vidi tek u izboru
> mete (vidi §3), ne u tekstu direktive.

---

## 2. Taksonomija — šta dominira

**Tviter (498.648):** 99% je čista akcija (`neutral`). Eksplicitno napadačkih
direktiva samo **2.712**, odbrambenih **1.446**. Dominira `odgovor` (akcija=2,
394k zadataka) — mreža je pre svega „odgovarač".

**Vesti (61.775):** `napad` **3.266**, `odbrana` 244. Izvor je ovde eksplicitniji:
**6.395 ŠEF-referenci**, **2.195 „iz četa"**, 1.736 automatskih.

Primeri (iz baze, verbatim):
- napad: „odgovaramo brutalno" (×1.344), „Zezamo ih što ih je malo, pukli su ko
  zvečke" (×112), „Rešavamo hejtere".
- odbrana: „odgovaramo branimo šefa" (×271), „Max lajk Šef SNS".
- SS: „odgovaramo po smernici iz ss / super specijala" (×560+).
- ČET: „Šefov video iz četa", „potvrdite da ste podelili Šefov video iz četa".

---

## 3. Lanac: direktiva → meta → reakcija

### Tviter: ton × klasa mete + sinhronija
Meta se vadi iz `tu_link_tvita` (handle), klasifikuje u `opozicija` (kurirani
set: marinikatepic, kpromeni, onlinedanas, n1srbija, novarsonline, …), `rezim`
(sns_srbija, avucic, milos_vucevic, …) ili `ostalo`. Reakcija = medijana
latencije zadatak→odgovor i `burst10` (udeo odgovora u prvih 10 min).

| ton | meta | n odgovora | med latencija | burst10 |
|---|---|---:|---:|---:|
| neutral | **režim** | 631 | **1.484 s** | **0,304** |
| neutral | opozicija | 113.991 | 2.767 s | 0,167 |
| neutral | ostalo | 279.286 | 3.529 s | 0,147 |
| napad | opozicija | 587 | 5.622 s | 0,102 |
| odbrana | opozicija | 1.194 | 3.598 s | 0,114 |

**Nalazi:**
1. **Najtešnja sinhronija = pro-režim amplifikacija** (`neutral→režim`, burst
   0,304 — duplo veći od proseka). Brza, koordinisana hvala režimskim nalozima.
2. **Napad na opoziciju ne ide kroz tekst direktive** — eksplicitnih napad-odgovora
   na opoziciju je samo 587, ali pod generičkim „odgovaramo" ide **113.991**
   odgovora na iste opozicione mete. **Ton napada je u izboru mete, ne u reči.**
3. Eksplicitne napad-direktive su *sporije* (burst 0,10) — operater ručno sastavlja
   uvredu; amplifikacija (lajk/kvot) je brža od pisanja napada.

### Vesti: portal → prolaznost moderacije
Prolaznost = objavljeni / prijavljeni komentari.

| portal | ton | zadataka | prolaznost |
|---|---|---:|---:|
| kritički | napad | 220 | **3,8%** |
| kritički | neutral | 1.798 | 2,9% |
| tabloid | napad | 122 | **40,8%** |
| tabloid | neutral | 9.525 | 3,3% |
| tabloid | odbrana | 59 | 49,5% |

**Nalaz:** kritički mediji seku **~97%** (moderacija radi), tabloidi propuštaju
**33–49%** — tabloidi rado objavljuju mrežne (i napadačke) komentare. Potvrda
„Infiltrator vs Podrška" nalaza iz ugla direktiva.

---

## 4. Centralni komandni izvor (SS / ČET / ŠEF) — zaseban nalaz

Postoji sloj direktiva sa oznakom **centralnog izvora**: „super specijal (SS)" i
„Šefov video iz četa". To je komanda IZNAD koordinatora — gotova smernica koja se
kaskadira naniže.

- **1.099 SS + 70 ČET** tviter/vesti direktiva; **30 različitih izdavača**
  centralnih direktiva.
- Top izdavači SS-a (po obimu): **Lidija Milićević** (192), **Branislava Spevak**
  (152), **Ivana Ranković** (145), **Dragoslav Janjić** (101), **Zorica Holasek**
  (93, org=0,339 — jedina sa jakim grafom), **Milica Tmušić** (64, koordinator).
- **Većina izdavača SS-a NIJE jaka u grafu** (org≈0) — to je zaseban *administrativni*
  komandni sloj (unose smernice), različit od izvršnih centroida. Ovo je sam po
  sebi nalaz: komanda i izvršenje su razdvojeni.

### ⚖ Granica atribucije (fer play, obavezno)
**Kreator u bazi = ko je zadatak UNEO u sistem.** Reči „Šef" i „video iz četa" u
tekstu direktive referišu na **uzvodnog čoveka-lidera** koji **nije nužno red u
bazi**. Zato se **NE sme** reći „osoba X iz baze JESTE Šef" niti da je lično
autor politike — podaci pokazuju samo ko je unosio smernice označene kao centralne.
Isto pravilo kao kod voter atribucije ([`komandna_odgovornost_i_pravni_osnov.md`](komandna_odgovornost_i_pravni_osnov.md)).

---

## 5. Lanac (koliko podaci nose)

```
CENTRALNI IZVOR (SS/ČET)   →  KOORDINATOR (zadaje)  →  OPERATER (akcija)        →  META
tu/vu_smernica ~ 'ss|cet'     tu/vu_kreirano_kor_id    tuka_akcija + tuka_vreme    tu_link_tvita / vu_portal
✔ oznaka u tekstu             ✔ ko je uneo             ✔ reakcija (latencija)      ✔ klasa mete / prolaznost
✘ osoba ≠ „Šef" (nema veze u bazi)
```

Sve brojke reproducibilne: `./venv/bin/python src/analysis/directives.py`.
