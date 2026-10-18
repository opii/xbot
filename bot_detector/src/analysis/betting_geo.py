#!/usr/bin/env python3
"""
Faza B: kladionice (voter_racunari.vr_naziv_ss) -> opština, i preklapanje sa
centroidima/organizatorima u grafu.

Imena mašina su uplatna mesta kladionica (Scooorebet/Casino/Joker/Maxi). RS imena
često nose grad/opštinu („Sombor 3", „Pozarevac Centar"); mapiramo ih na opštinu
(normalizacija dijakritika + prefiks + aliasi za kvartove). Strani/regionalni
(Afrika, CG, BiH) idu u poseban bucket. Zatim gledamo koje opštine sa kladionicama
imaju jake organizatore/centroide (tw_org/cc_org) — geografsko preklapanje.

Pokretanje:  ./venv/bin/python src/analysis/betting_geo.py
"""
import json
import os
from collections import Counter

import psycopg2
from neo4j import GraphDatabase

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO = ("bolt://localhost:7687", ("neo4j", "bot_password"))
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "betting_geo.json")

# kvartovi / lokacije -> opština
ALIAS = {
    "borca": "Beograd-Palilula", "lacarak": "Sremska Mitrovica",
    "sivac": "Kula", "enjub": "Beograd-Novi Beograd", "roma": "Beograd-Novi Beograd",
    "belville": "Beograd-Novi Beograd", "zemun": "Beograd-Zemun",
    "vozdovac": "Beograd-Voždovac", "banovo brdo": "Beograd-Čukarica",
}


def norm(s):
    s = (s or "").lower()
    for a, b in (("ć", "c"), ("č", "c"), ("š", "s"), ("ž", "z"), ("đ", "dj")):
        s = s.replace(a, b)
    return s


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")
    cur.execute("SELECT op_naziv FROM opstina")
    ops = [r[0] for r in cur.fetchall()]
    # mapa normalizovano -> originalno ime opštine, duže prvo (da „Bačka Palanka" pre „Bač")
    opn = sorted(((norm(o), o) for o in ops), key=lambda x: -len(x[0]))

    def match(name):
        n = norm(name)
        for ali, op in ALIAS.items():
            if n.startswith(ali):
                return op
        for non, oo in opn:
            if n == non or n.startswith(non + " ") or n.startswith(non + str(0)) \
               or (n.startswith(non) and len(n) > len(non) and n[len(non)].isdigit()):
                return oo
        # jednoreč: prvi token == opština
        first = n.split()[0] if n.split() else ""
        for non, oo in opn:
            if first == non:
                return oo
        return None

    cur.execute("SELECT vr_naziv_ss, vr_srbija FROM voter_racunari WHERE vr_naziv_ss <> ''")
    rows = cur.fetchall()
    by_op = Counter()         # opština -> broj mašina
    unmatched = Counter()
    total, matched = 0, 0
    for name, srb in rows:
        total += 1
        op = match(name)
        if op:
            by_op[op] += 1; matched += 1
        else:
            unmatched[name] += 1
    print(f"kladionica (mašina): {total:,} · mapirano na opštinu: {matched:,} "
          f"({100*matched/total:.0f}%)", flush=True)
    print("\nTOP OPŠTINE sa kladionicama (mašina):")
    for op, n in by_op.most_common(15):
        print(f"  {op}: {n}")

    # preklapanje sa centroidima/organizatorima
    drv = GraphDatabase.driver(*NEO[:1], auth=NEO[1])
    overlap = []
    with drv.session() as s:
        for op, n in by_op.most_common(30):
            r = s.run("""
                MATCH (o:Operator {opstina:$op})
                RETURN count(o) AS ops,
                       sum(CASE WHEN o.tw_organizer OR o.cc_organizer THEN 1 ELSE 0 END) AS centroids,
                       max(o.tw_org) AS max_tw, max(o.cc_org) AS max_cc
            """, op=op).single()
            overlap.append({"opstina": op, "shops": n, "operators": r["ops"],
                            "centroids": r["centroids"] or 0,
                            "max_tw_org": round(r["max_tw"] or 0, 3),
                            "max_cc_org": round(r["max_cc"] or 0, 3)})
    drv.close()
    print("\nPREKLAPANJE kladionice ↔ centroidi (opština · kladionica · operatera · centroida · max org):")
    for o in overlap[:15]:
        print(f"  {o['opstina']:<24} shops={o['shops']:<3} op={o['operators']:<4} "
              f"centroidi={o['centroids']} maxOrg={max(o['max_tw_org'], o['max_cc_org'])}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"total": total, "matched": matched,
                   "by_opstina": dict(by_op.most_common()),
                   "unmatched_top": dict(unmatched.most_common(40)),
                   "overlap": overlap}, fh, ensure_ascii=False, indent=2)
    print(f"\n[OK] {OUT}")


if __name__ == "__main__":
    main()
