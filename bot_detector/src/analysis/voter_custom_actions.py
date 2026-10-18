#!/usr/bin/env python3
"""
KORAK 3: Headless automatizacija — JavaScript/XPath injekcija (voter_glasanje_custom).

Tabele: voter_glasanje_custom (4 custom akcije: vgc_link, vgc_akcija_1..3 = sirovi JS,
vgc_limit, vgc_uradjeno), voter_racunari_glasanje_custom (511 izvršenja: vrgc_racunar_id
→ vr_id, vrgc_vreme).

Dokumentuje tehnički mehanizam: sistem šalje klijentima JS sa XPath selektorima
(document.evaluate), scrollIntoView() i el.click() da emulira ljudski klik/skrol.

FER PLAY: ako JS sadrži hardkodovane tajne (npr. pass=...), one se REDIGUJU — ne
izlažu se. Izvršenje po mašini je eksplicitno (vrgc_racunar_id → vr_id).

Izlaz: data/geo/voter_custom_actions.json
"""
import json
import os
import re
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "voter_custom_actions.json")


def unesc(s):
    return (s or "").replace("\\/", "/").replace("\\r", " ").replace("\\n", " ").replace('\\"', '"')


def redact(js):
    """Redaguj hardkodovane tajne u JS kodu (pass/token/key = '...')."""
    js = re.sub(r"(pass|password|token|key|secret)(['\"]?\s*[:=]\s*['\"])[^'\"]+",
                r"\1\2<REDIGOVANO>", js, flags=re.I)
    return js


def mechanism(js):
    """Prepoznaj tehnike simulacije ljudskog ponašanja."""
    j = (js or "").lower()
    tech = []
    if "document.evaluate" in j or "xpath" in j:
        tech.append("XPath selektor (document.evaluate)")
    if "scrollintoview" in j:
        tech.append("scrollIntoView (skrol do elementa)")
    if ".click(" in j:
        tech.append("el.click() (simuliran klik)")
    if "formdata" in j:
        tech.append("FormData POST (direktan upis)")
    if "fetch(" in j or "xmlhttprequest" in j or "myheaders" in j:
        tech.append("fetch/XHR (API poziv)")
    if "settimeout" in j or "sleep" in j:
        tech.append("timing/delay (ljudski tempo)")
    return tech


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    actions = []
    for r in q("""SELECT vgc_id, vgc_link, vgc_limit, vgc_uradjeno,
                         vgc_akcija_1, vgc_akcija_2, vgc_akcija_3 FROM voter_glasanje_custom"""):
        vid, link, lim, done = r[0], unesc(r[1]), r[2], r[3]
        full_js = " ".join(unesc(x) for x in r[4:7] if x)
        tech = mechanism(full_js)
        # izvršenja po ovoj akciji
        ex = q("""SELECT count(*), count(DISTINCT g.vrgc_racunar_id),
                        min(g.vrgc_vreme), max(g.vrgc_vreme),
                        count(*) FILTER (WHERE r.vr_srbija=0) strano
                 FROM voter_racunari_glasanje_custom g
                 LEFT JOIN voter_racunari r ON r.vr_id=g.vrgc_racunar_id
                 WHERE g.vrgc_akcija_id=%s""", (vid,))[0]
        actions.append({
            "id": vid, "link": link, "limit": lim, "uradjeno": done,
            "techniques": tech,
            "js_excerpt_redacted": redact(full_js)[:220],
            "executions": ex[0], "machines": ex[1],
            "exec_from": ex[2], "exec_to": ex[3], "exec_foreign": ex[4],
        })

    # satnica izvršenja (sva custom akcija) po državi mašine
    def hours(srb):
        h = [0] * 24
        for hh, n in q(r"""SELECT substr(g.vrgc_vreme,12,2), count(*)
                          FROM voter_racunari_glasanje_custom g JOIN voter_racunari r ON r.vr_id=g.vrgc_racunar_id
                          WHERE r.vr_srbija=%s AND g.vrgc_vreme ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}'
                          GROUP BY 1""", (srb,)):
            if hh and hh.isdigit():
                h[int(hh)] = n
        return h

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "actions": actions,
        "exec_total": q("SELECT count(*) FROM voter_racunari_glasanje_custom")[0][0],
        "hours_foreign": hours(0), "hours_serbia": hours(1),
        "note": ("Sistem šalje sirovi JS klijentu da emulira čoveka u browseru "
                 "(XPath + scrollIntoView + click + FormData). Hardkodovane tajne u JS "
                 "su REDIGOVANE. Izvršenje po mašini je eksplicitno (vrgc_racunar_id)."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Custom akcija: {len(actions)} · izvršenja ukupno: {out['exec_total']}")
    for a in actions:
        print(f"  id={a['id']} {a['link'][:60]} | {', '.join(a['techniques'])} | "
              f"izvrš={a['executions']} (strano {a['exec_foreign']})")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
