# Analiza koordinatora — hijerarhija komande i raspon kontrole

**Projekat:** Cacix · **Datum:** Oktobar 2026. · Reprodukcija:
`src/analysis/coordinators.py` → `data/geo/coordinators.json` → `/api/coordinators`
→ UI pogled **„🏛 Koordinatori"**.

Komandna struktura mreže je **geografska**: `Region (7) → Okrug (26) → Opština
(162)`. Koordinatorske pozicije su u namenskim tabelama (autoritativne).

---

## 1. Struktura (koliko čega)

| Nivo | Tabela | Pozicija | Zamenika |
|---|---|---:|---:|
| Region | `region_koordinator` | 5 | 3 |
| Okrug | `okrug_koordinator` | 15 | 3 |
| Opština | `opstina_koordinator` | 136 | 16 |
| **Ukupno** | | **156** | **22** |

Operatera (registrovanih `korisnici`): **9.314**, svi geolocirani. Po regionima:
Vojvodina 2.973 · Zapadna Srbija 1.996 · Centralna Srbija 1.713 · Južna Srbija
1.297 · Grad Beograd 872 · Istočna Srbija 457 (+ „TEST" 6).

## 2. Raspon kontrole (heuristika)

Za svaki čvor hijerarhije merimo 5 veličina (agregirano naviše: opština→okrug→region):

| Metrika | Značenje | Izvor |
|---|---|---|
| **operators** | registrovani operateri u toj geografiji | `korisnici.k_opstina/k_okrug/k_region` |
| **centroids** | koliko ih je jakih u grafu (izvršna moć) | Neo4j `tw_organizer`/`cc_organizer` |
| **command** | koliko ih zadaje zadatke (komandni sloj) | distinct `tu_kreirano_korisnik_id` ∪ `vu_korisnik_id` |
| **ss_issuers** | koliko izdaje centralne direktive | kreatori sa `~ 'super spec\|iz ss\|iz cet'` |
| **shops** 🎰 | uplatna mesta kladionica (voter infra) | `data/geo/betting_geo.json` |

> Raspon = **geografska nadležnost**, ne dokaz pojedinačnog naređenja (fer play).

---

## 3. KLJUČNI NALAZ — komanda ≠ izvršenje

**Od 156 koordinatora: 139 se vidi u grafu (rade neke akcije), ali 0 su grafni
centroidi, i samo 4 izdaju SS direktive.**

U grafu postoji **16 centroida** (od 3.799 operatera sa koordinacijom) — ali
**nijedan od njih nema formalnu koordinatorsku titulu**. Obrnuto, formalni
koordinatori nisu mrežni habovi.

**Zaključak:** *formalna komanda* (koordinatorska pozicija, geografska nadležnost)
i *izvršna moć* (centralnost u mreži akcija) su **razdvojeni slojevi**. Ovo je
dosledno nalazu o direktivama: i izdavači „super specijala" su uglavnom van jakog
grafa (`org≈0`) — administrativni sloj koji prosleđuje smernice, odvojen od
operativnih habova. Vidi [`analiza_direktiva.md`](analiza_direktiva.md).

### Raspon po regionima

| Region | operateri | centroidi | komanda | SS | 🎰 | region-koordinator |
|---|---:|---:|---:|---:|---:|---|
| Vojvodina | 2.973 | 5 | 51 | 8 | 120 | — |
| Zapadna Srbija | 1.996 | 6 | 41 | 8 | 37 | Radmila Isaković |
| Centralna Srbija | 1.713 | 2 | 45 | 4 | 39 | Marijana Karajović |
| Južna Srbija | 1.297 | 1 | 15 | 4 | 11 | Ivan Jovanović |
| Grad Beograd | 872 | 2 | 17 | 3 | 45 | Lana Lana |
| Istočna Srbija | 457 | 0 | 23 | 3 | 14 | Tanja Dimić |

Centroidi i kladionice (🎰) su koncentrisani u Vojvodini i Beogradu; komandni sloj
(ko zadaje) je ravnomernije raspoređen.

---

## 4. Lanac (koliko podaci nose)

```
REGION koord  →  OKRUG koord  →  OPŠTINA koord   ‖  (odvojeno)  GRAFNI CENTROID
5                15               136                            16 habova
region_koordinator / okrug_koordinator / opstina_koordinator    tw/cc_organizer
✔ formalna geografska komanda                                    ✔ mrežna izvršna moć
                        presek ova dva sloja = 0 (!)
```

Sve brojke reproducibilne: `./venv/bin/python src/analysis/coordinators.py`.
Sledeće (dublje): kaskada izdavač SS → okružni/opštinski koordinator → operater
kroz vreme (ko kome prosleđuje smernicu).
