#!/usr/bin/env python3
"""
KORAK 8: Multi-platformski arsenal i zvanična dežurstva.

Nalozi po platformi: twitter, tiktok (7.957), instagram (8.761), facebook (6.176),
threads (3.366), reddit (642). arhiva_instagram_unos (10.891 zadatak),
arhiva_instagram_korisnici_komentari (68.710). dezurstva (15 kategorija).

Računa: unakrsnu matricu (koliko operatera pokriva 3+ mreže), obim po platformi,
Instagram dinamiku, i spisak 15 tipova dežurstava.

Izlaz: data/geo/multiplatform.json → /api/multiplatform_stats.
Doc: docs/multiplatform_arsenal.md
"""
import json
import os
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "multiplatform.json")

PLATFORMS = [
    ("Twitter", "korisnici_twitter_nalozi"),
    ("TikTok", "korisnici_tiktok_nalozi"),
    ("Instagram", "korisnici_instagram_nalozi"),
    ("Facebook", "korisnici_facebook_nalozi"),
    ("Threads", "korisnici_threads_nalozi"),
    ("Reddit", "korisnici_reddit_nalozi"),
]


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    def kcol(table):
        r = q("""SELECT column_name FROM information_schema.columns
                 WHERE table_schema='progress' AND table_name=%s AND column_name ILIKE '%%korisnik_id'
                 LIMIT 1""", (table,))
        return r[0][0] if r else None

    platforms, cover = [], {}
    total_accounts = 0
    for label, table in PLATFORMS:
        col = kcol(table)
        if not col:
            continue
        acc = q(f"SELECT count(*) FROM {table}")[0][0]
        ops = q(f"SELECT count(DISTINCT {col}) FROM {table} WHERE {col} IS NOT NULL")[0][0]
        total_accounts += acc
        platforms.append({"platform": label, "accounts": acc, "operators": ops})
        for (kid,) in q(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL"):
            cover.setdefault(kid, set()).add(label)

    # unakrsna matrica: koliko operatera pokriva N platformi
    dist = {}
    for kid, plats in cover.items():
        dist[len(plats)] = dist.get(len(plats), 0) + 1
    coverage = [{"platforms": n, "operators": dist[n]} for n in sorted(dist)]
    multi3 = sum(v for n, v in dist.items() if n >= 3)
    multi4 = sum(v for n, v in dist.items() if n >= 4)

    # Instagram dinamika
    ig_tasks = q("SELECT count(*) FROM arhiva_instagram_unos")[0][0]
    ig_comments = q("SELECT count(*) FROM arhiva_instagram_korisnici_komentari")[0][0]
    ig_span = q("""SELECT min(iu_kreirano_datum), max(iu_kreirano_datum)
                   FROM arhiva_instagram_unos WHERE iu_kreirano_datum<>''""")[0]
    ig_top_targets = [{"post": (r[0] or "")[:80], "komentara": r[1]} for r in q("""
        SELECT u.iu_naslov_posta, count(k.ikk_id) n
        FROM arhiva_instagram_unos u
        LEFT JOIN arhiva_instagram_korisnici_komentari k ON k.ikk_instagram_id = u.iu_id
        GROUP BY u.iu_id, u.iu_naslov_posta ORDER BY n DESC LIMIT 8""")]

    # dežurstva (15 tipova)
    dezurstva = [r[1] for r in q("SELECT d_id, d_naziv FROM dezurstva ORDER BY d_id")]

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_accounts": total_accounts,
        "platforms": platforms,
        "coverage": coverage,
        "operators_3plus_networks": multi3,
        "operators_4plus_networks": multi4,
        "instagram": {"tasks": ig_tasks, "comments": ig_comments,
                      "from": ig_span[0], "to": ig_span[1], "top_targets": ig_top_targets},
        "dezurstva_types": dezurstva,
        "note": ("Arsenal preko 6 platformi (+~51k naloga). Unakrsna matrica = broj "
                 "distinct platformi po operateru (iz *_korisnik_id). 15 kategorija "
                 "dežurstava pokriva Twitter/Instagram/Facebook/Telegram/Sajtovi/Voter…"),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Naloga ukupno (6 platformi): {total_accounts:,}")
    for p in platforms:
        print(f"  {p['platform']:<10} {p['accounts']:>6,} naloga · {p['operators']:>5} operatera")
    print(f"Operatera na 3+ mreže: {multi3} · 4+: {multi4}")
    print(f"Instagram: {ig_tasks:,} zadataka, {ig_comments:,} komentara")
    print(f"Dežurstva ({len(dezurstva)}): {dezurstva}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
