"""
Cacix — API za graf-explorer povezanih bot-naloga.

Operaterska mreža (Operator, Account; CONTROLS, CO_ACTED) živi u Neo4j.
Amplifikacija (operater -> meta) se računa uživo iz Postgres šeme `progress`.
Node id šema za frontend: 'op:<id>', 'acc:<id>', 'tgt:<handle>'.
"""
import math
import os

from fastapi import FastAPI, Query
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
    RETURN o AS node, collect(DISTINCT {{other:p.id, shared:c.shared}}) AS edges
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
                              "type": ltype, "shared": e["shared"]})
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
                "RETURN p, c.shared AS shared ORDER BY c.shared DESC LIMIT $lim",
                id=op_id, lim=co_limit):
                p = dict(r["p"])
                nodes.append(op_node(p))
                a, b = sorted((op_id, p["id"]))
                links.append({"source": f"op:{a}", "target": f"op:{b}",
                              "type": "co_commented", "shared": r["shared"]})
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
                "RETURN p, c.shared AS shared ORDER BY c.shared DESC LIMIT $lim",
                id=op_id, lim=co_limit):
                p = dict(r["p"])
                nodes.append(op_node(p))
                a, b = sorted((op_id, p["id"]))
                links.append({"source": f"op:{a}", "target": f"op:{b}",
                              "type": "co_acted", "shared": r["shared"]})
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
    return {
        "hours": hours,
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
    "entropy": "hour_entropy", "dup": "dup_ratio",
}


@app.get("/api/behavior_top")
def behavior_top(layer: str = "twitter", limit: int = Query(40, le=150),
                 metric: str = "auto"):
    """Operateri rangirani po izabranoj bihevioralnoj metrici + veze među njima.
    metric: auto | night | short_lat | entropy | dup"""
    prop = BEHAV_METRIC.get(metric, "auto_score")
    rel, ltype = (("CO_COMMENTED", "co_commented") if layer == "comments"
                  else ("CO_ACTED", "co_acted"))
    q = f"""
    MATCH (o:Operator) WHERE o.{prop} > 0
    WITH o ORDER BY o.{prop} DESC LIMIT $limit
    WITH collect(o) AS top
    UNWIND top AS o
    OPTIONAL MATCH (o)-[c:{rel}]-(p:Operator) WHERE p IN top
    RETURN o AS node, collect(DISTINCT {{other:p.id, shared:c.shared}}) AS edges
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
                              "type": ltype, "shared": e["shared"]})
    return {"nodes": nodes, "links": links}


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
    WITH top, mss, o, collect(DISTINCT {id:p.id, s:c.shared}) AS twe
    OPTIONAL MATCH (o)-[d:CO_COMMENTED]-(r:Operator) WHERE r IN top
    RETURN o AS node, twe, collect(DISTINCT {id:r.id, s:d.shared}) AS cce,
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
                                  "type": etype, "shared": e["s"]})
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
    RETURN o AS node, collect(DISTINCT {{other:p.id, shared:c.shared}}) AS edges
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
                              "type": ltype, "shared": e["shared"]})
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


@app.get("/api/stats")
def stats():
    with driver.session() as s:
        ops = s.run("MATCH (o:Operator) RETURN count(o)").single()[0]
        accs = s.run("MATCH (a:Account) RETURN count(a)").single()[0]
        co = s.run("MATCH ()-[c:CO_ACTED]->() RETURN count(c)").single()[0]
    return {"operators": ops, "accounts": accs, "co_acted": co}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
