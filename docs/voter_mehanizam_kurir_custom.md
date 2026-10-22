# Voter mehanizam: relay nalozi (K2) i headless JS/XPath injekcija (K3)

**Projekat:** Cacix · **Datum:** Oktobar 2026.
Moduli: `src/analysis/voter_kurir_links.py` → `data/geo/voter_kurir_accounts.json`
(`/api/voter_kurir`) i `src/analysis/voter_custom_actions.py` →
`data/geo/voter_custom_actions.json` (`/api/voter_custom`).

> ⚠ **Fer play / sigurnost:** lozinke (`voter_kurir_nalozi.password`) se **NE čitaju
> ni izlažu** (samo postojanje/broj). Tajne hardkodovane u JS kodu su **redigovane**.
> `racunar_id → vr_id` je **dokazan FK**. „kurir“ = **relay** nalog — **NE tvrdi se**
> da su to nalozi na portalu Kurir.rs (nema takve veze u bazi).

## K2 — Kurir/relay nalozi ↔ mašine

`voter_kurir_nalozi`: **1.514 naloga** (svi `aktivan=1`, svi sa lozinkom — koja se
ne izlaže), kreirani preko **jednokratnih (temp-mail) domena**: `undeep.xyz` (213),
`smallntm.lol` (206), `dunkos.xyz` (170), `apwoghkn.site` (115), `nbmbb.com` (94)…
Kolona `vreme_uzimanja` beleži početak masovnog preuzimanja/aktivacije **28.10.2024. u 09:14:01**
(nakon čega u naredne dve godine klijent `voter_racunari` prolazi kroz **32 verzije**
od `1.0.2.149` do `1.0.2.177`; vidi [`istorijat_i_arhitektura_platforme.md`](istorijat_i_arhitektura_platforme.md)).

Preko `racunar_id → voter_racunari.vr_id`: nalozi su dodeljeni na **114 mašina**,
od kojih **111 strano** (afričke lokacije: Bunker, Rue Mbochis, Nkongsamba…) i **3
Srbija**.

**Nalaz (mehanizam):** mašine u uplatnim mestima (uglavnom afrička) nisu samo slale
anonimne glasove — imale su **registrovane naloge (email+lozinka)** za autorizaciju/
upis. Konkretan ciljani portal **nije** eksplicitno vezan u tabeli → interpretacija
„nalozi za Kurir.rs" ostaje **hipoteza**, ne dokaz.

## K3 — Headless automatizacija (JS/XPath injekcija)

`voter_glasanje_custom` (4 akcije) + `voter_racunari_glasanje_custom` (511 izvršenja,
`vrgc_racunar_id → vr_id`). Sistem šalje klijentima **sirovi JavaScript** koji
emulira čoveka u browseru:

| # | Meta (link) | Tehnike | Izvršenja |
|---|---|---|---:|
| 1 | kurir.rs (tenis, Novak/Sinner) | XPath (`document.evaluate`) + `scrollIntoView` + `click` | 23 |
| 2 | rtcg.me (fudbal, Sutjeska) | XPath + `scrollIntoView` + `click` | 31 |
| 4 | avaz.ba (Kosovo, protesti) | `fetch`/XHR (`myHeaders`) | 101 |
| 5 | progress.rs | `FormData` POST (tajna **redigovana**) | 4 (3 strane mašine) |

**Nalaz (mehanizam):** automatizacija simulira ljudski klik i skrol (`scrollIntoView`,
`el.click()`) i/ili direktno šalje zahteve (`fetch`/`FormData`) na tačno određene
URL-ove — tehnički dokaz emulacije čoveka u pretraživaču na komercijalnim portalima.

Reprodukcija: `./venv/bin/python src/analysis/voter_kurir_links.py` i
`./venv/bin/python src/analysis/voter_custom_actions.py`. Vidi i
[`voter_kladionice_infrastruktura.md`](voter_kladionice_infrastruktura.md).
