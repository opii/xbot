#!/usr/bin/env python3
"""
Zadatak 2: partijska ekonomija — bodovi, kvote i „udarnici".

Izvori:
  - izvestaj_dnevni (2,22M dnevnih izveštaja po operateru): bodovi PO SVAKOM tipu
    akcije (lajk/retvit/reply/quote/komentar/sns_link/vesti_deljenje/voter), ukupno
    po operateru/danu + geografija (opština/okrug/region).
  - timski_bodovi (264): timski bodovi po lideru (tb_bodova, tb_procenat, tb_quote,
    tb_reply, tb_broj_aktivista).

Računa:
  1) vrednost po akciji = Σbodovi / Σcount (koliko sistem plaća quote vs lajk…),
  2) rang-lista „udarnika" (top operateri po ukupnim bodovima) + bihevioralna uloga,
  3) bodovi po opštini (ko postiže najviše),
  4) sažetak timskih bodova (fer-play napomena o tb_procenat).

FER PLAY: tb_procenat ima samo 2 vrednosti (30/50) i 2 lidera — NIJE realizacija
kvote („≥100%"); ne predstavljamo ga kao ispunjenost. Bodovi su interna partijska
ekonomija, ne dokaz o pojedincu van onoga što je sistem zabeležio.

Izlaz: data/geo/gamification.json → /api/gamification → UI „🎯 Kvote & Bodovanje".
Pokretanje:  ./venv/bin/python src/analysis/gamification_points.py
"""
import json
import os
from datetime import datetime

import psycopg2
from neo4j import GraphDatabase

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO = ("bolt://localhost:7687", ("neo4j", "bot_password"))
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "gamification.json")

ACTIONS = [
    ("lajk", "iz_twitter_like", "iz_twitter_like_bodovi"),
    ("retvit", "iz_twitter_retweet", "iz_twitter_retweet_bodovi"),
    ("reply", "iz_twitter_reply", "iz_twitter_reply_bodovi"),
    ("quote", "iz_twitter_quote", "iz_twitter_quote_bodovi"),
    ("komentar objavljen", "iz_komentari_objavljeni", "iz_komentari_objavljeni_bodovi"),
    ("komentar prijavljen", "iz_komentari_prijavljeni", "iz_komentari_prijavljeni_bodovi"),
    ("SNS link", "iz_komentari_sns_linkovi", "iz_komentari_sns_linkovi_bodovi"),
    ("deljenje vesti", "iz_vesti_deljenje", "iz_vesti_deljenje_bodovi"),
]


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    # 1) vrednost po akciji -----------------------------------------------------
    ppa = []
    for lbl, cnt, bod in ACTIONS:
        r = q(f"SELECT sum({cnt}), sum({bod}) FROM izvestaj_dnevni")[0]
        cc, bb = float(r[0] or 0), float(r[1] or 0)
        ppa.append({"action": lbl, "count": int(cc), "points": int(bb),
                    "per_action": round(bb / cc, 3) if cc else 0})
    ppa.sort(key=lambda d: d["per_action"], reverse=True)

    # 2) rang-lista udarnika (po ukupnim bodovima) -----------------------------
    top = q("""
        SELECT z.iz_korisnik_id, sum(z.iz_ukupno_bodovi) pts,
               sum(z.iz_twitter_quote) q, sum(z.iz_twitter_reply) rep,
               sum(z.iz_twitter_like) lk, sum(z.iz_twitter_retweet) rt,
               sum(z.iz_komentari_objavljeni) kom, sum(z.iz_vesti_deljenje) vd,
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'') ime,
               o.o_naziv okrug, op.op_naziv opstina
        FROM izvestaj_dnevni z
        LEFT JOIN korisnici k ON k.k_id = z.iz_korisnik_id
        LEFT JOIN okrug o ON o.o_id = k.k_okrug
        LEFT JOIN opstina op ON op.op_id = k.k_opstina
        GROUP BY z.iz_korisnik_id, k.k_ime, k.k_prezime, o.o_naziv, op.op_naziv
        ORDER BY pts DESC LIMIT 20
    """)
    leaders = []
    for r in top:
        leaders.append({"id": r[0], "points": int(r[1] or 0), "quote": int(r[2] or 0),
                        "reply": int(r[3] or 0), "like": int(r[4] or 0), "retweet": int(r[5] or 0),
                        "komentari": int(r[6] or 0), "deljenje": int(r[7] or 0),
                        "ime": r[8] or f"#{r[0]}", "okrug": r[9], "opstina": r[10]})

    # bihevioralna uloga top udarnika (iz grafa)
    drv = GraphDatabase.driver(NEO[0], auth=NEO[1])
    with drv.session() as s:
        for m in leaders:
            rec = s.run("MATCH (o:Operator {id:$id}) RETURN o.role AS role, "
                        "o.toxicity_level AS tox, o.shift_archetype AS arh", id=m["id"]).single()
            m["role"] = rec["role"] if rec else None
            m["toxicity_level"] = rec["tox"] if rec else None
            m["shift_archetype"] = rec["arh"] if rec else None
    drv.close()

    # 3) bodovi po opštini ------------------------------------------------------
    opr = q("""
        SELECT op.op_naziv, o.o_naziv, sum(z.iz_ukupno_bodovi) pts,
               count(DISTINCT z.iz_korisnik_id) ops
        FROM izvestaj_dnevni z
        LEFT JOIN opstina op ON op.op_id = z.iz_opstina_id
        LEFT JOIN okrug o ON o.o_id = z.iz_okrug_id
        WHERE z.iz_opstina_id IS NOT NULL
        GROUP BY op.op_naziv, o.o_naziv ORDER BY pts DESC LIMIT 25
    """)
    by_opstina = [{"opstina": r[0] or "?", "okrug": r[1], "points": int(r[2] or 0),
                   "operators": r[3]} for r in opr]

    # 4) timski bodovi (sažetak, fer-play) -------------------------------------
    tb = q("""SELECT count(*), count(DISTINCT tb_korisnik), sum(tb_bodova),
                     avg(tb_broj_aktivista), array_agg(DISTINCT tb_procenat)
              FROM timski_bodovi""")[0]
    team = {"records": tb[0], "distinct_leaders": tb[1], "total_points": int(tb[2] or 0),
            "avg_activists": round(float(tb[3] or 0), 1),
            "procenat_values": sorted(int(x) for x in (tb[4] or []) if x is not None),
            "note": ("tb_procenat ima samo fiksne vrednosti (30/50) i malo lidera → "
                     "NIJE merilo realizacije kvote; tretira se kao težina/kategorija, "
                     "ne „ispunjenost ≥100%“.")}

    # agregatni datum raspon
    span = q("SELECT min(iz_datum), max(iz_datum), count(DISTINCT iz_korisnik_id) FROM izvestaj_dnevni")[0]

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "date_from": span[0], "date_to": span[1], "operators": span[2],
        "points_per_action": ppa,
        "leaderboard": leaders,
        "by_opstina": by_opstina,
        "team_points": team,
        "fair_play": ("Bodovi su interna partijska ekonomija (sistem ih sam dodeljuje). "
                      "Vrednost po akciji = Σbodovi/Σcount. Uloga udarnika je iz grafa "
                      "(role/toxicity). Ne izvlače se zaključci o pojedincu van onoga "
                      "što je sistem zabeležio."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("Vrednost po akciji:")
    for p in ppa:
        print(f"  {p['action']:<20} {p['per_action']:>6} bod/akcija")
    print("\nTop udarnici (bodovi · uloga · toksičnost):")
    for m in leaders[:8]:
        print(f"  {m['points']:>10,} {m['ime']:<22} {m['role'] or '?':<12} {m['toxicity_level'] or ''}")
    print(f"\nTimski bodovi: {team['records']} zapisa, {team['distinct_leaders']} lidera, "
          f"procenat={team['procenat_values']}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
