#!/usr/bin/env python3
"""
Zadatak 1: korporativni/vlasnički profil uplatnih mesta — DATA-BACKED TRAGOVI.

VAŽNO (fer play): baza NE sadrži vlasničke/registarske podatke. Ovaj modul izvlači
SAMO ono što baza ima (brendovi, lokacije, broj mašina, Srbija/strano) kao
INVESTIGATIVNE MeTE, i upisuje ih u JSON. Rezolucija vlasništva (koja privredna
društva drže mesta, ko su osnivači) radi se protiv PRIMARNIH REGISTARA (APR,
Uprava za igre na sreću) — to NIJE u ovim podacima i NE sme se izmišljati.
Metodologija i (javno proverljiv) kontekst: docs/vlasnicki_profil_kladionica.md.

Izlaz: data/geo/betting_corporate.json
Pokretanje:  ./venv/bin/python src/analysis/betting_corporate.py
"""
import json
import os
import re
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "betting_corporate.json")

# Brend-tokeni koje tražimo u imenu mašine (vr_naziv_ss). Prisustvo tokena je
# LEAD (naziv liči na brend), ne dokaz vlasništva.
BRANDS = {
    "Scooorebet": r"scoooreb", "Maxi": r"\bmaxi\b", "Joker": r"\bjoker\b",
    "Casino": r"casino", "Soccerbet": r"soccerb", "Admiral": r"admiral",
    "Mozzart": r"mozzart", "Meridian": r"meridian", "Balkanbet": r"balkanbet",
    "Volcano": r"volcano", "Roma": r"\broma\b",
}


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    rows = q("SELECT vr_naziv_ss, vr_srbija, count(*) FROM voter_racunari "
             "WHERE vr_naziv_ss <> '' GROUP BY 1,2")
    serbia = sum(n for _, srb, n in rows if srb == 1)
    foreign = sum(n for _, srb, n in rows if srb == 0)

    brand = {}       # brend -> {total, serbia, foreign}
    for naz, srb, n in rows:
        low = naz.lower()
        for b, rx in BRANDS.items():
            if re.search(rx, low):
                d = brand.setdefault(b, {"brand": b, "total": 0, "serbia": 0, "foreign": 0})
                d["total"] += n
                d["serbia" if srb == 1 else "foreign"] += n
                break
    brands = sorted(brand.values(), key=lambda d: d["total"], reverse=True)
    branded = sum(d["total"] for d in brands)

    def locs(srb, limit=40):
        return [{"naziv": naz, "machines": n} for naz, n in q(
            "SELECT vr_naziv_ss, count(*) FROM voter_racunari WHERE vr_srbija=%s "
            "AND vr_naziv_ss<>'' GROUP BY 1 ORDER BY 2 DESC LIMIT %s", (srb, limit))]

    serbia_locs = locs(1)
    foreign_locs = locs(0)

    # klijentske verzije (dokaz instaliranog softvera)
    versions = [{"ver": v, "n": n} for v, n in q(
        "SELECT vr_verzija, count(*) FROM voter_racunari WHERE vr_verzija<>'' "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT 10")]

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "machines_total": serbia + foreign,
        "machines_serbia": serbia, "machines_foreign": foreign,
        "brands": brands, "branded_machines": branded,
        "serbia_locations": serbia_locs, "foreign_locations": foreign_locs,
        "client_versions": versions,
        "investigation_targets": {
            "registries": [
                {"name": "APR — Agencija za privredne registre",
                 "url": "https://www.apr.gov.rs/", "use": "privredna društva, osnivači, sedište"},
                {"name": "Uprava za igre na sreću (Ministarstvo finansija RS)",
                 "url": "https://uis.gov.rs/", "use": "licence/koncesije za igre na sreću, spisak uplatnih mesta"},
            ],
            "method": ("Uparivanje: naziv mašine (vr_naziv_ss) → adresa uplatnog mesta "
                       "→ APR/UIS registar → privredno društvo i osnivači. Brend u "
                       "Africi (Scooorebet/Maxi/Joker) → tražiti povezana lica preko "
                       "franšiznih/ugovornih veza. SVE zahteva primarni izvor."),
        },
        "fair_play": ("Baza NE sadrži vlasništvo. Brend/lokacija su TRAGOVI, ne dokaz. "
                      "Javne pretrage NE potvrđuju vezu brenda „Scooorebet“ (Afrika) sa "
                      "bilo kojim srpskim društvom — NE izjednačavati sa „Soccerbet“ "
                      "(Phuket d.o.o.) bez primarnog izvora. Ne imenovati pojedince kao "
                      "vlasnike/krivce bez proverljive dokumentacije."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Mašina: {serbia + foreign} (Srbija {serbia} / strano {foreign})")
    print(f"Sa prepoznatim brendom: {branded}")
    for d in brands:
        print(f"  {d['brand']:<12} {d['total']:>4}  (Srbija {d['serbia']} / strano {d['foreign']})")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
