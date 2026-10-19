"""
Cacix — API za graf-explorer povezanih bot-naloga.

Operaterska mreža (Operator, Account; CONTROLS, CO_ACTED) živi u Neo4j.
Amplifikacija (operater -> meta) se računa uživo iz Postgres šeme `progress`.
Node id šema za frontend: 'op:<id>', 'acc:<id>', 'tgt:<handle>'.
"""
import json
import math
import os
from datetime import datetime

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.pool import ThreadedConnectionPool
from neo4j import GraphDatabase

PG_DSN = os.environ.get(
    "PROGRESS_PG_DSN",
    "host={h} dbname={d} user={u} password={p} options='-c search_path=progress'".format(
        h=os.environ.get("PG_HOST", "localhost"),
        d=os.environ.get("PG_DB", "bot_detector_db"),
        u=os.environ.get("PG_USER", "bot_user"),
        p=os.environ.get("PG_PASSWORD", "bot_password"),
    ),
)
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.environ.get("NEO4J_USER", "neo4j"),
              os.environ.get("NEO4J_PASSWORD", "bot_password"))

app = FastAPI(title="Cacix Graph Explorer")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

pg_pool = ThreadedConnectionPool(1, 8, dsn=PG_DSN)
driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

HANDLE_SQL = "lower(split_part(split_part(t.tu_link_tvita,'.com/',2),'/',1))"


def pg(query, params=()):
    conn = pg_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        pg_pool.putconn(conn)


def time_clause(frm, to):
    """Vraća (sql_fragment, params) za opcioni vremenski prozor nad tuka_vreme."""
    frag, params = "", []
    if frm:
        frag += " AND a.tuka_vreme >= %s"; params.append(frm)
    if to:
        frag += " AND a.tuka_vreme <= %s"; params.append(to + " 23:59:59" if len(to) == 10 else to)
    return frag, params


def op_targets(op_id, limit, frm=None, to=None):
    """Mete koje operater najviše pumpa (Postgres), uz opcioni vremenski prozor."""
    tc, tp = time_clause(frm, to)
    rows = pg(f"""
        SELECT {HANDLE_SQL} AS handle, count(*) AS actions,
               count(*) FILTER (WHERE a.tuka_akcija=1) AS rts
        FROM arhiva_twitter_unos_korisnici_akcije a
        JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
        WHERE a.tuka_korisnik_id = %s{tc}
        GROUP BY 1 ORDER BY actions DESC LIMIT %s
    """, (op_id, *tp, limit))
    return [{"handle": h, "actions": a, "rts": r} for h, a, r in rows if h]


_PLATFORMS = [("Twitter", "korisnici_twitter_nalozi"), ("Instagram", "korisnici_instagram_nalozi"),
              ("TikTok", "korisnici_tiktok_nalozi"), ("Facebook", "korisnici_facebook_nalozi"),
              ("Threads", "korisnici_threads_nalozi"), ("Reddit", "korisnici_reddit_nalozi")]


def _platform_cols():
    out = {}
    for label, tbl in _PLATFORMS:
        r = pg("""SELECT column_name FROM information_schema.columns
                  WHERE table_schema='progress' AND table_name=%s
                  AND column_name ILIKE '%%korisnik_id' LIMIT 1""", (tbl,))
        if r:
            out[label] = (tbl, r[0][0])
    return out


PLATFORM_COLS = _platform_cols()


def op_layers(op_id):
    """Operativni slojevi za profil: taktičke grupe, F12 nadzor, uređaji, platforme."""
    groups = [r[0] for r in pg("""SELECT g.kg_naziv FROM korisnici_grupe_aktivisti ga
        JOIN korisnici_grupe g ON g.kg_id = ga.kga_grupa_id
        WHERE ga.kga_aktivista_id = %s AND g.kg_naziv IS NOT NULL
        ORDER BY g.kg_naziv""", (op_id,))]
    f12 = pg("SELECT count(*) FROM otvoren_inspector WHERE oi_korisnik_id = %s", (op_id,))[0][0]
    dev = pg("""SELECT count(*), mode() WITHIN GROUP (ORDER BY ku_operativni_sistem)
                FROM korisnici_uredjaji WHERE ku_korisnik_id = %s""", (op_id,))[0]
    platforms = []
    for label, (tbl, col) in PLATFORM_COLS.items():
        if pg(f"SELECT count(*) FROM {tbl} WHERE {col} = %s", (op_id,))[0][0]:
            platforms.append(label)
    return {
        "tactical_groups": groups,
        "f12_count": int(f12 or 0),
        "devices": {"total": int(dev[0]), "os": dev[1]} if dev and dev[0] else None,
        "platforms": platforms,
    }


def op_points(op_id):
    """Partijski bodovi operatera (izvestaj_dnevni): ukupno + razbijeno po akciji."""
    rows = pg("""SELECT sum(iz_ukupno_bodovi), sum(iz_twitter_quote), sum(iz_twitter_reply),
                        sum(iz_twitter_like), sum(iz_twitter_retweet),
                        sum(iz_komentari_objavljeni), count(DISTINCT iz_datum),
                        max(iz_ukupno_bodovi)
                 FROM izvestaj_dnevni WHERE iz_korisnik_id = %s""", (op_id,))
    if not rows or rows[0][0] is None:
        return None
    r = rows[0]
    return {"total": int(r[0] or 0), "quote": int(r[1] or 0), "reply": int(r[2] or 0),
            "like": int(r[3] or 0), "retweet": int(r[4] or 0),
            "komentari": int(r[5] or 0), "active_days": int(r[6] or 0),
            "best_day": round(float(r[7] or 0), 1)}


def op_node(rec):
    return {
        "id": f"op:{rec['id']}", "type": "operator",
        "label": rec.get("ime") or f"Operater #{rec['id']}",
        "actions": rec.get("actions"), "accounts": rec.get("accounts"),
        "targets": rec.get("targets"), "region": rec.get("region"),
        "okrug": rec.get("okrug"), "opstina": rec.get("opstina"),
        "rts": rec.get("rts"), "likes": rec.get("likes"),
        "replies": rec.get("replies"), "quotes": rec.get("quotes"),
        "co_degree": rec.get("co_degree") or 0,
        "cc_degree": rec.get("cc_degree") or 0,
        "comments": rec.get("comments") or 0,
        "top_portal": rec.get("top_portal"),
        "tw_community": rec.get("tw_community"), "cc_community": rec.get("cc_community"),
        "tw_org": rec.get("tw_org") or 0, "cc_org": rec.get("cc_org") or 0,
        "tw_organizer": rec.get("tw_organizer") or False,
        "cc_organizer": rec.get("cc_organizer") or False,
        "auto_score": rec.get("auto_score") or 0,
        "night_ratio_g": rec.get("night_ratio") or 0,
        "hour_entropy": rec.get("hour_entropy") or 0,
        "short_lat_frac": rec.get("short_lat_frac") or 0,
        "dup_ratio_g": rec.get("dup_ratio") or 0,
        "lead_score": rec.get("lead_score") or 0,
        "lead_n": rec.get("lead_n") or 0,
        "template_frac": rec.get("template_frac") or 0,
        "reg_score": rec.get("reg_score") or 0,
        "role": rec.get("role"),
        "farm_ratio": rec.get("farm_ratio") or 0,
        "farm_machine": rec.get("farm_machine"),
        "work_hours_pct": rec.get("work_hours_pct") or 0,
        "weekend_ratio": rec.get("weekend_ratio") or 0,
        "shift_archetype": rec.get("shift_archetype"),
        "pseudonyms": rec.get("pseudonyms") or 0,
        "toxicity_score": rec.get("toxicity_score") or 0,
        "toxicity_level": rec.get("toxicity_level") or "Netoksičan",
        "toxic_attacks": rec.get("toxic_attacks") or 0,
        "infiltrator_ratio": rec.get("infiltrator_ratio") or 0,
        "portal_role": rec.get("portal_role"),
        "crit_comments": rec.get("crit_comments") or 0,
        "tab_comments": rec.get("tab_comments") or 0,
        # veličina čvora raste logaritamski sa brojem akcija (~2..7)
        "val": round(2 + 1.1 * math.log10((rec.get("actions") or 0) + 1), 2),
    }


def acc_node(rec):
    return {
        "id": f"acc:{rec['id']}", "type": "account",
        "label": ("@" + rec["handle"]) if rec.get("handle") else f"nalog #{rec['id']}",
        "deleted": rec.get("deleted"), "verified": rec.get("verified"),
        "link": rec.get("link"), "val": 1,
    }


# ---------------------------------------------------------------- overview
@app.get("/api/overview")
def overview(limit: int = Query(60, le=200),
             okrug: str = None, opstina: str = None, layer: str = "twitter"):
    """Najpovezaniji operateri + veze među njima. Sloj 'twitter' koristi
    CO_ACTED/co_degree, 'comments' koristi CO_COMMENTED/cc_degree.
    Opcioni filteri okrug/opština izoluju lokalni klaster."""
    rel, deg, ltype = (("CO_COMMENTED", "cc_degree", "co_commented")
                       if layer == "comments" else ("CO_ACTED", "co_degree", "co_acted"))
    q = f"""
    MATCH (o:Operator)
    WHERE o.{deg} > 0
      AND ($okrug   IS NULL OR o.okrug   = $okrug)
      AND ($opstina IS NULL OR o.opstina = $opstina)
    WITH o ORDER BY o.{deg} DESC LIMIT $limit
    WITH collect(o) AS top
    UNWIND top AS o
    OPTIONAL MATCH (o)-[c:{rel}]-(p:Operator) WHERE p IN top
    RETURN o AS node, collect(DISTINCT {{other:p.id, shared:c.shared, backbone:c.backbone}}) AS edges
    """
    nodes, links, seen = [], [], set()
    with driver.session() as s:
        for row in s.run(q, limit=limit, okrug=okrug, opstina=opstina):
            o = dict(row["node"])
            nodes.append(op_node(o))
            seen.add(o["id"])
            for e in row["edges"]:
                if e["other"] is None:
                    continue
                a, b = sorted((o["id"], e["other"]))
                key = (a, b)
                if key in seen:
                    continue
                seen.add(key)
                links.append({"source": f"op:{a}", "target": f"op:{b}",
                              "type": ltype, "shared": e["shared"],
                              "backbone": e.get("backbone")})
    return {"nodes": nodes, "links": links}


def op_portals(op_id, limit=10, frm=None, to=None):
    """Portali na kojima operater komentariše, sa brojem komentara."""
    tf, tp = "", []
    if frm:
        tf += " AND v.vkk_vreme >= %s"; tp.append(frm)
    if to:
        tf += " AND v.vkk_vreme <= %s"; tp.append(to + " 23:59:59" if len(to) == 10 else to)
    rows = pg(f"""
        SELECT u.vu_portal, count(*) AS comments
        FROM arhiva_vesti_korisnici_komentari v
        JOIN arhiva_vesti_unos u ON u.vu_id = v.vkk_vest_id
        WHERE v.vkk_korisnik_id = %s AND v.vkk_simulacija = 0 AND u.vu_portal <> ''{tf}
        GROUP BY 1 ORDER BY comments DESC LIMIT %s
    """, (op_id, *tp, limit))
    return [{"portal": p, "comments": c} for p, c in rows]


# ---------------------------------------------------------------- detail
@app.get("/api/operator/{op_id}")
def operator_detail(op_id: int, frm: str = None, to: str = None):
    with driver.session() as s:
        rec = s.run("MATCH (o:Operator {id:$id}) RETURN o", id=op_id).single()
        if not rec:
            return {"error": "nije pronađen"}
        o = dict(rec["o"])
    detail = op_node(o)
    detail["top_targets"] = op_targets(op_id, 15, frm, to)
    detail["points"] = op_points(op_id)
    detail.update(op_layers(op_id))
    return detail


# ---------------------------------------------------------------- expand
@app.get("/api/expand/{op_id}")
def expand(op_id: int,
           controls: bool = True, coacted: bool = True, amplifies: bool = True,
           acc_limit: int = 40, co_limit: int = 30, tgt_limit: int = 12,
           frm: str = None, to: str = None, layer: str = "twitter"):
    nodes, links = [], []
    if layer == "comments":
        # ko-komentatori + portali na kojima operater komentariše
        with driver.session() as s:
            for r in s.run(
                "MATCH (o:Operator {id:$id})-[c:CO_COMMENTED]-(p:Operator) "
                "RETURN p, c.shared AS shared, c.backbone AS backbone "
                "ORDER BY c.shared DESC LIMIT $lim",
                id=op_id, lim=co_limit):
                p = dict(r["p"])
                nodes.append(op_node(p))
                a, b = sorted((op_id, p["id"]))
                links.append({"source": f"op:{a}", "target": f"op:{b}",
                              "type": "co_commented", "shared": r["shared"],
                              "backbone": r["backbone"]})
        for pr in op_portals(op_id, 10, frm, to):
            pid = f"portal:{pr['portal']}"
            nodes.append({"id": pid, "type": "portal", "label": pr["portal"], "val": 3})
            links.append({"source": f"op:{op_id}", "target": pid,
                          "type": "comments_on", "comments": pr["comments"]})
        return {"nodes": nodes, "links": links}

    with driver.session() as s:
        if controls:
            for r in s.run(
                "MATCH (o:Operator {id:$id})-[:CONTROLS]->(a:Account) "
                "RETURN a LIMIT $lim", id=op_id, lim=acc_limit):
                a = dict(r["a"])
                nodes.append(acc_node(a))
                links.append({"source": f"op:{op_id}", "target": f"acc:{a['id']}",
                              "type": "controls"})
        if coacted:
            for r in s.run(
                "MATCH (o:Operator {id:$id})-[c:CO_ACTED]-(p:Operator) "
                "RETURN p, c.shared AS shared, c.backbone AS backbone "
                "ORDER BY c.shared DESC LIMIT $lim",
                id=op_id, lim=co_limit):
                p = dict(r["p"])
                nodes.append(op_node(p))
                a, b = sorted((op_id, p["id"]))
                links.append({"source": f"op:{a}", "target": f"op:{b}",
                              "type": "co_acted", "shared": r["shared"],
                              "backbone": r["backbone"]})
    if amplifies:
        for t in op_targets(op_id, tgt_limit, frm, to):
            nodes.append({"id": f"tgt:{t['handle']}", "type": "target",
                          "label": f"@{t['handle']}", "val": 3})
            links.append({"source": f"op:{op_id}", "target": f"tgt:{t['handle']}",
                          "type": "amplifies", "actions": t["actions"]})
    return {"nodes": nodes, "links": links}


# ---------------------------------------------------------- expand a target
@app.get("/api/target/{handle}")
def target_operators(handle: str, limit: int = 30):
    """Operateri koji najviše pumpaju datu metu (reverzno razlistavanje)."""
    rows = pg(f"""
        WITH tw AS (
            SELECT tu_id FROM arhiva_twitter_unos
            WHERE {HANDLE_SQL.replace('t.','')} = %s
        )
        SELECT a.tuka_korisnik_id AS op, count(*) AS actions
        FROM arhiva_twitter_unos_korisnici_akcije a
        JOIN tw ON tw.tu_id = a.tuka_twitter_id
        GROUP BY 1 ORDER BY actions DESC LIMIT %s
    """, (handle.lower().lstrip("@"), limit))
    nodes, links = [{"id": f"tgt:{handle.lower().lstrip('@')}", "type": "target",
                     "label": f"@{handle.lower().lstrip('@')}", "val": 3}], []
    ids = [r[0] for r in rows]
    counts = {r[0]: r[1] for r in rows}
    if ids:
        with driver.session() as s:
            for r in s.run("MATCH (o:Operator) WHERE o.id IN $ids RETURN o", ids=ids):
                o = dict(r["o"])
                nodes.append(op_node(o))
                links.append({"source": f"op:{o['id']}",
                              "target": nodes[0]["id"], "type": "amplifies",
                              "actions": counts.get(o["id"])})
    return {"nodes": nodes, "links": links}


# ---------------------------------------------------------------- search
@app.get("/api/search")
def search(q: str, limit: int = 20):
    ql = q.strip().lower()
    out = []
    if not ql:
        return {"results": out}
    with driver.session() as s:
        for r in s.run(
            "MATCH (o:Operator) WHERE toLower(coalesce(o.ime,'')) CONTAINS $q "
            "RETURN o ORDER BY o.actions DESC LIMIT $lim", q=ql, lim=limit):
            o = dict(r["o"])
            out.append({"id": f"op:{o['id']}", "type": "operator",
                        "label": o.get("ime") or f"Operater #{o['id']}",
                        "actions": o.get("actions"), "accounts": o.get("accounts"),
                        "co_degree": o.get("co_degree") or 0})
        for r in s.run(
            "MATCH (a:Account) WHERE toLower(coalesce(a.handle,'')) CONTAINS $q "
            "RETURN a LIMIT $lim", q=ql, lim=limit):
            a = dict(r["a"])
            out.append({"id": f"acc:{a['id']}", "type": "account",
                        "label": "@" + (a.get("handle") or ""),
                        "deleted": a.get("deleted")})
    return {"results": out}


# ------------------------------------------- account -> its operator (expand)
@app.get("/api/account/{acc_id}")
def account_operator(acc_id: int):
    nodes, links = [], []
    with driver.session() as s:
        r = s.run("MATCH (o:Operator)-[:CONTROLS]->(a:Account {id:$id}) "
                  "RETURN o, a", id=acc_id).single()
        if r:
            o, a = dict(r["o"]), dict(r["a"])
            nodes = [op_node(o), acc_node(a)]
            links = [{"source": f"op:{o['id']}", "target": f"acc:{a['id']}",
                      "type": "controls"}]
    return {"nodes": nodes, "links": links}


def shared_targets(a_id, b_id, limit=8, frm=None, to=None, max_pop=None):
    """Mete na kojima su OBA operatera delovala (konkretne 'spone').
    max_pop: izbaci mete koje dira više od toliko operatera (masovne), i
    rangiraj retke (diskriminativne) spone prve."""
    tc, tp = time_clause(frm, to)
    pop_join = "JOIN target_popularity tp ON tp.handle = z.handle" if max_pop else \
               "LEFT JOIN target_popularity tp ON tp.handle = z.handle"
    pop_filt = "AND tp.operators <= %s" if max_pop else ""
    order = "tp.operators ASC NULLS LAST, " if max_pop else ""
    params = [a_id, b_id, a_id, b_id, *tp] + ([max_pop] if max_pop else []) + [limit]
    rows = pg(f"""
        SELECT z.handle, z.a_cnt, z.b_cnt, tp.operators FROM (
            SELECT {HANDLE_SQL} AS handle,
                   count(*) FILTER (WHERE a.tuka_korisnik_id = %s) AS a_cnt,
                   count(*) FILTER (WHERE a.tuka_korisnik_id = %s) AS b_cnt
            FROM arhiva_twitter_unos_korisnici_akcije a
            JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
            WHERE a.tuka_korisnik_id IN (%s, %s){tc}
            GROUP BY 1
        ) z
        {pop_join}
        WHERE z.a_cnt > 0 AND z.b_cnt > 0 AND z.handle <> '' {pop_filt}
        ORDER BY {order}z.a_cnt + z.b_cnt DESC LIMIT %s
    """, tuple(params))
    return [{"handle": h, "a": ac, "b": bc, "pop": pop} for h, ac, bc, pop in rows]


def shared_news(a_id, b_id, limit=6, frm=None, to=None, max_pop=None):
    """Vesti koje su OBA operatera komentarisala (spone u sloju komentara)."""
    tf, tp = "", []
    if frm:
        tf += " AND v.vkk_vreme >= %s"; tp.append(frm)
    if to:
        tf += " AND v.vkk_vreme <= %s"; tp.append(to + " 23:59:59" if len(to) == 10 else to)
    pop_filt = "AND np.operators <= %s" if max_pop else ""
    order = "np.operators ASC, " if max_pop else ""
    params = [a_id, b_id, a_id, b_id, *tp] + ([max_pop] if max_pop else []) + [limit]
    rows = pg(f"""
        SELECT z.vid, u.vu_portal, u.vu_naslov, z.a_cnt, z.b_cnt, np.operators
        FROM (
            SELECT v.vkk_vest_id AS vid,
                   count(*) FILTER (WHERE v.vkk_korisnik_id = %s) AS a_cnt,
                   count(*) FILTER (WHERE v.vkk_korisnik_id = %s) AS b_cnt
            FROM arhiva_vesti_korisnici_komentari v
            WHERE v.vkk_korisnik_id IN (%s, %s) AND v.vkk_simulacija = 0{tf}
            GROUP BY 1
        ) z
        JOIN arhiva_vesti_unos u ON u.vu_id = z.vid
        LEFT JOIN news_popularity np ON np.vid = z.vid
        WHERE z.a_cnt > 0 AND z.b_cnt > 0 {pop_filt}
        ORDER BY {order}z.a_cnt + z.b_cnt DESC LIMIT %s
    """, tuple(params))
    return [{"vid": v, "portal": p, "naslov": (n or "")[:80], "a": ac, "b": bc, "pop": op}
            for v, p, n, ac, bc, op in rows]


@app.get("/api/path")
def path(a: int, b: int, max_hops: int = 8, targets_per_hop: int = 6,
         frm: str = None, to: str = None, max_pop: int = None, layer: str = "twitter"):
    """Najkraća putanja između dva operatera, sa konkretnim sponama na svakom
    skoku. Sloj 'twitter' = CO_ACTED + zajedničke mete; 'comments' =
    CO_COMMENTED + zajedničke vesti."""
    if a == b:
        return {"found": False, "reason": "isti operater"}
    rel = "CO_COMMENTED" if layer == "comments" else "CO_ACTED"
    ltype = "co_commented" if layer == "comments" else "co_acted"
    with driver.session() as s:
        rec = s.run(f"""
            MATCH (a:Operator {{id:$a}}), (b:Operator {{id:$b}}),
                  p = shortestPath((a)-[:{rel}*..{int(max_hops)}]-(b))
            RETURN [n IN nodes(p) | n{{.id,.ime,.co_degree,.cc_degree,.actions,
                   .accounts,.comments,.top_portal,.targets,.okrug,.opstina,
                   .likes,.rts,.replies,.quotes}}] AS ns,
                   [r IN relationships(p) | r.shared] AS shareds
        """, a=a, b=b).single()
    if not rec or not rec["ns"]:
        return {"found": False, "reason": "nema putanje u izabranoj mreži"}

    ns, shareds = rec["ns"], rec["shareds"]
    nodes = [op_node(dict(n)) for n in ns]
    links, hops = [], []
    for i in range(len(ns) - 1):
        oa, ob = dict(ns[i]), dict(ns[i + 1])
        x, y = sorted((oa["id"], ob["id"]))
        links.append({"source": f"op:{x}", "target": f"op:{y}",
                      "type": ltype, "shared": shareds[i]})
        if layer == "comments":
            br = shared_news(oa["id"], ob["id"], targets_per_hop, frm, to, max_pop)
            for b_ in br:
                nid = f"news:{b_['vid']}"
                lbl = f"{b_['portal']}: {b_['naslov']}" if b_["naslov"] else b_["portal"]
                nodes.append({"id": nid, "type": "news", "label": lbl, "val": 2.5})
                links.append({"source": f"op:{oa['id']}", "target": nid,
                              "type": "commented_on", "comments": b_["a"]})
                links.append({"source": f"op:{ob['id']}", "target": nid,
                              "type": "commented_on", "comments": b_["b"]})
            hops.append({"from": oa.get("ime") or f"#{oa['id']}",
                         "to": ob.get("ime") or f"#{ob['id']}",
                         "shared": shareds[i], "bridges": br, "kind": "news"})
        else:
            tgts = shared_targets(oa["id"], ob["id"], targets_per_hop, frm, to, max_pop)
            for t in tgts:
                tid = f"tgt:{t['handle']}"
                nodes.append({"id": tid, "type": "target", "label": f"@{t['handle']}", "val": 3})
                links.append({"source": f"op:{oa['id']}", "target": tid,
                              "type": "amplifies", "actions": t["a"]})
                links.append({"source": f"op:{ob['id']}", "target": tid,
                              "type": "amplifies", "actions": t["b"]})
            hops.append({"from": oa.get("ime") or f"#{oa['id']}",
                         "to": ob.get("ime") or f"#{ob['id']}",
                         "shared": shareds[i],
                         "bridges": [{"handle": t["handle"], "a": t["a"], "b": t["b"],
                                      "pop": t["pop"]} for t in tgts], "kind": "target"})
    return {"found": True, "hops_count": len(ns) - 1, "layer": layer,
            "path": [n["label"] for n in nodes if n["type"] == "operator"],
            "hops": hops, "nodes": nodes, "links": links}


@app.get("/api/export/operator/{op_id}")
def export_operator(op_id: int, frm: str = None, to: str = None):
    """Ceo klaster jednog operatera: svi nalozi, SVE mete (Postgres, bez
    limita), svi ko-akteri. Pogodno za dalju analizu van platna."""
    with driver.session() as s:
        rec = s.run("MATCH (o:Operator {id:$id}) RETURN o", id=op_id).single()
        if not rec:
            return {"error": "nije pronađen"}
        operator = op_node(dict(rec["o"]))
        accounts = [acc_node(dict(r["a"])) for r in s.run(
            "MATCH (:Operator {id:$id})-[:CONTROLS]->(a:Account) RETURN a", id=op_id)]
        coactors = [{**op_node(dict(r["p"])), "shared": r["shared"]} for r in s.run(
            "MATCH (:Operator {id:$id})-[c:CO_ACTED]-(p:Operator) "
            "RETURN p, c.shared AS shared ORDER BY c.shared DESC", id=op_id)]
    operator.pop("top_targets", None)
    return {
        "operator": operator,
        "accounts": accounts,
        "coactors": coactors,
        "targets": op_targets(op_id, 100000, frm, to),  # sve mete
        "window": {"from": frm, "to": to},
    }


@app.get("/api/behavior/{op_id}")
def behavior(op_id: int):
    """Bihevioralni profil operatera: ritam po satu, noćna aktivnost,
    latencija zadatak→akcija, miks akcija, raspon aktivnosti."""
    hours = [0] * 24
    for hh, c in pg("""
        SELECT substr(tuka_vreme, 12, 2) AS hh, count(*)
        FROM arhiva_twitter_unos_korisnici_akcije
        WHERE tuka_korisnik_id = %s GROUP BY 1
    """, (op_id,)):
        if hh and hh.isdigit():
            hours[int(hh)] = c
    total = sum(hours) or 1
    night = sum(hours[0:6])
    agg = pg("""
        SELECT count(*), min(tuka_datum), max(tuka_datum),
               count(DISTINCT tuka_datum),
               count(*) FILTER (WHERE tuka_akcija=0), count(*) FILTER (WHERE tuka_akcija=1),
               count(*) FILTER (WHERE tuka_akcija=2), count(*) FILTER (WHERE tuka_akcija=3),
               count(DISTINCT tuka_twitter_id), count(DISTINCT tuka_nalog_id)
        FROM arhiva_twitter_unos_korisnici_akcije WHERE tuka_korisnik_id = %s
    """, (op_id,))[0]
    # medijana latencije + raspodela po koficama (sekunde/minuti)
    latrows = pg("""
        SELECT
          percentile_cont(0.5) WITHIN GROUP (ORDER BY d) AS med,
          count(*) AS n,
          count(*) FILTER (WHERE d < 60)             AS b1,
          count(*) FILTER (WHERE d >= 60 AND d < 300)   AS b2,
          count(*) FILTER (WHERE d >= 300 AND d < 1800)  AS b3,
          count(*) FILTER (WHERE d >= 1800 AND d < 7200) AS b4,
          count(*) FILTER (WHERE d >= 7200 AND d < 43200) AS b5,
          count(*) FILTER (WHERE d >= 43200)           AS b6
        FROM (
          SELECT extract(epoch FROM (a.tuka_vreme::timestamp - t.tu_kreirano_vreme::timestamp)) AS d
          FROM arhiva_twitter_unos_korisnici_akcije a
          JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
          WHERE a.tuka_korisnik_id = %s AND a.tuka_vreme > t.tu_kreirano_vreme
        ) z
    """, (op_id,))[0]
    med = latrows[0]
    lat_buckets = {"<1min": latrows[2], "1-5min": latrows[3], "5-30min": latrows[4],
                   "30min-2h": latrows[5], "2-12h": latrows[6], ">12h": latrows[7]}
    # radni dani (0=nedelja .. 6=subota) -> preuredi u pon..ned
    wd = [0] * 7
    for d, c in pg("""
        SELECT extract(dow FROM tuka_datum::date)::int, count(*)
        FROM arhiva_twitter_unos_korisnici_akcije
        WHERE tuka_korisnik_id = %s AND tuka_datum IS NOT NULL GROUP BY 1
    """, (op_id,)):
        wd[d] = c
    weekday = wd[1:] + wd[:1]  # pon, uto, sre, cet, pet, sub, ned
    # dnevni timeline
    daily = [{"d": d, "n": n} for d, n in pg("""
        SELECT tuka_datum, count(*) FROM arhiva_twitter_unos_korisnici_akcije
        WHERE tuka_korisnik_id = %s AND tuka_datum IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """, (op_id,))]
    # komentari: duplikati + broj + portali
    crow = pg("""
        SELECT count(*), count(DISTINCT vkk_komentar)
        FROM arhiva_vesti_korisnici_komentari
        WHERE vkk_korisnik_id = %s AND vkk_simulacija = 0 AND vkk_komentar <> ''
    """, (op_id,))[0]
    dup_ratio = round(1 - (crow[1] / crow[0]), 3) if crow[0] else None
    # top napadnute mete (najviše reply akcija od ovog operatera)
    top_attacked = [{"handle": h, "attacks": a} for h, a in pg(f"""
        SELECT {HANDLE_SQL} AS handle, count(*) AS attacks
        FROM arhiva_twitter_unos_korisnici_akcije a
        JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
        WHERE a.tuka_korisnik_id = %s AND a.tuka_akcija = 2
        GROUP BY 1 ORDER BY attacks DESC LIMIT 5
    """, (op_id,)) if h]
    with driver.session() as s:
        tox = s.run("MATCH (o:Operator {id:$id}) RETURN o.toxicity_score AS sc, "
                    "o.toxicity_level AS lv, o.toxic_attacks AS at, "
                    "o.portal_role AS pr, o.infiltrator_ratio AS ir", id=op_id).single()
    # tretman portala: poslato/objavljeno (prolaznost) po kategoriji
    pt = {}
    for kat, portals in (("critical", CRIT_PORTALS), ("tabloid", TAB_PORTALS)):
        row = pg("""
            SELECT count(*), sum((v.vkk_objavljen=1)::int)
            FROM arhiva_vesti_korisnici_komentari v
            JOIN arhiva_vesti_unos u ON u.vu_id = v.vkk_vest_id
            WHERE v.vkk_korisnik_id = %s AND v.vkk_simulacija = 0 AND u.vu_portal = ANY(%s)
        """, (op_id, list(portals)))[0]
        sent, pub = row[0] or 0, row[1] or 0
        pt[kat] = {"sent": sent, "published": pub,
                   "rate": round(pub / sent, 4) if sent else None}
    return {
        "hours": hours,
        "toxicity_score": (tox and tox["sc"]) or 0,
        "toxicity_level": (tox and tox["lv"]) or "Netoksičan",
        "toxic_attacks": (tox and tox["at"]) or 0,
        "portal_role": (tox and tox["pr"]) or None,
        "infiltrator_ratio": (tox and tox["ir"]) or 0,
        "portal_treatment": pt,
        "top_attacked": top_attacked,
        "night_ratio": round(night / total, 3),
        "actions": agg[0], "from": agg[1], "to": agg[2], "active_days": agg[3],
        "mix": {"like": agg[4], "rt": agg[5], "reply": agg[6], "quote": agg[7]},
        "targets": agg[8], "accounts": agg[9],
        "median_latency_min": round(med / 60.0, 1) if med is not None else None,
        "lat_buckets": lat_buckets,
        "weekday": weekday,
        "daily": daily,
        "comments": crow[0], "dup_ratio": dup_ratio,
        "portals": op_portals(op_id, 6),
    }


BEHAV_METRIC = {
    "auto": "auto_score", "night": "night_ratio", "short_lat": "short_lat_frac",
    "entropy": "hour_entropy", "dup": "dup_ratio", "lead": "lead_score",
    "template": "template_frac", "reg": "reg_score", "farm": "farm_ratio",
    "pseudonyms": "pseudonyms", "toxicity": "toxicity_score",
    "infiltrator": "infiltrator_ratio",
}

CRIT_PORTALS = ('n1info.rs', 'nova.rs', 'danas.rs', 'juznevesti.com', 'vreme.com', 'radar.rs')
TAB_PORTALS = ('informer.rs', 'alo.rs', 'kurir.rs', 'novosti.rs')


@app.get("/api/behavior_top")
def behavior_top(layer: str = "twitter", limit: int = Query(40, le=150),
                 metric: str = "auto"):
    """Operateri rangirani po izabranoj bihevioralnoj metrici + veze među njima.
    metric: auto | night | short_lat | entropy | dup | lead | template"""
    prop = BEHAV_METRIC.get(metric, "auto_score")
    if metric == "template":
        rel, ltype = "CO_TEMPLATE", "co_template"
    elif layer == "comments":
        rel, ltype = "CO_COMMENTED", "co_commented"
    else:
        rel, ltype = "CO_ACTED", "co_acted"
    q = f"""
    MATCH (o:Operator) WHERE o.{prop} > 0
    WITH o ORDER BY o.{prop} DESC LIMIT $limit
    WITH collect(o) AS top
    UNWIND top AS o
    OPTIONAL MATCH (o)-[c:{rel}]-(p:Operator) WHERE p IN top
    RETURN o AS node, collect(DISTINCT {{other:p.id, shared:c.shared, backbone:c.backbone}}) AS edges
    """
    nodes, links, seen = [], [], set()
    with driver.session() as s:
        for row in s.run(q, limit=limit):
            o = dict(row["node"])
            nodes.append(op_node(o)); seen.add(o["id"])
            for e in row["edges"]:
                if e["other"] is None:
                    continue
                a, b = sorted((o["id"], e["other"]))
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                links.append({"source": f"op:{a}", "target": f"op:{b}",
                              "type": ltype, "shared": e["shared"],
                              "backbone": e.get("backbone")})
    return {"nodes": nodes, "links": links}


@app.get("/api/bursts")
def bursts(limit: int = Query(40, le=200), min_ops: int = 10):
    """Najsinhronizovanije kampanje (mete) — nalet operatera u prvih 10 min."""
    rows = pg("""
        SELECT tid, handle, nops, peak10, span_min, synchrony
        FROM target_bursts
        WHERE nops >= %s AND handle <> ''
        ORDER BY peak10 DESC, synchrony DESC
        LIMIT %s
    """, (min_ops, limit))
    return {"campaigns": [
        {"tid": r[0], "handle": r[1], "operators": r[2], "peak10": r[3],
         "span_min": r[4], "synchrony": float(r[5])} for r in rows]}


@app.get("/api/burst/{tid}")
def burst(tid: int):
    """Vremenska linija jedne kampanje: nalet po minutu + prvi (lideri) +
    operateri kao čvorovi oko mete."""
    ft = pg("""
        SELECT a.tuka_korisnik_id,
               extract(epoch FROM (min(a.tuka_vreme::timestamp) - c.t0)) AS off
        FROM arhiva_twitter_unos_korisnici_akcije a
        CROSS JOIN (SELECT min(tuka_vreme::timestamp) t0
                    FROM arhiva_twitter_unos_korisnici_akcije
                    WHERE tuka_twitter_id = %s) c
        WHERE a.tuka_twitter_id = %s
        GROUP BY a.tuka_korisnik_id, c.t0
    """, (tid, tid))
    if not ft:
        return {"found": False}
    offs = sorted(o for _, o in ft)
    # nalet po minutu u prvih 60 min + ostatak
    mins = [0] * 61
    for o in offs:
        m = int(o // 60)
        mins[m if m < 60 else 60] += 1
    hrow = pg("SELECT handle, nops, peak10, span_min, synchrony "
              "FROM target_bursts WHERE tid = %s", (tid,))
    meta = ({"handle": hrow[0][0], "operators": hrow[0][1], "peak10": hrow[0][2],
             "span_min": hrow[0][3], "synchrony": float(hrow[0][4])} if hrow else {})
    # lideri (prvih 12 po vremenu) sa imenima
    order = sorted(ft, key=lambda x: x[1])[:12]
    ids = [op for op, _ in order]
    names = {}
    if ids:
        for r in pg("""
            SELECT k_id, NULLIF(trim(coalesce(k_ime,'')||' '||coalesce(k_prezime,'')),'')
            FROM korisnici WHERE k_id = ANY(%s)
        """, (ids,)):
            names[r[0]] = r[1]
    leaders = [{"id": op, "ime": names.get(op) or f"#{op}", "off_s": round(o)}
               for op, o in order]
    # operateri kao čvorovi oko mete (iz Neo4j, puni op_node)
    allids = [op for op, _ in ft][:120]
    nodes, links = [], []
    h = meta.get("handle", str(tid))
    tgt = f"tgt:{h}"
    nodes.append({"id": tgt, "type": "target", "label": f"@{h}", "val": 4})
    with driver.session() as s:
        for r in s.run("MATCH (o:Operator) WHERE o.id IN $ids RETURN o", ids=allids):
            o = dict(r["o"])
            nodes.append(op_node(o))
            links.append({"source": f"op:{o['id']}", "target": tgt, "type": "amplifies"})
    return {"found": True, "tid": tid, "meta": meta, "minutes": mins,
            "leaders": leaders, "nodes": nodes, "links": links}


@app.get("/api/behavior_cohort")
def behavior_cohort():
    """Raspodela (decili) ključnih bihevioralnih metrika kroz sve operatere —
    za smestiti pojedinca u kontekst mreže."""
    out = {}
    with driver.session() as s:
        for key in ("auto_score", "night_ratio", "short_lat_frac", "hour_entropy"):
            vals = [r["v"] for r in s.run(
                f"MATCH (o:Operator) WHERE o.{key} IS NOT NULL "
                f"RETURN o.{key} AS v")]
            vals.sort()
            n = len(vals)
            if not n:
                out[key] = None; continue
            dec = [round(vals[min(n - 1, int(n * i / 10))], 4) for i in range(11)]
            out[key] = {"deciles": dec, "n": n,
                        "mean": round(sum(vals) / n, 4)}
    return out


@app.get("/api/crosslayer")
def crosslayer(limit: int = Query(40, le=150)):
    """Operateri jaki u OBA sloja (tviter + komentari) — verovatni glavni
    koordinatori. master = sqrt(tw_org * cc_org). Vraća oba tipa veza."""
    q = """
    MATCH (o:Operator) WHERE o.tw_org > 0 AND o.cc_org > 0
    WITH o, sqrt(o.tw_org * o.cc_org) AS ms ORDER BY ms DESC LIMIT $limit
    WITH collect(o) AS top, collect({id:o.id, ms:ms}) AS mss
    UNWIND top AS o
    OPTIONAL MATCH (o)-[c:CO_ACTED]-(p:Operator) WHERE p IN top
    WITH top, mss, o, collect(DISTINCT {id:p.id, s:c.shared, bb:c.backbone}) AS twe
    OPTIONAL MATCH (o)-[d:CO_COMMENTED]-(r:Operator) WHERE r IN top
    RETURN o AS node, twe, collect(DISTINCT {id:r.id, s:d.shared, bb:d.backbone}) AS cce,
           [m IN mss WHERE m.id = o.id][0].ms AS ms
    """
    nodes, links, seen = [], [], set()
    with driver.session() as s:
        for row in s.run(q, limit=limit):
            o = dict(row["node"])
            nd = op_node(o)
            nd["master"] = round(row["ms"], 4)
            nd["community"] = o.get("tw_community")
            nd["val"] = round(3 + 5 * row["ms"], 2)
            nodes.append(nd)
            for etype, coll in (("co_acted", row["twe"]), ("co_commented", row["cce"])):
                for e in coll:
                    if e["id"] is None:
                        continue
                    a, b = sorted((o["id"], e["id"]))
                    key = (a, b, etype)
                    if key in seen:
                        continue
                    seen.add(key)
                    links.append({"source": f"op:{a}", "target": f"op:{b}",
                                  "type": etype, "shared": e["s"],
                                  "backbone": e.get("bb")})
    return {"nodes": nodes, "links": links}


@app.get("/api/organizers")
def organizers(layer: str = "twitter", limit: int = Query(40, le=150),
               only_centroids: bool = False):
    """Najuticajniji operateri (organizatori/centroidi) po sloju, sa vezama
    među sobom. Boji se po zajednici (community), centroidi su označeni."""
    pfx, rel, ltype = (("cc", "CO_COMMENTED", "co_commented")
                       if layer == "comments" else ("tw", "CO_ACTED", "co_acted"))
    cond = f"o.{pfx}_organizer = true" if only_centroids else f"o.{pfx}_org > 0"
    q = f"""
    MATCH (o:Operator) WHERE {cond}
    WITH o ORDER BY o.{pfx}_org DESC LIMIT $limit
    WITH collect(o) AS top
    UNWIND top AS o
    OPTIONAL MATCH (o)-[c:{rel}]-(p:Operator) WHERE p IN top
    RETURN o AS node, collect(DISTINCT {{other:p.id, shared:c.shared, backbone:c.backbone}}) AS edges
    """
    nodes, links, seen = [], [], set()
    with driver.session() as s:
        for row in s.run(q, limit=limit):
            o = dict(row["node"])
            nd = op_node(o)
            nd["community"] = o.get(f"{pfx}_community")
            nd["org"] = o.get(f"{pfx}_org") or 0
            nd["is_organizer"] = o.get(f"{pfx}_organizer") or False
            nodes.append(nd); seen.add(o["id"])
            for e in row["edges"]:
                if e["other"] is None:
                    continue
                a, b = sorted((o["id"], e["other"]))
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                links.append({"source": f"op:{a}", "target": f"op:{b}",
                              "type": ltype, "shared": e["shared"],
                              "backbone": e.get("backbone")})
    return {"nodes": nodes, "links": links, "layer": layer}


@app.get("/api/regions")
def regions():
    """Okruzi sa pripadajućim opštinama (za filtere)."""
    out = []
    with driver.session() as s:
        for r in s.run("""
            MATCH (o:Operator) WHERE o.okrug IS NOT NULL
            RETURN o.okrug AS okrug,
                   count(o) AS n,
                   [x IN collect(DISTINCT o.opstina) WHERE x IS NOT NULL] AS opstine
            ORDER BY n DESC
        """):
            out.append({"okrug": r["okrug"], "n": r["n"],
                        "opstine": sorted(r["opstine"])})
    return {"okruzi": out}


def _load_betting():
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "betting_geo.json")
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("by_opstina", {})
    except Exception:  # noqa: BLE001
        return {}


BETTING_BY_OPSTINA = _load_betting()


def _load_taskmasters():
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "task_masters.json")
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {"masters": [], "count": 0, "coordinators": 0}


TASKMASTERS = _load_taskmasters()


def _load_command_voter():
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "command_voter.json")
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {"people": [], "count": 0, "coordinators": 0, "with_terminals": 0}


COMMAND_VOTER = _load_command_voter()


@app.get("/api/command_voter")
def command_voter(limit: int = Query(61, le=61)):
    """Komandna odgovornost & Voter: nosioci VOTER privilegija + uloge + glasovi
    + terminali u opštini. SAMO ono što podaci dokazuju (fer play)."""
    people = []
    for m in COMMAND_VOTER.get("people", [])[:limit]:
        people.append({
            "id": m["id"], "ime": m.get("ime") or f"#{m['id']}",
            "privs": m.get("privs") or [], "coordinator": m.get("coordinator", False),
            "centroid": m.get("centroid", False), "okrug": m.get("okrug"),
            "opstina": m.get("opstina"), "shops_in_opstina": m.get("shops_in_opstina", 0),
            "votes_credited": m.get("votes_credited", 0),
            "voter_priority_tasks": m.get("voter_priority_tasks", 0),
            "max_org": m.get("max_org", 0), "in_graph": m.get("max_org", 0) > 0 or m.get("centroid", False),
        })
    return {"count": COMMAND_VOTER.get("count", 0),
            "coordinators": COMMAND_VOTER.get("coordinators", 0),
            "with_terminals": COMMAND_VOTER.get("with_terminals", 0),
            "people": people}


def _load_directives():
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "directives.json")
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


DIRECTIVES = _load_directives()


def _load_coordinators():
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "coordinators.json")
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


COORDINATORS = _load_coordinators()


def _load_cascade():
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "cascade.json")
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


CASCADE = _load_cascade()


def _load_json_geo(fname):
    try:
        p = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", fname)
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


VOTER_GEOIP = _load_json_geo("voter_geoip.json")
VOTER_TIMING = _load_json_geo("voter_timing.json")
BETTING_CORP = _load_json_geo("betting_corporate.json")
SHIFT_CHAT = _load_json_geo("shift_chat.json")
GAMIFICATION = _load_json_geo("gamification.json")
REGIONAL_OPS = _load_json_geo("regional_operations.json")
TACTICAL_GROUPS = _load_json_geo("tactical_groups.json")
SYSTEM_SURVEILLANCE = _load_json_geo("system_surveillance.json")
MULTIPLATFORM = _load_json_geo("multiplatform.json")
VOTER_KURIR = _load_json_geo("voter_kurir_accounts.json")
VOTER_CUSTOM = _load_json_geo("voter_custom_actions.json")

# ISO-2 kodovi afričkih država prisutnih u voter podacima (za udeo Afrike)
_AFRICA = {"CM": "Kamerun", "CG": "Kongo (Brazavil)", "CD": "DR Kongo", "TZ": "Tanzanija",
           "CI": "Obala Slonovače", "LS": "Lesoto", "SC": "Sejšeli", "TD": "Čad",
           "NG": "Nigerija", "GH": "Gana", "SN": "Senegal", "KE": "Kenija"}
_CC_NAME = {"RS": "Srbija", "BA": "BiH", "ME": "Crna Gora", "IT": "Italija",
            "PE": "Peru", "CY": "Kipar", "US": "SAD", "MT": "Malta", "GB": "UK",
            "HR": "Hrvatska", "BE": "Belgija", "DE": "Nemačka", **_AFRICA}


@app.get("/api/directives")
def directives(top: int = Query(25, le=40)):
    """Analiza direktiva (smernica): taksonomija (akcija/ton/izvor/cross-platform),
    lanac direktiva→meta→reakcija, i centralni komandni izvor (SS/ČET/ŠEF).
    FER PLAY: kreator = ko je UNEO zadatak; „Šef/čet“ u tekstu referišu na uzvodnog
    lidera koji NIJE nužno red u bazi (vidi disclaimer u command_source)."""
    d = DIRECTIVES
    cs = dict(d.get("command_source", {}))
    cs["top_issuers"] = cs.get("top_issuers", [])[:top]
    return {
        "generated": d.get("generated"),
        "twitter": d.get("twitter", {}),
        "news": d.get("news", {}),
        "chain": d.get("chain", {}),
        "command_source": cs,
        "examples": d.get("examples", {}),
        "defs": d.get("defs", {}),
    }


@app.get("/api/voter_geoip")
def voter_geoip():
    """Voter infrastruktura: GeoIP (države/ASN, udeo Afrike) + tajming glasanja.
    Offline iptoasn mapiranje voter IP adresa; strana/afrička kladioničarska mreža."""
    g = VOTER_GEOIP or {}
    countries = g.get("country_ip", {}) or g.get("countries", {})
    africa = {cc: n for cc, n in countries.items() if cc in _AFRICA}
    africa_ip = sum(africa.values())
    total_ip = sum(countries.values()) or 1
    # rang država (po IP) sa imenima + afrička oznaka
    ranked = sorted(countries.items(), key=lambda kv: kv[1], reverse=True)
    country_rows = [{"cc": cc, "name": _CC_NAME.get(cc, cc), "ips": n,
                     "africa": cc in _AFRICA} for cc, n in ranked]
    asn_rows = [{"asn": k, "n": v, "africa": any(f"({cc})" in k for cc in _AFRICA)}
                for k, v in sorted((g.get("asn", {}) or {}).items(),
                                   key=lambda kv: kv[1], reverse=True)]
    t = VOTER_TIMING or {}
    return {
        "total": g.get("total", 0), "matched": g.get("matched", 0),
        "foreign": g.get("foreign", 0), "distinct_ip": g.get("distinct_ip", 0),
        "rs_ip": g.get("rs_ip", 0),
        "africa_ip": africa_ip, "africa_share": round(africa_ip / total_ip, 3),
        "africa_countries": {_CC_NAME.get(cc, cc): n for cc, n in
                             sorted(africa.items(), key=lambda kv: kv[1], reverse=True)},
        "countries": country_rows, "asn": asn_rows[:30],
        "timing": {
            "median_s": t.get("latency", {}).get("median_s"),
            "n": t.get("latency", {}).get("n"),
            "buckets": t.get("latency", {}).get("buckets", {}),
            "vote_hours": t.get("vote_hours", []),
            "vote_night_ratio": t.get("vote_night_ratio"),
            "vote_night_0008": t.get("vote_night_0008"),
            "machine_hours": t.get("machine_hours", {}),
            "machine_night_0008": t.get("machine_night_0008", {}),
            "custom_hours": t.get("custom_hours", {}),
            "verdict": t.get("verdict"),
        },
        "note": ("Velik deo voter mašina je OZNAČEN imenima uplatnih mesta/brendova "
                 "kladionica (polje vr_naziv_ss: Scooorebet/Maxi/Joker + srpske "
                 "filijale + afričke lokacije), potvrđeno IP geografijom — inferencija "
                 "iz labele, ne hard-dokaz da je mašina baš terminal. IP daje samo "
                 "državu/ASN; operateri NEMAJU IP (ovo je geografija VOTER mašina, ne "
                 "operatera). Vidi docs/voter_kladionice_infrastruktura.md."),
    }


def _fmt(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _build_dossier():
    """Sintetiše sve module u formalni Markdown istraživački dosije. Brojke se
    čitaju iz generisanih JSON-ova (žive sa analizom); fer-play granice su ugrađene."""
    cv, dr, co = COMMAND_VOTER, DIRECTIVES, COORDINATORS
    ca, gi, ti = CASCADE, VOTER_GEOIP, VOTER_TIMING
    bc, tm = BETTING_CORP, TASKMASTERS
    cve = (co or {}).get("command_vs_execution", {})
    ssp = (ca or {}).get("ss_priority", {})
    gi_c = gi or {}
    countries = gi_c.get("country_ip", {}) or gi_c.get("countries", {})
    africa_ip = sum(v for k, v in countries.items() if k in _AFRICA)
    total_ip = sum(countries.values()) or 1
    africa_share = africa_ip / total_ip
    africa_countries = {_CC_NAME.get(k, k): v for k, v in
                        sorted(((k, v) for k, v in countries.items() if k in _AFRICA),
                               key=lambda kv: kv[1], reverse=True)}
    asn_sorted = sorted((gi_c.get("asn", {}) or {}).items(), key=lambda kv: kv[1], reverse=True)
    L = []
    a = L.append
    a("# Istraživački dosije — koordinisana astroturfing mreža (Cacix)\n")
    a(f"**Generisano:** {datetime.now().isoformat(timespec='seconds')}  ")
    a("**Izvor:** interna baza `progress` (ground-truth sistema), Neo4j graf, offline GeoIP.  ")
    a("**Status:** radni dokument. Fer-play granice atribucije su sastavni deo svakog nalaza.\n")
    a("---\n")

    # 1
    a("## 1. Izvršni rezime\n")
    a("Reč je o **unutrašnjem ground-truth sistemu** koordinisane mreže naloga koja "
      "svojim članovima zadaje zadatke na društvenim mrežama i portalima i beleži ko je "
      "šta uradio. Analiza pokazuje:\n")
    a("- **Organizovani ljudi u smenama**, ne klasična automatizacija (auto_score max ~0,45; "
      "vrh aktivnosti 9–16h; pad vikendom).")
    a(f"- **Komanda je odvojena od izvršenja:** {_fmt(cve.get('coordinators_total','?'))} formalnih "
      f"koordinatora, ali **{cve.get('are_centroids','?')}** su mrežni centroidi.")
    a("- **550M+ automatskih glasova** sa terminala u uplatnim mestima kladionica u Srbiji i "
      f"Africi; **{int(africa_share*100)}% distinct IP iz Afrike**.")
    a(f"- **Centralne direktive (SS) imaju prioritet** i propagiraju ~{ssp.get('speedup_pct','?')}% "
      "brže; vrh koplja je Vojvodina/Beograd.")
    a("- **Granica (fer play):** NE postoji veza mašina↔operater; vlasništvo kladionica NIJE u "
      "bazi. Zaključci o mehanizmu i vlasništvu su hipoteze/metodologija, ne dokaz.\n")

    # 2
    a("## 2. Komandna struktura\n")
    a(f"- **Task-masteri (ko zadaje):** {_fmt((tm or {}).get('count','?'))} ljudi kreira sve "
      f"portal-zadatke; {_fmt((tm or {}).get('coordinators','?'))} su koordinatori.")
    a(f"- **Nosioci VOTER privilegija:** {_fmt((cv or {}).get('count','?'))} lica "
      f"(eksplicitne privilegije), {_fmt((cv or {}).get('coordinators','?'))} koordinatora, "
      f"{_fmt((cv or {}).get('with_terminals','?'))} u opštini sa terminalima.")
    lv = (co or {}).get("levels", {})
    a(f"- **Hijerarhija koordinatora (geografska):** region {lv.get('region','?')}, okrug "
      f"{lv.get('okrug','?')}, opština {lv.get('opstina','?')} (+{lv.get('deputies','?')} zamenika).")
    a(f"- **Komanda ≠ izvršenje:** od {_fmt(cve.get('coordinators_total','?'))} koordinatora u grafu "
      f"{_fmt(cve.get('in_graph','?'))}, centroida **{cve.get('are_centroids','?')}**, SS-izdavača "
      f"{cve.get('are_ss_issuers','?')}. Formalna titula i mrežna moć su razdvojeni slojevi.")
    top = [p for p in (cv or {}).get("people", [])][:5]
    if top:
        a("\n  Istaknuti (prava + uloge + kreditirani glasovi — NE dokaz pokretanja mašina):")
        for p in top:
            a(f"  - {p.get('ime','?')}: {_fmt(p.get('votes_credited',0))} glasova"
              f"{' · koordinator' if p.get('coordinator') else ''}"
              f"{' · '+p['opstina'] if p.get('opstina') else ''}")
    sc, gm = SHIFT_CHAT or {}, GAMIFICATION or {}
    sup = sc.get("supervisors", [])
    if sup:
        tax = sc.get("taxonomy", {})
        a(f"- **Dežurstva (operativni chat, {_fmt(sc.get('total_messages','?'))} poruka):** smene se "
          f"vode i kontrolišu kroz interni chat (primopredaja {_fmt(tax.get('primopredaja','?'))}, "
          f"kontrola {_fmt(tax.get('kontrola','?'))}, nalozi za brisanje {_fmt(tax.get('brisanje','?'))}). "
          f"Vodeći supervizor: {sup[0].get('ime','?')}"
          f"{' ('+sup[0]['pozicija']+')' if sup[0].get('pozicija') else ''}.")
    lb = gm.get("leaderboard", [])
    ppa = {p["action"]: p["per_action"] for p in gm.get("points_per_action", [])}
    if ppa:
        a(f"- **Partijska ekonomija (bodovi):** sistem najviše plaća quote (~{ppa.get('quote','?')}) i "
          f"reply (~{ppa.get('reply','?')}) vs lajk (~{ppa.get('lajk','?')}) — podsticaj za napad/odgovor, "
          f"ne za pasivan lajk.")
    if lb:
        juris = sum(1 for m in lb[:10] if (m.get("toxicity_level") or "").find("Jurišnik") >= 0 or (m.get("toxicity_level") or "").find("Ekstremna") >= 0)
        a(f"  Među top 10 „udarnika“ po bodovima, {juris} su jurišnici (ekstremna toksičnost) — "
          f"ekonomija nagrađuje napadače. Vrh: {lb[0].get('ime','?')} ({_fmt(lb[0].get('points',0))} bodova).")
    a("")

    # 3
    a("## 3. Infrastruktura uplatnih mesta i Afrika\n")
    a(f"- **Mašine:** {_fmt((bc or {}).get('machines_total','?'))} ukupno — "
      f"{_fmt((bc or {}).get('machines_serbia','?'))} Srbija, {_fmt((bc or {}).get('machines_foreign','?'))} strano.")
    if (bc or {}).get("brands"):
        a("- **Brendovi (iz labele mašine `vr_naziv_ss`, tragovi):** "
          + ", ".join(f"{b['brand']} {b['total']} (strano {b['foreign']})" for b in bc["brands"][:5]) + ".")
    a(f"- **GeoIP:** {_fmt(gi_c.get('foreign','?'))}/{_fmt(gi_c.get('matched','?'))} mašina strano; "
      f"Afrika {int(africa_share*100)}% distinct IP.")
    if africa_countries:
        a("  - Afričke države (IP): " + ", ".join(f"{k} {v}" for k, v in list(africa_countries.items())[:6]) + ".")
    if asn_sorted:
        a("  - Vodeći ASN: " + ", ".join(f"{name.split(' · ')[0]}={n}" for name, n in asn_sorted[:5]) + ".")
    a("- **Instaliran softver:** verzionisan klijent (`vr_verzija` 1.0.2.172–177).")
    a("- **Regulatorna izloženost (okvir, ne presuda):** ako primarni registar (APR / Uprava za "
      "igre na sreću) potvrdi da licencirani priređivač drži terminale korišćene za političke "
      "sajber aktivnosti → osnov za zloupotrebu koncesije. **Brend/lokacija su tragovi, ne dokaz "
      "vlasništva; „Scooorebet“ (Afrika) se NE izjednačava sa srpskim lancima bez primarnog izvora.**\n")

    # 4
    a("## 4. Vremenski mehanizam\n")
    a(f"- **SS kaskada:** centralne direktive propagiraju ~{ssp.get('speedup_pct','?')}% brže "
      f"(medijana prve reakcije {ssp.get('ss',{}).get('median_s','?')}s vs "
      f"{ssp.get('baseline',{}).get('median_s','?')}s).")
    fm = (ca or {}).get("first_mover_all", [])[:3]
    if fm:
        a("- **Vrh koplja (prvi reagent):** " + ", ".join(f"{r['okrug'].replace(' okrug','')} ({_fmt(r['first_moves'])})" for r in fm) + ".")
    if (ti or {}).get("verdict"):
        a(f"- **Satnica mašina:** {ti['verdict']}")
    a("")

    # 5
    a("## 5. Pravni osnov i fer-play atribucija\n")
    a("**Citirani osnov (okvir, ne pravna presuda — nismo pravnici):**")
    a("- Budimpeštanska konvencija o sajber kriminalu — čl. 5 (ometanje sistema) i čl. 6 "
      "(zloupotreba uređaja: neovlašćeni bot-klijent na komercijalnim terminalima).")
    a("- Zloupotreba kockarske licence/koncesije (terminali za igre na sreću korišćeni za "
      "političke sajber operacije u Srbiji i Africi).")
    a("- Realna izloženost je po **domaćim zakonima** svake jurisdikcije.\n")
    a("**Granice atribucije (obavezno):**")
    a("- NE postoji spojni ključ `voter_racunari` (mašina/IP) ↔ `knv_voter_*` (glas kreditiran "
      "operateru) → mehanizam „operater → daljinski terminal → glas“ je **hipoteza**, ne dokaz.")
    a("- Vlasništvo uplatnih mesta NIJE u bazi → zahteva APR/UIS; ne imenovati pojedince bez "
      "primarnog izvora.")
    a("- Raspon kontrole koordinatora = geografska nadležnost, ne dokaz pojedinačnog naređenja.")
    a("- Kaskada (redosled/latencija) = korelacija (inferirana propagacija).\n")

    # 6 — širina operacije (K1–K8)
    ro, tg = REGIONAL_OPS or {}, TACTICAL_GROUPS or {}
    ss, mp = SYSTEM_SURVEILLANCE or {}, MULTIPLATFORM or {}
    vk = VOTER_KURIR or {}
    if ro or tg or ss or mp:
        a("## 6. Širina operacije (platforme, regioni, nadzor)\n")
        if ro.get("countries"):
            cg = next((c for c in ro["countries"] if c["country"] == "CRNA GORA"), {})
            bih = next((c for c in ro["countries"] if c["country"] == "BIH"), {})
            px = ro.get("proxy", {})
            a(f"- **Prekogranično (K1):** CG {_fmt(cg.get('votes',0))} + BiH {_fmt(bih.get('votes',0))} "
              f"glasova. Proxy mreža: {px.get('total','?')} servera ({px.get('distinct_ip','?')} IP) "
              f"— svi za **vijesti.me**.")
        if vk.get("accounts_total"):
            a(f"- **Kurir/relay nalozi (K2):** {_fmt(vk['accounts_total'])} naloga (temp-mail) na "
              f"{vk.get('machines_matched','?')} mašina ({vk.get('machines_foreign','?')} strano) — "
              f"FK na voter_racunari. (Lozinke se ne izlažu; „kurir“≠Kurir.rs.)")
        if (VOTER_CUSTOM or {}).get("actions"):
            a(f"- **Headless injekcija (K3):** {len((VOTER_CUSTOM or {})['actions'])} custom akcija sa "
              f"sirovim JS/XPath (document.evaluate, scrollIntoView, click, FormData) na "
              f"Kurir/RTCG/Avaz/Progress.rs. (Tajne u kodu redigovane.)")
        if tg.get("categories"):
            tiktok = next((c for c in tg["categories"] if "TikTok" in c["category"]), {})
            a(f"- **Taktičke grupe (K4):** {tg.get('groups_total','?')} internih grupa / "
              f"{_fmt(tg.get('memberships_total',0))} članstava — TikTok divizija "
              f"({tiktok.get('members','?')} članova, abecedna podela), Voter admini, Hit Tvit, Nadzor.")
        if ss.get("inspector"):
            insp, dev, sms = ss["inspector"], ss.get("devices", {}), ss.get("sms", {})
            a(f"- **Nadzor operatera (K5–K7):** F12-telemetrija {insp.get('records','?')} zapisa u "
              f"prozoru {insp.get('from','?')[:10]}–{insp.get('to','?')[:10]} (korelacija s događajem); "
              f"{_fmt(dev.get('records',0))} uređaja (Android dominira, {dev.get('operators_5plus_devices','?')} "
              f"op sa 5+ uređaja); SMS gateway „Internet Tim“ {_fmt(sms.get('messages',0))} poruka "
              f"(2FA; telefoni maskirani).")
        if mp.get("platforms"):
            a(f"- **Multi-platformski arsenal (K8):** {_fmt(mp.get('total_accounts',0))} naloga na "
              f"{len(mp['platforms'])} mreža; {_fmt(mp.get('operators_3plus_networks',0))} operatera "
              f"pokriva 3+ mreže. 15 kategorija dežurstava (Twitter/IG/FB/Telegram/Sajtovi/Voter).")
        a("")

    a("---\n")
    a("*Detaljni moduli: `docs/analiza_direktiva.md`, `docs/analiza_koordinatora.md`, "
      "`docs/analiza_kaskade.md`, `docs/komandna_odgovornost_i_pravni_osnov.md`, "
      "`docs/voter_kladionice_infrastruktura.md`, `docs/vlasnicki_profil_kladionica.md`, "
      "`docs/regionalne_operacije_cg_bih.md`, `docs/takticke_grupe_i_divizije.md`, "
      "`docs/nadzor_operatera.md`, `docs/multiplatform_arsenal.md`.*")
    return "\n".join(L)


@app.get("/api/export/investigation_dossier")
def export_investigation_dossier():
    """Generiše i vraća kompletan istraživački dosije (Markdown, download)."""
    md = _build_dossier()
    fname = f"cacix_dosije_{datetime.now().strftime('%Y%m%d')}.md"
    return Response(content=md, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/api/regional_operations")
def regional_operations():
    """KORAK 1: prekogranične operacije (CG/BiH) + proxy mreža (133 za vijesti.me).
    Glasovi po državi/portalu iz izvestaj_voter (agregat; država izvedena iz portala)."""
    return REGIONAL_OPS or {"countries": [], "portals": [], "proxy": {}}


@app.get("/api/voter_kurir")
def voter_kurir():
    """KORAK 2: kurir/relay nalozi ↔ mašine (voter_kurir_nalozi→voter_racunari).
    FER PLAY: bez lozinki; „kurir“ nije Kurir.rs."""
    return VOTER_KURIR or {}


@app.get("/api/voter_custom")
def voter_custom():
    """KORAK 3: headless JS/XPath custom akcije (tajne redigovane)."""
    return VOTER_CUSTOM or {}


@app.get("/api/tactical_groups")
def tactical_groups():
    """KORAK 4: taktičke grupe/divizije (TikTok, Voter admini, Hit Tvit, Nadzor)."""
    return TACTICAL_GROUPS or {"groups": [], "categories": []}


@app.get("/api/system_surveillance")
def system_surveillance():
    """KORACI 5–7: nadzor operatera — F12 inspector, uređaji (otisak), SMS gateway.
    FER PLAY: telefoni/2FA kodovi maskirani; vremenska poklapanja = korelacija."""
    return SYSTEM_SURVEILLANCE or {"inspector": {}, "devices": {}, "sms": {}}


@app.get("/api/multiplatform_stats")
def multiplatform_stats():
    """KORAK 8: arsenal preko 6 platformi (51k+ naloga), unakrsna matrica, 15 dežurstava."""
    return MULTIPLATFORM or {"platforms": [], "coverage": []}


@app.get("/api/shift_chat")
def shift_chat():
    """Operativni chat / dnevnik dežurstava: vodeći supervizori, taksonomija poruka
    (primopredaja/kontrola/brisanje), satnica, verbatim raporti i nalozi za brisanje.
    FER PLAY: interni operativni logovi realnih ljudi (operateri)."""
    return SHIFT_CHAT or {"supervisors": [], "taxonomy": {}, "hours": [], "samples": {}}


@app.get("/api/gamification")
def gamification():
    """Partijska ekonomija: vrednost bodova po akciji (quote/reply/lajk/komentar),
    kvote/timski bodovi, i top „udarnici" po ukupnim bodovima + bihevioralna uloga."""
    return GAMIFICATION or {"points_per_action": [], "leaderboard": [], "by_opstina": []}


@app.get("/api/voter_timing")
def voter_timing():
    """Cirkadijalna analiza voter glasanja: satnica (overall + po državi mašine:
    Srbija vs strano/Afrika), noćni udeo (00–08h = lokal zaključan), latencija.
    Odgovara na: da li su mašine radile samo dok je lokal otvoren ili 24/7."""
    return VOTER_TIMING or {}


@app.get("/api/cascade")
def cascade():
    """Vremenska kaskada: SS/ČET direktiva → teren (okruzi). SS prioritet, vrh
    koplja (prvi reagent), ritam po satu, mesečni timeline, izdavač→okrug.
    FER PLAY: redosled/latencija = korelacija (inferirana propagacija), ne dokaz."""
    return CASCADE or {"ss_priority": {}, "first_mover_all": [], "first_mover_ss": [],
                       "hour_of_day": {}, "timeline": [], "issuer_okrug": []}


@app.get("/api/coordinators")
def coordinators():
    """Hijerarhija koordinatora (Region→Okrug→Opština) + raspon kontrole
    (operateri/centroidi/komanda/SS/🎰) i nalaz komanda-vs-izvršenje.
    FER PLAY: raspon = geografska nadležnost, ne dokaz pojedinačnog naređenja."""
    return COORDINATORS or {"tree": [], "levels": {}, "command_vs_execution": {}}


@app.get("/api/taskmasters")
def taskmasters(limit: int = Query(40, le=135)):
    """Kreatori zadataka za portale (komandni sloj) + koordinatorske uloge."""
    out = []
    for m in TASKMASTERS.get("masters", [])[:limit]:
        roles = []
        if m.get("ok_koord") or m.get("okrug_koord_tbl"):
            roles.append("okrug")
        if m.get("op_koord") or m.get("opstina_koord_tbl"):
            roles.append("opština")
        if m.get("reg_koord"):
            roles.append("region")
        out.append({
            "id": m["id"], "ime": m.get("ime") or f"#{m['id']}",
            "tasks": m["tasks"], "portals": m.get("portals"),
            "okrug": m.get("okrug"), "opstina": m.get("opstina"),
            "roles": roles, "centroid": m.get("centroid", False),
            "in_graph": m.get("in_graph", False), "max_org": m.get("max_org", 0),
        })
    return {"count": TASKMASTERS.get("count", 0),
            "coordinators": TASKMASTERS.get("coordinators", 0),
            "masters": out}


@app.get("/api/geo")
def geo():
    """Rangiranje okruga i opština po broju operatera i akcija (sve operatere),
    + broj kladionica (uplatnih mesta) po opštini iz voter infrastrukture."""
    with driver.session() as s:
        ok = {r["okrug"]: {"okrug": r["okrug"], "operators": r["ops"],
                           "actions": r["act"] or 0, "opstine": []}
              for r in s.run("""
                MATCH (o:Operator) WHERE o.okrug IS NOT NULL
                RETURN o.okrug AS okrug, count(o) AS ops, sum(o.actions) AS act
              """)}
        for r in s.run("""
            MATCH (o:Operator) WHERE o.okrug IS NOT NULL AND o.opstina IS NOT NULL
            RETURN o.okrug AS okrug, o.opstina AS opstina,
                   count(o) AS ops, sum(o.actions) AS act
        """):
            if r["okrug"] in ok:
                ok[r["okrug"]]["opstine"].append(
                    {"opstina": r["opstina"], "operators": r["ops"],
                     "actions": r["act"] or 0,
                     "shops": BETTING_BY_OPSTINA.get(r["opstina"], 0)})
    out = sorted(ok.values(), key=lambda x: -x["actions"])
    for o in out:
        o["opstine"].sort(key=lambda x: -x["actions"])
        o["shops"] = sum(x["shops"] for x in o["opstine"])  # kladionice po okrugu
    return {"okruzi": out}


@app.get("/api/stats")
def stats():
    with driver.session() as s:
        ops = s.run("MATCH (o:Operator) RETURN count(o)").single()[0]
        accs = s.run("MATCH (a:Account) RETURN count(a)").single()[0]
        co = s.run("MATCH ()-[c:CO_ACTED]->() RETURN count(c)").single()[0]
    return {"operators": ops, "accounts": accs, "co_acted": co}


# ───────────────────────── DOKUMENTACIJA (docs/*.md) ─────────────────────────
# Markdown studije iz repo-a se serviraju UI-ju ("📚 Dokumentacija" pogled) i
# čitaju se sa diska pri svakom zahtevu — izmena .md fajla je odmah vidljiva.

DOCS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs"))
ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# (fajl -> naslov, ikonica, kategorija, kratak opis). Redosled je redosled prikaza;
# fajlovi koji nisu navedeni dolaze na kraj u kategoriji „Ostalo".
DOCS_META = [
    ("docs/CACIX_MASTER_OSINT_WHITEPAPER.md", "Master OSINT Whitepaper", "📕", "Sinteza",
     "Sveobuhvatan publikabilni izveštaj: svi nalazi, pravni okvir i granice atribucije."),
    ("docs/ISTRAZIVACKI_DOSIJE_CACIX.md", "Istraživački dosije", "📑", "Sinteza",
     "Automatski generisan dosije iz žive baze (isti sadržaj kao dugme „Dosije“)."),

    ("docs/analiza_direktiva.md", "Analiza direktiva", "📋", "Komanda",
     "Taksonomija smernica, lanac direktiva→meta→reakcija, centralni SS/ČET izvor."),
    ("docs/analiza_koordinatora.md", "Analiza koordinatora", "🏛", "Komanda",
     "Hijerarhija Region→Okrug→Opština i nalaz „komanda ≠ izvršenje“."),
    ("docs/analiza_kaskade.md", "Vremenska kaskada", "⏱", "Komanda",
     "SS prioritet (17,6% brže), vrh koplja po okruzima, prekoregionalni tok."),
    ("docs/analiza_komanda_i_voter.md", "Komanda i voter", "⚖", "Komanda",
     "Task-masteri, voter privilegije i veza komandnog sloja sa glasanjem."),
    ("docs/komandna_odgovornost_i_pravni_osnov.md", "Komandna odgovornost", "§", "Komanda",
     "Pravni osnov i granice atribucije (šta se sme, a šta ne sme tvrditi)."),
    ("docs/dnevnik_smena_i_kontrola.md", "Dnevnik smena i kontrola", "💬", "Komanda",
     "Interni chat smena: primopredaja, kontrola kvaliteta, krizno brisanje."),
    ("docs/gamifikacija_i_kvote.md", "Gamifikacija i kvote", "🎯", "Komanda",
     "Partijska ekonomija bodova: quote 4,59 > reply 3,19 > rt 1,59 > lajk 1,49."),

    ("docs/voter_kladionice_infrastruktura.md", "Voter ↔ kladionice", "🎰", "Voter infrastruktura",
     "Terminali uplatnih mesta u Srbiji i afričke franšize; GeoIP i ASN otisak."),
    ("docs/vlasnicki_profil_kladionica.md", "Vlasnički profil kladionica", "🏢", "Voter infrastruktura",
     "Korporativni tragovi brendova u `vr_naziv_ss` (bez tvrdnji o vlasništvu)."),
    ("docs/voter_mehanizam_kurir_custom.md", "Mehanizam: kurir i custom", "⚙", "Voter infrastruktura",
     "Relay nalozi i headless JS/XPath injekcija (tajne redigovane)."),
    ("docs/regionalne_operacije_cg_bih.md", "Regionalne operacije CG/BiH", "📡", "Voter infrastruktura",
     "Prekogranični voter (CG 11,5M + BiH 6,1M) i proxy mreža."),

    ("docs/takticke_grupe_i_divizije.md", "Taktičke grupe i divizije", "👥", "Operativa",
     "30 grupa / 1.232 članstva: TikTok divizija, Voter admini, Hit Tvit, Nadzor."),
    ("docs/nadzor_operatera.md", "Nadzor operatera", "🕵️", "Operativa",
     "F12 telemetrija, 29.682 uređaja, SMS „Internet Tim“ (2FA, maskirano)."),
    ("docs/multiplatform_arsenal.md", "Multiplatformski arsenal", "🌐", "Operativa",
     "51.703 naloga na 6 mreža; 7.178 operatera na 3+ mreže."),

    ("README.md", "README — izgradnja od nule", "🚀", "Projekat",
     "Instalacija, uvoz baze, gradnja grafa i pokretanje (samo kod + SQLite)."),
    ("AGENTS.md", "AGENTS.md — orijentir", "🧭", "Projekat",
     "Arhitektura, heuristike, definicije metrika, pravila rukovanja podacima."),
]
_DOCS_BY_REL = {rel: (title, icon, cat, desc) for rel, title, icon, cat, desc in DOCS_META}


def _docs_index():
    """Lista dostupnih dokumenata (samo oni koji stvarno postoje na disku)."""
    seen, out = set(), []
    for rel, title, icon, cat, desc in DOCS_META:
        p = os.path.join(ROOT_DIR, rel)
        if not os.path.isfile(p):
            continue
        seen.add(os.path.normpath(p))
        st = os.stat(p)
        out.append({"id": rel, "title": title, "icon": icon, "category": cat,
                    "description": desc, "bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    # fajlovi iz docs/ koji nisu u DOCS_META — da nijedan dokument ne „nestane"
    if os.path.isdir(DOCS_DIR):
        for fn in sorted(os.listdir(DOCS_DIR)):
            p = os.path.normpath(os.path.join(DOCS_DIR, fn))
            if not fn.endswith(".md") or p in seen:
                continue
            st = os.stat(p)
            out.append({"id": f"docs/{fn}", "title": fn[:-3].replace("_", " "), "icon": "📄",
                        "category": "Ostalo", "description": "", "bytes": st.st_size,
                        "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    return out


def _docs_resolve(doc_id):
    """Mapira id iz zahteva na putanju — SAMO unutar docs/ ili na .md u korenu."""
    rel = os.path.normpath((doc_id or "").lstrip("/"))
    if rel.startswith("..") or os.path.isabs(rel) or not rel.endswith(".md"):
        return None
    p = os.path.normpath(os.path.join(ROOT_DIR, rel))
    in_docs = p.startswith(DOCS_DIR + os.sep)
    in_root = os.path.dirname(p) == ROOT_DIR and rel in _DOCS_BY_REL
    if not (in_docs or in_root) or not os.path.isfile(p):
        return None
    return p


@app.get("/api/docs")
def docs_list():
    """Indeks dokumentacije za „📚 Dokumentacija" pogled u UI-ju."""
    return {"docs": _docs_index()}


@app.get("/api/docs/{doc_id:path}")
def docs_get(doc_id: str):
    """Sirov Markdown jednog dokumenta (frontend ga renderuje)."""
    p = _docs_resolve(doc_id)
    if not p:
        return Response(content=json.dumps({"error": "nepoznat dokument"}),
                        media_type="application/json", status_code=404)
    with open(p, encoding="utf-8") as f:
        text = f.read()
    meta = _DOCS_BY_REL.get(os.path.normpath(doc_id), (os.path.basename(p), "📄", "Ostalo", ""))
    st = os.stat(p)
    return {"id": doc_id, "title": meta[0], "icon": meta[1], "category": meta[2],
            "description": meta[3], "markdown": text, "bytes": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
