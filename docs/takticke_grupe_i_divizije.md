# Taktičke grupe i divizije (paralelna hijerarhija)

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Modul: `src/analysis/tactical_groups.py`
→ `data/geo/tactical_groups.json` → `/api/tactical_groups`.

Pored geografske komande (Region→Okrug→Opština), baza (`korisnici_grupe` +
`korisnici_grupe_aktivisti`) otkriva **paralelnu funkcionalnu hijerarhiju**: **30
internih grupa** sa **1.232 članstava**.

## Kategorije

| Kategorija | grupa | članstava |
|---|---:|---:|
| **TikTok divizija** | 3 | 386 |
| Voter administracija | 7 | 193 |
| Koordinacija | 4 | 191 |
| Vesti / Deljenje | 2 | 139 |
| Nadzor i kontrola | 5 | 116 |
| Specijal / sastanak | 2 | 107 |
| Analiza komentara | 2 | 27 |
| Instagram | 1 | 17 |
| Hit Tvit (rapid) | 1 | 4 |

## Istaknute strukture

- **TikTok divizija — abecedna podela** (jasna organizacija po prezimenu): „Tik Tok
  - Dragana" (A–I, 121), „Tik Tok - Nenad" (J–M, 132), „Tik Tok - Danijela" (N–Z,
  133). Ukupno ~386 ljudi samo za TikTok.
- **Voter administracija** (grupe „Voter glasanje", „voter admini", „Voter
  administracija"): operativni tim za mašineriju glasanja.
- **Hit Tvit (rapid)** — mala grupa (4) za koordinaciju u realnom vremenu (npr.
  tokom TV emisija / „javljanja").
- **Nadzor i kontrola** — „Kontrolori", „Sekretari", „Monitoring", „protokol -
  dežurni": interni nadzorni sloj.

**Nalaz:** organizacija nije samo geografska — postoje **namenske divizije po
platformi i funkciji**, uključujući rapid-reakciju i interni nadzor. Članstvo je
eksplicitno (`korisnici_grupe_aktivisti`); imena članova ključnih komandnih grupa su
u JSON/UI (operateri — rukovati odgovorno).

Reprodukcija: `./venv/bin/python src/analysis/tactical_groups.py`.
