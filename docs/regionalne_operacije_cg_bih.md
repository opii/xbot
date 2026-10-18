# Prekogranične informacione operacije (Crna Gora & BiH) + proxy mreža

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Modul: `src/analysis/regional_operations.py`
→ `data/geo/regional_operations.json` → `/api/regional_operations`.

Baza (`drzava`) definiše 4 države (1=Srbija, 2=Crna Gora, 3=Hrvatska, 4=BiH). Voter
mašinerija nije gađala samo srpske portale.

> ⚠ **Fer play:** `izvestaj_voter` je **dnevni agregat** (`iv_glasanja`) i **nema
> kolonu države** — država je izvedena iz **portala** (eksplicitni spisak, jer TLD
> nije dovoljan: `b92.net`=RS, `in4s.net`=CG). Proxy veza (`proxy_ip_adrese.portal`)
> je **eksplicitna**.

## 1. Glasovi po državi

| Država | glasova | komentara | portala |
|---|---:|---:|---:|
| Srbija | 554.001.240 | 4.333.431 | 8 |
| **Crna Gora** | **11.526.386** | 100.438 | 5 |
| **BiH** | **6.127.655** | 43.391 | 2 |

**Crna Gora:** in4s.net (6,66M), vijesti.me (2,85M / 19.191 kom), rtcg.me (803k),
cdm.me (795k), pobjeda.me (410k). **BiH:** klix.ba (3,16M), avaz.ba (2,95M).
Ukupno **~17,65M** prekograničnih lažnih glasova.

## 2. Namenska proxy mreža za vijesti.me

`proxy_ip_adrese`: **133 proxy endpointa** (format `IP:port`), raspoređenih na
**samo 4 distinct IP adrese** — i **svih 133 konfigurisano isključivo za
`vijesti.me`**. To je ciljana infrastruktura za zaobilaženje zaštite baš tog
crnogorskog portala (rotacija portova preko malo IP-ova).

**Nalaz:** operacija je **regionalna** (Srbija + CG + BiH), sa namenskom proxy
mrežom uperenom na vijesti.me. Glasovi su agregat iz baze; proxy↔portal je dokazana
veza.

Reprodukcija: `./venv/bin/python src/analysis/regional_operations.py`.
