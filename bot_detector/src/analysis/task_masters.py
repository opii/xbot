#!/usr/bin/env python3
"""
Faza A: ko komanduje — kreatori zadataka za portale (vu_korisnik_id) i njihove
koordinatorske uloge.

Samo ~135 ljudi kreira SVE zadatke za portale (vesti). Spajamo ih sa:
  - korisnici (ime, pozicija, okrug/opština)
  - koordinatorske tabele (koordinatori_korisnici flags, okrug/opstina_koordinator)
i rangiramo po obimu. Takođe gledamo preklapanje sa Operator čvorovima (da li su
task-masteri i sami jaki u grafu / centroidi).

Pokretanje:  ./venv/bin/python src/analysis/task_masters.py
"""
import json
import os

import psycopg2
from neo4j import GraphDatabase

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO = ("bolt://localhost:7687", ("neo4j", "bot_password"))
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "task_masters.json")


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")
    # kreatori zadataka za vesti + obim + portali + top smernica
    cur.execute("""
        SELECT v.vu_korisnik_id,
               count(*) AS tasks,
               count(DISTINCT v.vu_portal) AS portals,
               count(*) FILTER (WHERE v.vu_smernica ~* 'max') AS smer_max,
               count(*) FILTER (WHERE v.vu_smernica ~ '[0-9]') AS smer_broj,
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'') AS ime,
               k.k_pozicija, o.o_naziv AS okrug, op.op_naziv AS opstina,
               kk.okrug_koordinator, kk.opstina_koordinator, kk.region_koordinator
        FROM arhiva_vesti_unos v
        LEFT JOIN korisnici k ON k.k_id = v.vu_korisnik_id
        LEFT JOIN okrug  o  ON o.o_id  = k.k_okrug
        LEFT JOIN opstina op ON op.op_id = k.k_opstina
        LEFT JOIN koordinatori_korisnici kk ON kk.korisnik_id = v.vu_korisnik_id
        GROUP BY v.vu_korisnik_id, k.k_ime, k.k_prezime, k.k_pozicija,
                 o.o_naziv, op.op_naziv, kk.okrug_koordinator,
                 kk.opstina_koordinator, kk.region_koordinator
        ORDER BY tasks DESC
    """)
    cols = ("id", "tasks", "portals", "smer_max", "smer_broj", "ime", "pozicija",
            "okrug", "opstina", "ok_koord", "op_koord", "reg_koord")
    masters = [dict(zip(cols, r)) for r in cur.fetchall()]
    print(f"kreatora zadataka za portale: {len(masters)}", flush=True)

    # koordinatorski status iz namenskih tabela
    cur.execute("SELECT ok_korisnik_id FROM okrug_koordinator"); okset = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT ok_korisnik_id FROM opstina_koordinator"); opset = {r[0] for r in cur.fetchall()}

    # preklapanje sa grafom (da li je task-master i jak operater/centroid)
    drv = GraphDatabase.driver(*NEO[:1], auth=NEO[1])
    with drv.session() as s:
        for m in masters:
            r = s.run("MATCH (o:Operator {id:$id}) RETURN o.tw_org AS tw, o.cc_org AS cc, "
                      "o.tw_organizer AS two, o.cc_organizer AS cco, o.actions AS act",
                      id=m["id"]).single()
            m["in_graph"] = r is not None
            m["max_org"] = round(max((r["tw"] or 0), (r["cc"] or 0)), 3) if r else 0
            m["centroid"] = bool(r and (r["two"] or r["cco"]))
            m["okrug_koord_tbl"] = m["id"] in okset
            m["opstina_koord_tbl"] = m["id"] in opset
    drv.close()

    coord = sum(1 for m in masters if m["ok_koord"] or m["op_koord"]
                or m["reg_koord"] or m["okrug_koord_tbl"] or m["opstina_koord_tbl"])
    centroids = sum(1 for m in masters if m["centroid"])
    print(f"  od toga koordinatori (bilo koji nivo): {coord}", flush=True)
    print(f"  od toga centroidi u grafu: {centroids}", flush=True)
    print("\nTOP TASK-MASTERI (kreator · zadataka · uloga · okrug · maxOrg):")
    for m in masters[:15]:
        role = []
        if m["ok_koord"] or m["okrug_koord_tbl"]:
            role.append("okrug-koord")
        if m["op_koord"] or m["opstina_koord_tbl"]:
            role.append("opština-koord")
        if m["reg_koord"]:
            role.append("region-koord")
        if m["centroid"]:
            role.append("CENTROID")
        print(f"  {(m['ime'] or m['id']):<24} {m['tasks']:>6} · "
              f"{','.join(role) or '—':<28} · {m['okrug'] or '?':<18} · org={m['max_org']}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"count": len(masters), "coordinators": coord,
                   "centroids": centroids, "masters": masters[:60]},
                  fh, ensure_ascii=False, indent=2)
    print(f"\n[OK] {OUT}")


if __name__ == "__main__":
    main()
