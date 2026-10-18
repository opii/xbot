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

    print("Računanje farme (serverske mašine) + radnog vremena ...", flush=True)
    # farma = akcije preko namenske mašine (tuka_program_racunar);
    # radno vreme = pon–pet 08–15h; vikend = sub/ned.
    cur.execute("""
        SELECT tuka_korisnik_id, count(*) total,
               count(*) FILTER (WHERE tuka_program_racunar <> '') farm_n,
               mode() WITHIN GROUP (ORDER BY NULLIF(tuka_program_racunar, '')) machine,
               count(*) FILTER (WHERE extract(dow FROM tuka_datum::date) BETWEEN 1 AND 5
                                AND substr(tuka_vreme, 12, 2)::int BETWEEN 8 AND 15) work,
               count(*) FILTER (WHERE extract(dow FROM tuka_datum::date) IN (0, 6)) weekend
        FROM arhiva_twitter_unos_korisnici_akcije GROUP BY 1
    """)
    fw = {}
    for op, tot, fn, mach, work, wknd in cur.fetchall():
        tot = tot or 1
        fw[op] = (round(fn / tot, 4), mach, round(work / tot, 4), round(wknd / tot, 4))

    def archetype(work_pct, wknd, night):
        if work_pct >= 0.75 and wknd < 0.1:
            return "Kancelarijski"
        if night >= 0.25:
            return "Noćna smena"
        if wknd >= 0.40:
            return "Vikend"
        return "Mešovit / 24-7"

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
        farm_r, mach, work_pct, wknd = fw.get(op, (0.0, None, 0.0, 0.0))
        rows.append({"id": op, "auto": round(score, 4), "night": round(night, 4),
                     "ent": round(ent, 4), "sl": round(sl, 4),
                     "farm": farm_r, "mach": mach, "work": work_pct, "wknd": wknd,
                     "arch": archetype(work_pct, wknd, night)})

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

    print("Računanje regularnosti ritma (razmaci između akcija) ...", flush=True)
    # reg = m/(m+s) razmaka između uzastopnih akcija; 1 = savršeno pravilno (bot)
    cur.execute("""
        WITH ordered AS (
            SELECT tuka_korisnik_id op, tuka_vreme::timestamp t,
                   lag(tuka_vreme::timestamp) OVER
                       (PARTITION BY tuka_korisnik_id ORDER BY tuka_vreme) prev
            FROM arhiva_twitter_unos_korisnici_akcije),
        gaps AS (SELECT op, extract(epoch FROM (t - prev)) g
                 FROM ordered WHERE prev IS NOT NULL AND t > prev)
        SELECT op, avg(g) m, stddev_pop(g) s, count(*) n
        FROM gaps GROUP BY op HAVING count(*) >= 30
    """)
    reg_rows = [{"id": op, "reg": round(float(m) / (float(m) + float(s)), 4)
                 if (m is not None and s is not None and (m + s)) else 0.0}
                for op, m, s, n in cur.fetchall()]

    print("Određivanje uloga (dominantni tip akcije) ...", flush=True)
    cur.execute("""
        SELECT tuka_korisnik_id,
               count(*) FILTER (WHERE tuka_akcija IN (0,1)) amp,
               count(*) FILTER (WHERE tuka_akcija IN (2,3)) resp,
               count(*) total
        FROM arhiva_twitter_unos_korisnici_akcije GROUP BY 1
    """)
    role_rows = []
    for op, amp, resp, tot in cur.fetchall():
        tot = tot or 1
        role = ("Odgovarač" if resp / tot > 0.5
                else "Pojačivač" if amp / tot > 0.8 else "Mešovit")
        role_rows.append({"id": op, "role": role})

    print("Računanje udela duplikata komentara ...", flush=True)
    cur.execute("""
        SELECT vkk_korisnik_id, count(*), count(DISTINCT vkk_komentar)
        FROM arhiva_vesti_korisnici_komentari
        WHERE vkk_simulacija = 0 AND vkk_komentar <> ''
        GROUP BY 1
    """)
    dup_rows = [{"id": op, "dup": round(1 - (dist / tot), 4) if tot else 0.0}
                for op, tot, dist in cur.fetchall()]

    print("Računanje pseudonima (različita imena u komentarima) ...", flush=True)
    cur.execute("""
        SELECT vkk_korisnik_id, count(DISTINCT vkk_autor)
        FROM arhiva_vesti_korisnici_komentari
        WHERE vkk_simulacija = 0 AND vkk_autor <> ''
        GROUP BY 1
    """)
    pseudo_rows = [{"id": op, "ps": n} for op, n in cur.fetchall()]

    print("Računanje toksičnosti (jurišni odredi) ...", flush=True)
    # Napad = odgovor (akcija=2) na opozicionu metu ILI uz agresivnu direktivu,
    # PLUS komentar na kritičkom portalu. (NB: generičko „odgovaramo" se NE broji
    # kao agresivno — inače bi skoro svi odgovori bili toksični; primeri iz baze
    # #2656/#2649 se poklapaju sa ovom definicijom.)
    OPP = ['marinikatepic', 'kpromeni', 'onlinedanas', 'n1srbija', 'novarsonline',
           'gjesic', 'slobodaipravda', 'slobageorgiev', 'zdravkoponos', 'miranpogacar',
           'narodnipokrets', 'dragandjilas']
    AGG = r'brutalno|zezamo|sprdamo|hejt|lazov|resavamo|pukli'
    CRIT = ['n1info.rs', 'danas.rs', 'nova.rs', 'juznevesti.com', 'vreme.com', 'radar.rs']
    H = "lower(split_part(split_part(t.tu_link_tvita, '.com/', 2), '/', 1))"
    cur.execute(f"""
        SELECT a.tuka_korisnik_id, count(*) AS total_tw,
               count(*) FILTER (WHERE a.tuka_akcija=2
                   AND (t.tu_smernica ~* %s OR {H} = ANY(%s))) AS toxic_tw
        FROM arhiva_twitter_unos_korisnici_akcije a
        JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
        GROUP BY 1
    """, (AGG, OPP))
    tw = {op: (tt, tx) for op, tt, tx in cur.fetchall()}
    cur.execute("""
        SELECT v.vkk_korisnik_id, count(*) AS total_cm,
               count(*) FILTER (WHERE u.vu_portal = ANY(%s)) AS crit_cm
        FROM arhiva_vesti_korisnici_komentari v
        JOIN arhiva_vesti_unos u ON u.vu_id = v.vkk_vest_id
        WHERE v.vkk_simulacija = 0
        GROUP BY 1
    """, (CRIT,))
    cm = {op: (tt, cc) for op, tt, cc in cur.fetchall()}

    def tox_level(score, attacks):
        if score >= 0.40 or attacks >= 300:
            return "Ekstremna (Jurišnik)"
        if score >= 0.20:
            return "Visoka"
        if score >= 0.08:
            return "Umerena"
        return "Netoksičan (Pojačivač)"

    tox_rows = []
    for op in set(tw) | set(cm):
        ttw, txw = tw.get(op, (0, 0))
        tcm, ccm = cm.get(op, (0, 0))
        attacks = txw + ccm
        total = (ttw + tcm) or 1
        conf = min(1.0, attacks / 40.0)
        score = round((attacks / total) * conf, 4)
        tox_rows.append({"id": op, "sc": score, "lv": tox_level(score, attacks),
                         "at": attacks})

    print("Računanje tretmana portala (Infiltrator vs Podrška) ...", flush=True)
    # infiltrator_ratio = kritički / (kritički + tabloid) komentari.
    # Kritički mediji: prolaznost ~0,9% (99% blokade); tabloidi ~32%+.
    TAB = ['informer.rs', 'alo.rs', 'kurir.rs', 'novosti.rs']
    cur.execute("""
        SELECT v.vkk_korisnik_id,
               count(*) FILTER (WHERE u.vu_portal = ANY(%s)) crit,
               count(*) FILTER (WHERE u.vu_portal = ANY(%s)) tab
        FROM arhiva_vesti_korisnici_komentari v
        JOIN arhiva_vesti_unos u ON u.vu_id = v.vkk_vest_id
        WHERE v.vkk_simulacija = 0 AND u.vu_portal = ANY(%s)
        GROUP BY 1
    """, (CRIT, TAB, CRIT + TAB))
    portal_rows = []
    for op, crit, tab in cur.fetchall():
        tot = crit + tab
        if tot < 20:
            role, inf = None, 0.0
        else:
            inf = round(crit / tot, 4)
            role = ("Infiltrator" if inf >= 0.6 else
                    "Podrška" if inf <= 0.3 else "Mešovit (portali)")
        portal_rows.append({"id": op, "inf": inf, "role": role,
                            "crit": crit, "tab": tab})

    print("Računanje udela deljenih šablona (konzerviran tekst) ...", flush=True)
    # template_frac = udeo komentara operatera čiji tekst koristi >=3 operatera
    cur.execute(r"""
        WITH norm AS (
            SELECT vkk_korisnik_id op,
                   lower(btrim(regexp_replace(vkk_komentar, '\s+', ' ', 'g'))) t
            FROM arhiva_vesti_korisnici_komentari
            WHERE vkk_simulacija = 0 AND length(vkk_komentar) >= 15),
        cnt AS (SELECT t, count(DISTINCT op) nop FROM norm GROUP BY t)
        SELECT n.op, count(*) total, count(*) FILTER (WHERE c.nop >= 3) shared_n
        FROM norm n JOIN cnt c USING(t) GROUP BY n.op
    """)
    tpl_rows = [{"id": op, "tf": round(sh / tot, 4) if tot else 0.0}
                for op, tot, sh in cur.fetchall()]

    print("Računanje CO_TEMPLATE veza (deljeni šabloni) ...", flush=True)
    cur.execute(r"""
        WITH norm AS (
            SELECT DISTINCT vkk_korisnik_id op,
                   lower(btrim(regexp_replace(vkk_komentar, '\s+', ' ', 'g'))) t
            FROM arhiva_vesti_korisnici_komentari
            WHERE vkk_simulacija = 0 AND length(vkk_komentar) >= 15),
        tpl AS (SELECT t FROM norm GROUP BY t HAVING count(*) BETWEEN 3 AND 60),
        ot AS (SELECT n.op, n.t FROM norm n JOIN tpl USING(t))
        SELECT x.op, y.op, count(*) shared
        FROM ot x JOIN ot y ON x.t = y.t AND x.op < y.op
        GROUP BY x.op, y.op HAVING count(*) >= 3
    """)
    ct_rows = [{"a": r[0], "b": r[1], "shared": r[2]} for r in cur.fetchall()]

    print(f"Upis auto_score za {len(rows):,} operatera ...", flush=True)
    with drv.session() as s:
        s.run("MATCH (o:Operator) SET o.auto_score=0, o.dup_ratio=0, o.lead_score=0, "
              "o.lead_n=0, o.farm_ratio=0, o.farm_machine=null, o.work_hours_pct=0, "
              "o.weekend_ratio=0, o.shift_archetype=null")
        for i in range(0, len(rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id})
                SET o.auto_score=r.auto, o.night_ratio=r.night,
                    o.hour_entropy=r.ent, o.short_lat_frac=r.sl,
                    o.farm_ratio=r.farm, o.farm_machine=r.mach,
                    o.work_hours_pct=r.work, o.weekend_ratio=r.wknd,
                    o.shift_archetype=r.arch
            """, rows=rows[i:i + 5000])
        for i in range(0, len(dup_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id}) SET o.dup_ratio = r.dup
            """, rows=dup_rows[i:i + 5000])
        s.run("MATCH (o:Operator) SET o.pseudonyms = 0")
        for i in range(0, len(pseudo_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id}) SET o.pseudonyms = r.ps
            """, rows=pseudo_rows[i:i + 5000])
        s.run("MATCH (o:Operator) SET o.toxicity_score=0, o.toxicity_level=null, o.toxic_attacks=0")
        for i in range(0, len(tox_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id})
                SET o.toxicity_score=r.sc, o.toxicity_level=r.lv, o.toxic_attacks=r.at
            """, rows=tox_rows[i:i + 5000])
        print(f"  toksičnost: {sum(1 for r in tox_rows if r['at'] >= 300):,} jurišnika "
              f"(≥300 napada)", flush=True)
        s.run("MATCH (o:Operator) SET o.infiltrator_ratio=0, o.portal_role=null, "
              "o.crit_comments=0, o.tab_comments=0")
        for i in range(0, len(portal_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id})
                SET o.infiltrator_ratio=r.inf, o.portal_role=r.role,
                    o.crit_comments=r.crit, o.tab_comments=r.tab
            """, rows=portal_rows[i:i + 5000])
        print(f"  portali: {sum(1 for r in portal_rows if r['role']=='Infiltrator'):,} "
              f"Infiltratora", flush=True)
        for i in range(0, len(lead_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id}) SET o.lead_score=r.lead, o.lead_n=r.ln
            """, rows=lead_rows[i:i + 5000])
        s.run("MATCH (o:Operator) SET o.template_frac = 0")
        for i in range(0, len(tpl_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (o:Operator {id: r.id}) SET o.template_frac = r.tf
            """, rows=tpl_rows[i:i + 5000])
        s.run("MATCH ()-[c:CO_TEMPLATE]-() DELETE c")
        for i in range(0, len(ct_rows), 5000):
            s.run("""
                UNWIND $rows AS r
                MATCH (a:Operator {id: r.a}), (b:Operator {id: r.b})
                MERGE (a)-[c:CO_TEMPLATE]-(b) SET c.shared = r.shared
            """, rows=ct_rows[i:i + 5000])
        print(f"  template_frac: {len(tpl_rows):,} op · CO_TEMPLATE: {len(ct_rows):,} veza", flush=True)
        s.run("MATCH (o:Operator) SET o.reg_score=0, o.role=null")
        for i in range(0, len(reg_rows), 5000):
            s.run("UNWIND $rows AS r MATCH (o:Operator {id:r.id}) SET o.reg_score=r.reg", rows=reg_rows[i:i + 5000])
        for i in range(0, len(role_rows), 5000):
            s.run("UNWIND $rows AS r MATCH (o:Operator {id:r.id}) SET o.role=r.role", rows=role_rows[i:i + 5000])
        print(f"  reg_score: {len(reg_rows):,} · uloge: {len(role_rows):,}", flush=True)
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
