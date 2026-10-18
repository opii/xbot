#!/usr/bin/env python3
"""
Računa bihevioralni skor automatizacije po operateru i upisuje ga u Neo4j.

auto_score (0..1, više = sličnije automatizaciji) = kombinacija tri signala:
  - night_ratio   : udeo akcija 00–05h (skripte rade i noću)
  - hour_entropy  : ravnomernost rasporeda po satu (ravnomerno 24/7 = bot-like)
  - short_lat_frac: udeo akcija izvršenih < 2 min od objave zadatka

Pokretanje:  ./venv/bin/python src/graph/behavior_scores.py
Poziva se i automatski na kraju load_graph.py.
"""
import math
import os

import psycopg2
from neo4j import GraphDatabase

PG_DSN = os.environ.get(
    "PROGRESS_PG_DSN",
    "host={h} dbname={d} user={u} password={p}".format(
        h=os.environ.get("PG_HOST", "localhost"),
        d=os.environ.get("PG_DB", "bot_detector_db"),
        u=os.environ.get("PG_USER", "bot_user"),
        p=os.environ.get("PG_PASSWORD", "bot_password"),
    ),
)
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.environ.get("NEO4J_USER", "neo4j"),
              os.environ.get("NEO4J_PASSWORD", "bot_password"))

# Težine signala u kompozitu
W_NIGHT, W_ENTROPY, W_SHORTLAT = 0.4, 0.3, 0.3
SHORT_LAT_SECONDS = 120


def run(drv=None):
    pg = psycopg2.connect(PG_DSN)
    cur = pg.cursor()
    cur.execute("SET search_path TO progress")
    own = drv is None
    if own:
        drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    print("Računanje ritma po satu (entropija, noćna aktivnost) ...", flush=True)
    cur.execute("""
        SELECT tuka_korisnik_id, substr(tuka_vreme, 12, 2) AS hh, count(*)
        FROM arhiva_twitter_unos_korisnici_akcije
        GROUP BY 1, 2
    """)
    hours = {}  # op -> [24]
    for op, hh, c in cur.fetchall():
        if hh is None or not hh.isdigit():
            continue
        hours.setdefault(op, [0] * 24)[int(hh)] = c

    print("Računanje udela kratkih latencija ...", flush=True)
    cur.execute(f"""
        SELECT a.tuka_korisnik_id,
               count(*) AS n,
               count(*) FILTER (WHERE
                   extract(epoch FROM (a.tuka_vreme::timestamp - t.tu_kreirano_vreme::timestamp))
                   < {SHORT_LAT_SECONDS}) AS short_n
        FROM arhiva_twitter_unos_korisnici_akcije a
        JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
        WHERE a.tuka_vreme > t.tu_kreirano_vreme
        GROUP BY 1
    """)
    shortlat = {op: (short / n if n else 0.0) for op, n, short in cur.fetchall()}

    ln24 = math.log(24)
    rows = []
    for op, hrs in hours.items():
        total = sum(hrs) or 1
        night = sum(hrs[0:6]) / total
        ent = 0.0
        for c in hrs:
            if c:
                p = c / total
                ent -= p * math.log(p)
        ent /= ln24  # 0..1 (1 = ravnomerno)
        sl = shortlat.get(op, 0.0)
        # prigušenje po pouzdanosti: malo akcija = nepouzdana procena -> ka 0
        conf = min(1.0, total / 50.0)
        score = (W_NIGHT * night + W_ENTROPY * ent + W_SHORTLAT * sl) * conf
        rows.append({"id": op, "auto": round(score, 4), "night": round(night, 4),
                     "ent": round(ent, 4), "sl": round(sl, 4)})

    print("Računanje udela duplikata komentara ...", flush=True)
    cur.execute("""
        SELECT vkk_korisnik_id, count(*), count(DISTINCT vkk_komentar)
        FROM arhiva_vesti_korisnici_komentari
        WHERE vkk_simulacija = 0 AND vkk_komentar <> ''
        GROUP BY 1
    """)
    dup_rows = [{"id": op, "dup": round(1 - (dist / tot), 4) if tot else 0.0}
                for op, tot, dist in cur.fetchall()]

    print(f"Upis auto_score za {len(rows):,} operatera ...", flush=True)
    with drv.session() as s:
        s.run("MATCH (o:Operator) SET o.auto_score = 0, o.dup_ratio = 0")
        for i in range(0, len(rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id})
                SET o.auto_score=r.auto, o.night_ratio=r.night,
                    o.hour_entropy=r.ent, o.short_lat_frac=r.sl
            """, rows=rows[i:i + 5000])
        for i in range(0, len(dup_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id}) SET o.dup_ratio = r.dup
            """, rows=dup_rows[i:i + 5000])
        top = s.run("MATCH (o:Operator) WHERE o.auto_score > 0 "
                    "RETURN o.ime AS ime, o.auto_score AS a "
                    "ORDER BY a DESC LIMIT 5").data()
    for r in top:
        print(f"    automatizacija: {r['ime']}  auto={r['a']}", flush=True)
    print("[OK] Bihevioralni skorovi upisani.", flush=True)

    pg.close()
    if own:
        drv.close()


if __name__ == "__main__":
    run()
