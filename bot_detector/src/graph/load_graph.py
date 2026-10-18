#!/usr/bin/env python3
"""
Gradi operatersku mrežu u Neo4j iz Postgres šeme `progress`.

Model (operater-centrično):
  (:Operator {id, ime, region, okrug, opstina,
              actions, likes, rts, replies, quotes,
              targets, accounts, first_action, last_action})
  (:Account  {id, handle, link, deleted, verified})
  (:Operator)-[:CONTROLS]->(:Account)
  (:Operator)-[:CO_ACTED {shared, targets}]-(:Operator)   // deljene mete

Mete (AMPLIFIES) se NE učitavaju ovde — ima ih 9.4M parova; API ih servira
uživo iz Postgresa pri razlistavanju čvora.

Pokretanje:
    cd bot_detector
    ./venv/bin/python src/graph/load_graph.py
Opcije: --coact-ceil 30 --coact-min 4   (pragovi ko-amplifikacije)
"""
import argparse
import os
import time

import psycopg2
from neo4j import GraphDatabase

# Konekcija je parametrizovana env promenljivama da bi radila i lokalno
# (localhost) i iz docker compose init servisa (hostovi postgres/neo4j).
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


def batched(driver, cypher, rows, size=5000, param="rows"):
    total = 0
    with driver.session() as s:
        for i in range(0, len(rows), size):
            chunk = rows[i:i + size]
            s.run(cypher, {param: chunk})
            total += len(chunk)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coact-ceil", type=int, default=30,
                    help="meta se broji samo ako je diraju 2..CEIL operatera")
    ap.add_argument("--coact-min", type=int, default=4,
                    help="minimum deljenih meta za CO_ACTED vezu")
    ap.add_argument("--cocom-ceil", type=int, default=20,
                    help="vest se broji samo ako je komentariše 2..CEIL operatera")
    ap.add_argument("--cocom-min", type=int, default=5,
                    help="minimum deljenih vesti za CO_COMMENTED vezu")
    args = ap.parse_args()

    pg = psycopg2.connect(PG_DSN)
    cur = pg.cursor()
    cur.execute("SET search_path TO progress")
    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    t0 = time.time()

    # --- 0. Čišćenje + constraints ---
    print("Čišćenje starog grafa ...", flush=True)
    with drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
        s.run("CREATE CONSTRAINT op_id IF NOT EXISTS "
              "FOR (o:Operator) REQUIRE o.id IS UNIQUE")
        s.run("CREATE CONSTRAINT acc_id IF NOT EXISTS "
              "FOR (a:Account) REQUIRE a.id IS UNIQUE")
        s.run("CREATE INDEX acc_handle IF NOT EXISTS FOR (a:Account) ON (a.handle)")
        s.run("CREATE INDEX op_ime IF NOT EXISTS FOR (o:Operator) ON (o.ime)")

    # --- 1. Operateri koji su izvršavali akcije, sa agregatima + metapodacima ---
    print("Učitavanje operatera ...", flush=True)
    cur.execute("""
        WITH agg AS (
            SELECT tuka_korisnik_id op,
                   count(*)                                      actions,
                   count(*) FILTER (WHERE tuka_akcija=0)         likes,
                   count(*) FILTER (WHERE tuka_akcija=1)         rts,
                   count(*) FILTER (WHERE tuka_akcija=2)         replies,
                   count(*) FILTER (WHERE tuka_akcija=3)         quotes,
                   count(DISTINCT tuka_twitter_id)               targets,
                   count(DISTINCT tuka_nalog_id)                 accounts_used,
                   min(tuka_vreme)                               first_action,
                   max(tuka_vreme)                               last_action
            FROM arhiva_twitter_unos_korisnici_akcije
            GROUP BY 1
        )
        SELECT a.op,
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),''),
               r.r_naziv, o.o_naziv, op.op_naziv,
               a.actions, a.likes, a.rts, a.replies, a.quotes,
               a.targets, a.accounts_used, a.first_action, a.last_action
        FROM agg a
        LEFT JOIN korisnici k ON k.k_id = a.op
        LEFT JOIN region  r  ON r.r_id  = k.k_region
        LEFT JOIN okrug   o  ON o.o_id  = k.k_okrug
        LEFT JOIN opstina op ON op.op_id = k.k_opstina
    """)
    ops = [dict(zip(
        ("id", "ime", "region", "okrug", "opstina", "actions", "likes",
         "rts", "replies", "quotes", "targets", "accounts", "first", "last"),
        row)) for row in cur.fetchall()]
    n = batched(drv, """
        UNWIND $rows AS r
        MERGE (o:Operator {id: r.id})
        SET o.ime=r.ime, o.region=r.region, o.okrug=r.okrug, o.opstina=r.opstina,
            o.actions=r.actions, o.likes=r.likes, o.rts=r.rts,
            o.replies=r.replies, o.quotes=r.quotes, o.targets=r.targets,
            o.accounts=r.accounts, o.first_action=r.first, o.last_action=r.last
    """, ops)
    print(f"  operatera: {n:,}", flush=True)
    op_ids = tuple(o["id"] for o in ops)

    # --- 2. Nalozi tih operatera + CONTROLS ---
    print("Učitavanje naloga (CONTROLS) ...", flush=True)
    cur.execute("""
        SELECT ktn_id, ktn_korisnik_id,
               NULLIF(NULLIF(ktn_nalog_ime,''),'NULL'),
               NULLIF(NULLIF(ktn_link_naloga,''),'NULL'),
               coalesce(ktn_obrisano,0), coalesce(ktn_verifikovan,0)
        FROM korisnici_twitter_nalozi
        WHERE ktn_korisnik_id IN %s
    """, (op_ids,))
    accs = [dict(zip(("id", "op", "handle", "link", "deleted", "verified"), row))
            for row in cur.fetchall()]
    batched(drv, """
        UNWIND $rows AS r
        MERGE (a:Account {id: r.id})
        SET a.handle=r.handle, a.link=r.link,
            a.deleted=(r.deleted=1), a.verified=(r.verified=1)
        WITH a, r
        MATCH (o:Operator {id: r.op})
        MERGE (o)-[:CONTROLS]->(a)
    """, accs)
    print(f"  naloga: {len(accs):,}", flush=True)

    # --- 3. CO_ACTED (deljene diskriminativne mete) ---
    print(f"Računanje CO_ACTED (ceil={args.coact_ceil}, min={args.coact_min}) ...",
          flush=True)
    cur.execute(f"""
        WITH tgt AS (
            SELECT tuka_twitter_id tid
            FROM arhiva_twitter_unos_korisnici_akcije
            GROUP BY 1
            HAVING count(DISTINCT tuka_korisnik_id)
                   BETWEEN 2 AND {args.coact_ceil}
        ),
        ot AS (
            SELECT DISTINCT a.tuka_korisnik_id op, a.tuka_twitter_id tid
            FROM arhiva_twitter_unos_korisnici_akcije a
            JOIN tgt ON tgt.tid = a.tuka_twitter_id
        )
        SELECT x.op, y.op, count(*) shared
        FROM ot x JOIN ot y ON x.tid=y.tid AND x.op < y.op
        GROUP BY x.op, y.op
        HAVING count(*) >= {args.coact_min}
    """)
    co = [{"a": r[0], "b": r[1], "shared": r[2]} for r in cur.fetchall()]
    batched(drv, """
        UNWIND $rows AS r
        MATCH (a:Operator {id: r.a}), (b:Operator {id: r.b})
        MERGE (a)-[c:CO_ACTED]-(b)
        SET c.shared = r.shared
    """, co)
    print(f"  CO_ACTED veza: {len(co):,}", flush=True)

    # --- 3b. Popularnost meta (za diskriminativne spone u putanji) ---
    # Koliko RAZLIČITIH operatera dira svaki handle. Masovne mete (@sns_srbija)
    # imaju ogroman broj; retke spone mali.
    print("Gradnja progress.target_popularity ...", flush=True)
    cur.execute("DROP TABLE IF EXISTS target_popularity")
    cur.execute("""
        CREATE TABLE target_popularity AS
        SELECT lower(split_part(split_part(t.tu_link_tvita,'.com/',2),'/',1)) AS handle,
               count(DISTINCT a.tuka_korisnik_id) AS operators,
               count(*) AS actions
        FROM arhiva_twitter_unos_korisnici_akcije a
        JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
        GROUP BY 1
    """)
    cur.execute("CREATE INDEX ix_target_popularity_handle ON target_popularity(handle)")
    pg.commit()
    cur.execute("SELECT count(*) FROM target_popularity")
    print(f"  handle-ova: {cur.fetchone()[0]:,}", flush=True)

    # --- 5. Komentatori portala: Operator čvorovi + statistika + CO_COMMENTED ---
    # Komentatori su isti korisnici; proširujemo iste Operator čvorove.
    print("Učitavanje komentatora (statistika) ...", flush=True)
    cur.execute("""
        SELECT v.vkk_korisnik_id,
               count(*) AS comments,
               count(DISTINCT v.vkk_vest_id) AS news,
               mode() WITHIN GROUP (ORDER BY u.vu_portal) AS top_portal,
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),''),
               r.r_naziv, o.o_naziv, op.op_naziv
        FROM arhiva_vesti_korisnici_komentari v
        JOIN arhiva_vesti_unos u ON u.vu_id = v.vkk_vest_id
        LEFT JOIN korisnici k ON k.k_id = v.vkk_korisnik_id
        LEFT JOIN region  r  ON r.r_id  = k.k_region
        LEFT JOIN okrug   o  ON o.o_id  = k.k_okrug
        LEFT JOIN opstina op ON op.op_id = k.k_opstina
        WHERE v.vkk_simulacija = 0
        GROUP BY v.vkk_korisnik_id, k.k_ime, k.k_prezime, r.r_naziv, o.o_naziv, op.op_naziv
    """)
    commenters = [dict(zip(
        ("id", "comments", "news", "top_portal", "ime", "region", "okrug", "opstina"),
        row)) for row in cur.fetchall()]
    # MERGE: postojeće operatere dopuni komentar-statistikom; nove kreiraj.
    batched(drv, """
        UNWIND $rows AS r
        MERGE (o:Operator {id: r.id})
        SET o.comments=r.comments, o.comment_news=r.news, o.top_portal=r.top_portal
        FOREACH (_ IN CASE WHEN o.ime IS NULL THEN [1] ELSE [] END |
            SET o.ime=r.ime, o.region=r.region, o.okrug=r.okrug, o.opstina=r.opstina)
    """, commenters)
    print(f"  komentatora: {len(commenters):,}", flush=True)

    # Popularnost vesti (za diskriminativne spone u komentar-putanji)
    print("Gradnja progress.news_popularity ...", flush=True)
    cur.execute("DROP TABLE IF EXISTS news_popularity")
    cur.execute("""
        CREATE TABLE news_popularity AS
        SELECT vkk_vest_id AS vid,
               count(DISTINCT vkk_korisnik_id) AS operators
        FROM arhiva_vesti_korisnici_komentari
        WHERE vkk_simulacija = 0
        GROUP BY 1
    """)
    cur.execute("CREATE INDEX ix_news_popularity_vid ON news_popularity(vid)")
    pg.commit()

    print(f"Računanje CO_COMMENTED (ceil={args.cocom_ceil}, "
          f"min={args.cocom_min}) ...", flush=True)
    cur.execute(f"""
        WITH vest AS (
            SELECT vkk_vest_id vid FROM arhiva_vesti_korisnici_komentari
            WHERE vkk_simulacija = 0 GROUP BY 1
            HAVING count(DISTINCT vkk_korisnik_id) BETWEEN 2 AND {args.cocom_ceil}
        ),
        ov AS (
            SELECT DISTINCT v.vkk_korisnik_id op, v.vkk_vest_id vid
            FROM arhiva_vesti_korisnici_komentari v
            JOIN vest ON vest.vid = v.vkk_vest_id
            WHERE v.vkk_simulacija = 0
        )
        SELECT x.op, y.op, count(*) shared
        FROM ov x JOIN ov y ON x.vid=y.vid AND x.op < y.op
        GROUP BY x.op, y.op HAVING count(*) >= {args.cocom_min}
    """)
    cc = [{"a": r[0], "b": r[1], "shared": r[2]} for r in cur.fetchall()]
    batched(drv, """
        UNWIND $rows AS r
        MATCH (a:Operator {id: r.a}), (b:Operator {id: r.b})
        MERGE (a)-[c:CO_COMMENTED]-(b)
        SET c.shared = r.shared
    """, cc)
    print(f"  CO_COMMENTED veza: {len(cc):,}", flush=True)

    # --- 6. Stepeni po operateru (za bojenje/sortiranje po sloju) ---
    print("Računanje stepena (co_degree, cc_degree) ...", flush=True)
    with drv.session() as s:
        s.run("""
            MATCH (o:Operator) OPTIONAL MATCH (o)-[c:CO_ACTED]-()
            WITH o, count(c) AS deg SET o.co_degree = deg
        """)
        s.run("""
            MATCH (o:Operator) OPTIONAL MATCH (o)-[c:CO_COMMENTED]-()
            WITH o, count(c) AS deg SET o.cc_degree = deg
        """)

    # --- 7. Detekcija organizatora (centroida) po sloju ---
    print("\nDetekcija organizatora (centroida) ...", flush=True)
    try:
        from detect_organizers import process as detect_process, LAYERS
        for prefix, rel in LAYERS.items():
            detect_process(drv, prefix, rel, 5, 95)
    except Exception as e:  # noqa: BLE001
        print(f"  [upozorenje] detekcija preskočena: {e}", flush=True)

    # --- 8. Bihevioralni skorovi (automatizacija) ---
    print("\nBihevioralni skorovi (automatizacija) ...", flush=True)
    try:
        from behavior_scores import run as behavior_run
        behavior_run(drv)
    except Exception as e:  # noqa: BLE001
        print(f"  [upozorenje] skorovi preskočeni: {e}", flush=True)

    with drv.session() as s:
        nn = s.run("MATCH (n) RETURN count(n)").single()[0]
        ne = s.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
    print(f"\n[OK] Neo4j graf: {nn:,} čvorova, {ne:,} veza "
          f"({time.time()-t0:.1f}s)", flush=True)
    drv.close(); pg.close()


if __name__ == "__main__":
    main()
