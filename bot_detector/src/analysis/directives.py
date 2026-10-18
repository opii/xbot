#!/usr/bin/env python3
"""
Analiza direktiva (smernica) — šta se tačno NAREĐUJE operaterima i kako reaguju.

Dve kolone direktiva:
  - tviter zadaci:  arhiva_twitter_unos.tu_smernica   (498k nepraznih, 2.195 distinct)
  - vesti/komentari: arhiva_vesti_unos.vu_smernica     (62k nepraznih, 3.578 distinct)

Radi tri stvari:

1) TAKSONOMIJA — svaku direktivu svrsta po dimenzijama (klasifikacija na
   NORMALIZOVANOM tekstu: lowercase + skidanje dijakritika + ćirilica→latinica):
     - action : koja akcija se traži (lajk/retvit/citat/odgovor/komentar/deljenje)
     - tone   : napad vs odbrana/podrška vs neutralno (samo akcija)
     - source : odakle dolazi direktiva — SS (super specijal) / ČET (Šefov video iz
                četa) / ŠEF (lider) / AUTOMATIKA / bez naznake
     - cross  : nalog za cross-platform amplifikaciju (delimo na svim mrežama/story)

2) LANAC direktiva → meta → reakcija:
     - tviter: ton direktive → klasa mete (opozicija/režim/ostalo) + izmerena
       reakcija (medijana latencije, udeo u prvih 10 min). Ton koristi ISTI raw
       AGG/SUP regex kao toksičnost (konzistentno sa jurišnim odredima).
     - vesti: ton direktive → klasa portala (kritički/tabloid) → prolaznost
       moderacije (objavljeni/prijavljeni komentari).

3) KOMANDNI IZVOR (SS/ČET/ŠEF) — zaseban nalaz: ko UNOSI direktive sa oznakom
   „super specijal"/„iz četa" (centralni izvor iznad koordinatora), njihove uloge
   i preklapanje sa grafom (centroidi). FER PLAY: kreator u bazi = ko je zadatak
   UNEO u sistem; „Šef/čet" u tekstu referišu na uzvodnog čoveka-lidera koji NIJE
   nužno red u bazi — NE izjednačavamo kreatora sa „Šefom".

Izlaz: data/geo/directives.json  (čita ga /api/directives → UI pogled „📋 Direktive").
Pokretanje:  ./venv/bin/python src/analysis/directives.py
"""
import json
import os
import re
import unicodedata

import psycopg2
from neo4j import GraphDatabase

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO = ("bolt://localhost:7687", ("neo4j", "bot_password"))
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "directives.json")

# --- handle / portal skupovi (isti kao u toksičnosti/portal tretmanu) ----------
OPP = ['marinikatepic', 'kpromeni', 'onlinedanas', 'n1srbija', 'novarsonline',
       'gjesic', 'slobodaipravda', 'slobageorgiev', 'zdravkoponos', 'miranpogacar',
       'narodnipokrets', 'dragandjilas']
PRO = ['sns_srbija', 'avucic', 'milos_vucevic', 'buducnostsrbijeav', 'vucic',
       'predsednikrs', 'sinisamali', 'anabrnabic', 'srbijanavidiku']
# raw (ne-normalizovani) regexi — rade uz Postgres ~* nad sirovim tekstom
AGG_RAW = r'brutalno|zezamo|sprdamo|hejt|lazov|resavamo|pukli'               # napad
SUP_RAW = r'branim|hvalim|podr[sš]k|slavim|[cč]estit|cuvamo|čuvamo'          # odbrana/podrška

# --- normalizacija: lower + ćirilica→latinica + skidanje dijakritika -----------
_CYR = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ђ': 'dj', 'е': 'e', 'ж': 'z',
    'з': 'z', 'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n',
    'њ': 'nj', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'ћ': 'c', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'c', 'џ': 'dz', 'ш': 's',
}


def norm(s):
    if not s:
        return ""
    s = s.lower()
    s = "".join(_CYR.get(ch, ch) for ch in s)
    # skini kombinujuće dijakritike (š→s, č/ć→c, ž→z) preko NFKD
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("đ", "dj")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- klasifikatori (na normalizovanom tekstu) ----------------------------------
def classify_action(n, akcija_code=None):
    # tviter: akcija_code 0=lajk 1=rt 2=odgovor 3=citat je POUZDAN izvor
    if akcija_code is not None:
        return {0: "lajk", 1: "retvit", 2: "odgovor", 3: "citat"}.get(akcija_code, "ostalo")
    if re.search(r"\bkv\b|kvot|quote|citat", n):
        return "citat"
    if re.search(r"\brt\b|retvit|retweet|\bsvi rt\b", n):
        return "retvit"
    if re.search(r"\bfv\b|lajk|\blike\b|svidj|svi?dja", n):
        return "lajk"
    if re.search(r"delim|deli |seruj|share|story|na svim mrez|mreza", n):
        return "deljenje"
    if re.search(r"komentar|komentem|komentaris", n):
        return "komentar"
    if re.search(r"odgovor|odgovara|\breply\b|\bog\b", n):
        return "odgovor"
    return "ostalo"


def classify_tone(n):
    if re.search(r"brutalno|zezamo|sprdamo|sprd|hejt|resavamo hejter|resavamo"
                 r"|pukli|pukl |lazov|razbij|rafal|napad|izmasakr|unist|raspal", n):
        return "napad"
    if re.search(r"branim|hvalim|podrsk|slavim|cestit|cuvamo|volimo", n):
        return "odbrana"
    return "neutral"


def classify_source(n, automatika=False):
    if automatika:
        return "automatika"
    if re.search(r"super ?spec|\biz ss\b|\bpo ss\b|smernic\w* .*\bss\b|\bss smernic", n):
        return "SS"
    if re.search(r"iz cet|\bceta\b|video iz cet|iz cheta", n):
        return "CET"
    if re.search(r"\bsef\b|sefov|\bsefa\b|sef sns", n):
        return "SEF"
    return "bez"


def has_cross(n):
    return bool(re.search(r"delim|seruj|na svim mrez|svim mrez|story|okacite link"
                          r"|kopirajte link|potvrdite da ste podel|deli(mo)? (video|link)"
                          r"|mreza|mreze", n))


def tally(rows, akcija_idx=None):
    """rows: lista (smernica, [akcija_code], [automatika]). Vrati zbirne brojače."""
    action, tone, source, cross, total = {}, {}, {}, 0, 0
    for r in rows:
        n = norm(r[0])
        if not n:
            continue
        total += 1
        ak = r[akcija_idx] if akcija_idx is not None else None
        auto = bool(r[-1]) if len(r) > 1 and akcija_idx is None else False
        a = classify_action(n, ak)
        t = classify_tone(n)
        s = classify_source(n, auto)
        action[a] = action.get(a, 0) + 1
        tone[t] = tone.get(t, 0) + 1
        source[s] = source.get(s, 0) + 1
        if has_cross(n):
            cross += 1
    return {"total": total, "by_action": action, "by_tone": tone,
            "by_source": source, "cross_platform": cross}


def ts_ok():
    return r"~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$'"


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    # =========================================================================
    # 1) TAKSONOMIJA
    # =========================================================================
    print("[1/4] Taksonomija direktiva ...", flush=True)
    cur.execute("SELECT tu_smernica, tu_akcija FROM arhiva_twitter_unos "
                "WHERE tu_smernica IS NOT NULL AND tu_smernica <> ''")
    tw_tax = tally(cur.fetchall(), akcija_idx=1)
    cur.execute("SELECT vu_smernica, vu_automatika_kreirala FROM arhiva_vesti_unos "
                "WHERE vu_smernica IS NOT NULL AND vu_smernica <> ''")
    nw_tax = tally(cur.fetchall())
    print(f"  tviter: {tw_tax['total']} direktiva  {tw_tax['by_tone']}")
    print(f"  vesti : {nw_tax['total']} direktiva  {nw_tax['by_tone']}")
    print(f"  izvor(tw): {tw_tax['by_source']}")
    print(f"  izvor(nw): {nw_tax['by_source']}")

    # mesečni trend (ton + izvor) — tviter
    def monthly(tbl, tcol, datecol, autocol=None):
        cur.execute(f"""
            SELECT substr({datecol},1,7) ym,
                   count(*) tot,
                   count(*) FILTER (WHERE {tcol} ~* %s) napad,
                   count(*) FILTER (WHERE {tcol} ~* %s) odbrana,
                   count(*) FILTER (WHERE {tcol} ~* 'super ?spec|iz ss|\\mss\\M') ss,
                   count(*) FILTER (WHERE {tcol} ~* 'iz cet|video iz cet|\\mceta\\M') cet
            FROM {tbl}
            WHERE {tcol} IS NOT NULL AND {tcol} <> '' AND {datecol} {ts_ok()}
            GROUP BY 1 ORDER BY 1
        """, (AGG_RAW, SUP_RAW))
        return [{"ym": r[0], "total": r[1], "napad": r[2], "odbrana": r[3],
                 "ss": r[4], "cet": r[5]} for r in cur.fetchall()]

    tw_month = monthly("arhiva_twitter_unos", "tu_smernica", "tu_kreirano_vreme")
    nw_month = monthly("arhiva_vesti_unos", "vu_smernica", "vu_vreme_kreiranja")

    # =========================================================================
    # 2) LANAC: ton → meta/portal → reakcija
    # =========================================================================
    print("[2/4] Lanac direktiva → meta → reakcija ...", flush=True)
    H = "lower(split_part(split_part(t.tu_link_tvita, '.com/', 2), '/', 1))"
    # tviter: ton × klasa mete + latencija/burst (jedan prolaz, raw regex)
    cur.execute(f"""
        WITH j AS (
          SELECT CASE WHEN t.tu_smernica ~* %s THEN 'napad'
                      WHEN t.tu_smernica ~* %s THEN 'odbrana'
                      ELSE 'neutral' END AS tone,
                 CASE WHEN {H} = ANY(%s) THEN 'opozicija'
                      WHEN {H} = ANY(%s) THEN 'rezim'
                      ELSE 'ostalo' END AS tgt,
                 EXTRACT(EPOCH FROM (a.tuka_vreme::timestamp
                         - t.tu_kreirano_vreme::timestamp)) AS lat
          FROM arhiva_twitter_unos_korisnici_akcije a
          JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
          WHERE a.tuka_akcija = 2
            AND a.tuka_vreme {ts_ok()}
            AND t.tu_kreirano_vreme {ts_ok()}
        )
        SELECT tone, tgt, count(*) n,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY lat) med_lat,
               avg((lat >= 0 AND lat <= 600)::int)::float burst10
        FROM j WHERE lat >= 0 AND lat <= 259200
        GROUP BY 1,2 ORDER BY 1,2
    """, (AGG_RAW, SUP_RAW, OPP, PRO))
    tw_chain = [{"tone": r[0], "target": r[1], "n": r[2],
                 "med_lat_s": round(float(r[3]), 1), "burst10": round(float(r[4]), 3)}
                for r in cur.fetchall()]

    # vesti: ton × klasa portala → prolaznost moderacije
    cur.execute("""
        SELECT CASE WHEN vu_portal ~* 'n1|nova|danas|juzne|vreme|radar' THEN 'kriticki'
                    WHEN vu_portal ~* 'informer|alo|kurir|novosti|pink|srbijadanas' THEN 'tabloid'
                    ELSE 'ostalo' END AS pcls,
               CASE WHEN vu_smernica ~* %s THEN 'napad'
                    WHEN vu_smernica ~* %s THEN 'odbrana'
                    ELSE 'neutral' END AS tone,
               count(*) tasks,
               sum(coalesce(vu_komentara_prijavljeno,0))::bigint prijav,
               sum(coalesce(vu_komentara_objavljeno,0))::bigint objav
        FROM arhiva_vesti_unos
        WHERE vu_smernica IS NOT NULL AND vu_smernica <> ''
        GROUP BY 1,2 ORDER BY 1,2
    """, (AGG_RAW, SUP_RAW))
    nw_chain = []
    for pcls, tone, tasks, prijav, objav in cur.fetchall():
        rate = round(objav / prijav, 4) if prijav else None
        nw_chain.append({"portal": pcls, "tone": tone, "tasks": tasks,
                         "prijavljeno": int(prijav), "objavljeno": int(objav),
                         "pass_rate": rate})

    # =========================================================================
    # 3) KOMANDNI IZVOR (SS/ČET/ŠEF) — ko unosi centralne direktive
    # =========================================================================
    print("[3/4] Komandni izvor (SS/ČET/ŠEF) ...", flush=True)
    SRC_SQL = ("count(*) FILTER (WHERE {c} ~* 'super ?spec|iz ss|\\mss\\M') ss, "
               "count(*) FILTER (WHERE {c} ~* 'iz cet|video iz cet|\\mceta\\M') cet, "
               "count(*) FILTER (WHERE {c} ~* '\\msef\\M|sefov|sef sns') sef")
    # tviter kreatori
    cur.execute(f"""
        SELECT t.tu_kreirano_korisnik_id id, count(*) tasks,
               {SRC_SQL.format(c='t.tu_smernica')}
        FROM arhiva_twitter_unos t
        WHERE t.tu_kreirano_korisnik_id IS NOT NULL
        GROUP BY 1
    """)
    issuers = {}
    for cid, tasks, ss, cet, sef in cur.fetchall():
        issuers[cid] = {"id": cid, "tw_tasks": tasks, "ss": ss, "cet": cet, "sef": sef,
                        "nw_tasks": 0}
    # vesti kreatori (spoji na isti korisnik_id)
    cur.execute(f"""
        SELECT v.vu_korisnik_id id, count(*) tasks,
               {SRC_SQL.format(c='v.vu_smernica')}
        FROM arhiva_vesti_unos v
        WHERE v.vu_korisnik_id IS NOT NULL
        GROUP BY 1
    """)
    for cid, tasks, ss, cet, sef in cur.fetchall():
        d = issuers.setdefault(cid, {"id": cid, "tw_tasks": 0, "ss": 0, "cet": 0,
                                     "sef": 0, "nw_tasks": 0})
        d["nw_tasks"] += tasks
        d["ss"] += ss; d["cet"] += cet; d["sef"] += sef
    for d in issuers.values():
        d["central"] = d["ss"] + d["cet"]          # SS+ČET = centralni izvor

    # obogati imenima/ulogama (samo oni koji imaju central>0 ili mnogo sef)
    cand = [d for d in issuers.values() if d["central"] > 0 or d["sef"] >= 50]
    ids = tuple(d["id"] for d in cand) or (0,)
    cur.execute("""
        SELECT k.k_id, NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'') ime,
               k.k_pozicija, o.o_naziv okrug, op.op_naziv opstina,
               kk.okrug_koordinator, kk.opstina_koordinator, kk.region_koordinator
        FROM korisnici k
        LEFT JOIN okrug o ON o.o_id = k.k_okrug
        LEFT JOIN opstina op ON op.op_id = k.k_opstina
        LEFT JOIN koordinatori_korisnici kk ON kk.korisnik_id = k.k_id
        WHERE k.k_id IN %s
    """, (ids,))
    meta = {r[0]: r for r in cur.fetchall()}
    for d in cand:
        m = meta.get(d["id"])
        d["ime"] = m[1] if m else None
        d["pozicija"] = m[2] if m else None
        d["okrug"] = m[3] if m else None
        d["opstina"] = m[4] if m else None
        d["coordinator"] = bool(m and (m[5] or m[6] or m[7])) if m else False

    # preklapanje sa grafom
    drv = GraphDatabase.driver(NEO[0], auth=NEO[1])
    with drv.session() as s:
        for d in cand:
            r = s.run("MATCH (o:Operator {id:$id}) RETURN o.tw_org AS tw, o.cc_org AS cc, "
                      "o.tw_organizer AS two, o.cc_organizer AS cco", id=d["id"]).single()
            d["max_org"] = round(max((r["tw"] or 0), (r["cc"] or 0)), 3) if r else 0
            d["centroid"] = bool(r and (r["two"] or r["cco"]))
    drv.close()

    cand.sort(key=lambda d: (d["central"], d["sef"]), reverse=True)
    ss_total = sum(d["ss"] for d in issuers.values())
    cet_total = sum(d["cet"] for d in issuers.values())
    sef_total = sum(d["sef"] for d in issuers.values())
    print(f"  SS direktiva: {ss_total} · ČET: {cet_total} · ŠEF-ref: {sef_total}")
    print(f"  izdavača centralnih (SS/ČET) direktiva: "
          f"{sum(1 for d in issuers.values() if d['central'] > 0)}")
    print("  TOP izdavači centralnih direktiva (ime · SS · ČET · ŠEF · uloga · org):")
    for d in cand[:12]:
        role = []
        if d.get("coordinator"):
            role.append("koord")
        if d.get("centroid"):
            role.append("CENTROID")
        print(f"    {(d.get('ime') or d['id']):<26} ss={d['ss']:>4} cet={d['cet']:>4} "
              f"sef={d['sef']:>5} · {','.join(role) or '—':<16} · org={d['max_org']}")

    # =========================================================================
    # 4) PRIMERI direktiva po tonu (za UI, da se vidi tekst)
    # =========================================================================
    print("[4/4] Primeri ...", flush=True)
    examples = {}
    for key, rx in (("napad", AGG_RAW), ("odbrana", SUP_RAW),
                    ("SS", r'super ?spec|iz ss'), ("CET", r'iz cet|video iz cet')):
        cur.execute("""
            SELECT tu_smernica, count(*) FROM arhiva_twitter_unos
            WHERE tu_smernica ~* %s GROUP BY 1 ORDER BY 2 DESC LIMIT 6
        """, (rx,))
        rows = [{"text": r[0], "n": r[1]} for r in cur.fetchall()]
        cur.execute("""
            SELECT vu_smernica, count(*) FROM arhiva_vesti_unos
            WHERE vu_smernica ~* %s GROUP BY 1 ORDER BY 2 DESC LIMIT 6
        """, (rx,))
        rows += [{"text": r[0], "n": r[1]} for r in cur.fetchall()]
        examples[key] = rows

    out = {
        "generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "twitter": {**tw_tax, "monthly": tw_month},
        "news": {**nw_tax, "monthly": nw_month},
        "chain": {"twitter_tone_target": tw_chain, "news_tone_portal": nw_chain},
        "command_source": {
            "ss_total": ss_total, "cet_total": cet_total, "sef_total": sef_total,
            "central_issuers": sum(1 for d in issuers.values() if d["central"] > 0),
            "top_issuers": [{k: v for k, v in d.items()} for d in cand[:40]],
            "disclaimer": ("Kreator = ko je zadatak UNEO u sistem. „Šef/čet“ u tekstu "
                           "referišu na uzvodnog lidera koji NIJE nužno red u bazi — "
                           "NE izjednačavamo kreatora sa „Šefom“."),
        },
        "examples": examples,
        "defs": {
            "opp_handles": OPP, "pro_handles": PRO,
            "agg_regex": AGG_RAW, "sup_regex": SUP_RAW,
            "note": ("Taksonomija klasifikuje na normalizovanom tekstu (lower + "
                     "ćirilica→latinica + bez dijakritika). Lanac/izvor koriste isti "
                     "raw AGG/SUP regex kao toksičnost radi konzistentnosti."),
        },
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
