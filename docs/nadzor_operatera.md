# Nadzor i telemetrija nad operaterima (F12 inspector, uređaji, SMS)

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Modul: `src/analysis/system_surveillance.py`
→ `data/geo/system_surveillance.json` → `/api/system_surveillance`.

> ⚠ **Fer play / privatnost:** telefoni (`sp_telefon`) i 2FA kodovi se **NE izlažu**
> (maska/tip/status). Vremenska poklapanja označena su kao **korelacija**, ne uzrok.
> Hipoteze (npr. „farma telefona") proveravaju se podatkom, ne pretpostavljaju.

## K5 — Kontraobaveštajni nadzor (otvoren_inspector)

Sistem je slao telemetriju centrali **čim operater otvori DevTools / F12 konzolu**.
**306 zapisa, 85 operatera**, svi u **uskom prozoru 21.–27.07.2023** (jedna nedelja).
Najpraćeniji: **Brankica Rašić (38×)**, Ivana Rajković (25×), Violeta Jakovljević (20×).

**Nalaz:** postoji aktivan nadzor nad sopstvenim aktivistima (ko „zaviruje pod
haubu"). Koncentracija baš u toj nedelji (**21.–27. jul 2023.**) direktno **korelira**
sa velikim javnim curenjem spiska od **>14.000 naloga i >3.000 imena** iz jula 2023.
(o kom je izveštavao RSE i koje je potvrđeno u Skupštini) — sve ukazuje da je nakon
curenja spiska sprovedena interna kontraobaveštajna provera ko od operatera otvara
inspektor u pretraživaču (vremenska korelacija; vidi i [`istorijat_i_arhitektura_platforme.md`](istorijat_i_arhitektura_platforme.md)).

## K6 — Digitalni otisak (korisnici_uredjaji)

**29.682 uređaja** praćeno (kolačić `ku_kolac_px`, LocalStorage GUID
`ku_local_storage_gh`, `ku_uredjaj_parametar`). Operativni sistemi:

| OS | uređaja | operatera |
|---|---:|---:|
| Android | 22.297 | 3.304 |
| Windows | 4.732 | 783 |
| iOS | 2.273 | 561 |
| Linux | 269 | 95 |

- **Multi-device:** **1.298 operatera koristi 5+ uređaja/pretraživača** (jedan čovek,
  mnogo otisaka).
- **Deljeni uređaj (3+ operatera isti parametar): 0.** → hipoteza o „farmi telefona"
  preko deljenog `ku_uredjaj_parametar` **NIJE potkrepljena** ovim poljem (parametar
  je po otisku jedinstven). Dominacija Androida ostaje jak hardverski signal.

## K7 — SMS gateway „Internet Tim" (arhiva_sms_poruke)

**11.627 SMS poruka** preko zvaničnog telekom gateway-a sa alfanumeričkim pošiljaocem
**„Internet Tim"**, raspon **2023-01 → 2025-08**, **~93% isporučeno** (`sp_status=2`).
Sadržaj: **11.621 2FA verifikacioni kod** + 6 administrativnih test poruka.

**Nalaz:** mreža koristi **legitiman komercijalni SMS gateway** za 2FA autentifikaciju
operatera (profesionalna infrastruktura). **Telefoni i kodovi se ne prikazuju** —
samo tip, status i obim.

Reprodukcija: `./venv/bin/python src/analysis/system_surveillance.py`.
