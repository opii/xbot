# Multi-platformski arsenal i zvanična dežurstva

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Modul: `src/analysis/multiplatform.py`
→ `data/geo/multiplatform.json` → `/api/multiplatform_stats`.

Cacix nije bio samo „Twitter mašinerija" — upravljao je **preko 51.700 naloga na 6
platformi**, uz **15 zvaničnih kategorija dežurstava**.

## Nalozi po platformi

| Platforma | naloga | operatera |
|---|---:|---:|
| Twitter | 24.801 | 4.389 |
| Instagram | 8.761 | 7.739 |
| TikTok | 7.957 | 7.709 |
| Facebook | 6.176 | 4.714 |
| Threads | 3.366 | 3.329 |
| Reddit | 642 | 640 |
| **Ukupno** | **51.703** | — |

## Unakrsna matrica (koliko mreža po operateru)

- **7.178 operatera pokriva 3+ mreže**, **4.769 pokriva 4+**. Dakle isti ljudi rade
  koordinisano preko više platformi (nije platform-specifično).

## Instagram operacija

`arhiva_instagram_unos`: **10.891 zadatak**; `arhiva_instagram_korisnici_komentari`:
**68.710 komentara** — paralelna komentarska mašinerija i na Instagramu.

## 15 kategorija dežurstava (tabela `dezurstva`)

TWITTER NADZOR · TWITTER ANALIZA · ANALIZA KOMENTARA · ANALIZA KOMENTARA - ADMIN ·
VOTER · VESTI · TWITTER PRINT SCREEN · MONITORING · INSTAGRAM · SAJTOVI · GLASANJE ·
KOMENTARISANJE · FACEBOOK I LIVE · TELEGRAM · ADMINISTRACIJA.

**Nalaz:** organizovana, višeplatformska operacija sa formalizovanim smenama po
funkciji (uključujući Telegram, „print screen" dokazivanje, nadzor i voter).

Reprodukcija: `./venv/bin/python src/analysis/multiplatform.py`.
