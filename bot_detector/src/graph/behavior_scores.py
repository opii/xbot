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

    print("Gradnja progress.target_bursts (nalet u prvih 10 min) ...", flush=True)
    cur.execute("DROP TABLE IF EXISTS target_bursts")
    cur.execute("""
        CREATE TABLE target_bursts AS
        WITH ft AS (
            SELECT tuka_twitter_id tid, tuka_korisnik_id op,
                   min(tuka_vreme::timestamp) t
            FROM arhiva_twitter_unos_korisnici_akcije GROUP BY 1, 2),
        agg AS (SELECT tid, min(t) t0, max(t) t1, count(*) nops
                FROM ft GROUP BY tid HAVING count(*) >= 8),
        burst AS (
            SELECT a.tid, a.nops, a.t0, a.t1,
                   count(*) FILTER (WHERE f.t <= a.t0 + interval '10 minutes') peak10
            FROM ft f JOIN agg a USING(tid)
            GROUP BY a.tid, a.nops, a.t0, a.t1)
        SELECT b.tid,
               lower(split_part(split_part(t.tu_link_tvita, '.com/', 2), '/', 1)) handle,
               b.nops, b.peak10,
               round(extract(epoch FROM (b.t1 - b.t0)) / 60.0)::int span_min,
               round(b.peak10::numeric / b.nops, 3) synchrony
        FROM burst b JOIN arhiva_twitter_unos t ON t.tu_id = b.tid
    """)
    cur.execute("CREATE INDEX ix_target_bursts_tid ON target_bursts(tid)")
    pg.commit()
    cur.execute("SELECT count(*) FROM target_bursts")
    print(f"  kampanja (>=8 operatera): {cur.fetchone()[0]:,}", flush=True)

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

    print("Računanje lead-lag skora (ko prvi reaguje) ...", flush=True)
    # Po meti (5..500 operatera) rangiramo po vremenu prve akcije; lead = prosek
    # udela ko-aktera koje je operater PRETEKAO. 1 = stalno prvi, 0 = poslednji.
    cur.execute("""
        WITH ft AS (
            SELECT tuka_twitter_id tid, tuka_korisnik_id op, min(tuka_vreme) t
            FROM arhiva_twitter_unos_korisnici_akcije GROUP BY 1, 2),
        cnt AS (SELECT tid, count(*) nops FROM ft GROUP BY 1
                HAVING count(*) BETWEEN 5 AND 500),
        rk AS (SELECT f.op, c.nops,
                      rank() OVER (PARTITION BY f.tid ORDER BY f.t) rnk
               FROM ft f JOIN cnt c USING(tid))
        SELECT op, round(avg((nops - rnk)::numeric / (nops - 1)), 4), count(*)
        FROM rk GROUP BY op HAVING count(*) >= 20
    """)
    lead_rows = [{"id": op, "lead": float(lead), "ln": n}
                 for op, lead, n in cur.fetchall()]

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
        s.run("MATCH (o:Operator) SET o.auto_score=0, o.dup_ratio=0, o.lead_score=0, o.lead_n=0")
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
        for i in range(0, len(lead_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id}) SET o.lead_score=r.lead, o.lead_n=r.ln
            """, rows=lead_rows[i:i + 5000])
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
