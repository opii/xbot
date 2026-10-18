#!/usr/bin/env python3
"""
KORAK 1: Prekogranične informacione operacije (Crna Gora & BiH) + proxy mreža.

Tabele: izvestaj_voter (dnevni agregat glasanja/komentara po portalu — NEMA kolonu
države, pa se država izvodi iz portala), drzava (1=SRBIJA,2=CRNA GORA,3=HRVATSKA,
4=BIH), proxy_ip_adrese (133 proxy servera, svih 133 za vijesti.me).

FER PLAY: portal→država je mapiranje po poznatom spisku (b92.net=RS, in4s.net=CG —
TLD nije dovoljan). Glasovi su agregat iz baze (iv_glasanja); proxy veza je
eksplicitna (kolona portal).

Izlaz: data/geo/regional_operations.json → /api/regional_operations.
Doc: docs/regionalne_operacije_cg_bih.md
"""
import json
import os
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "regional_operations.json")

# portal → država (eksplicitni spisak; TLD fallback na kraju)
CG = {"in4s.net", "vijesti.me", "rtcg.me", "cdm.me", "pobjeda.me", "antenam.net", "aktuelno.me"}
BIH = {"klix.ba", "avaz.ba", "dnevniavaz.ba", "n1info.ba", "faktor.ba", "slobodna-bosna.ba"}
HR = {"index.hr", "jutarnji.hr", "vecernji.hr", "24sata.hr"}


def country_of(portal):
    p = (portal or "").lower()
    if p in CG:
        return "CRNA GORA"
    if p in BIH:
        return "BIH"
    if p in HR:
        return "HRVATSKA"
    if p.endswith(".me"):
        return "CRNA GORA"
    if p.endswith(".ba"):
        return "BIH"
    if p.endswith(".hr"):
        return "HRVATSKA"
    return "SRBIJA"


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    rows = q("""SELECT iv_portal, sum(iv_glasanja), sum(iv_komentara), count(*)
                FROM izvestaj_voter WHERE iv_portal IS NOT NULL AND iv_portal<>''
                GROUP BY 1""")
    portals, by_country = [], {}
    for p, g, k, n in rows:
        c = country_of(p)
        portals.append({"portal": p, "country": c, "votes": int(g or 0),
                        "comments": int(k or 0)})
        d = by_country.setdefault(c, {"country": c, "votes": 0, "comments": 0, "portals": 0})
        d["votes"] += int(g or 0); d["comments"] += int(k or 0); d["portals"] += 1
    portals.sort(key=lambda x: x["votes"], reverse=True)
    countries = sorted(by_country.values(), key=lambda d: d["votes"], reverse=True)
    foreign_votes = sum(d["votes"] for d in countries if d["country"] != "SRBIJA")
    total_votes = sum(d["votes"] for d in countries) or 1

    # proxy mreža
    proxy_by_portal = {p: n for p, n in q("SELECT portal, count(*) FROM proxy_ip_adrese GROUP BY 1")}
    distinct_ip = q("SELECT count(DISTINCT split_part(ip,':',1)) FROM proxy_ip_adrese")[0][0]
    total_proxy = q("SELECT count(*) FROM proxy_ip_adrese")[0][0]
    proxy_sample = [r[0] for r in q("SELECT ip FROM proxy_ip_adrese LIMIT 4")]

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "countries": countries,
        "foreign_votes": foreign_votes,
        "foreign_share": round(foreign_votes / total_votes, 4),
        "portals": portals[:40],
        "proxy": {"total": total_proxy, "distinct_ip": distinct_ip,
                  "by_portal": proxy_by_portal, "ip_port_format": True,
                  "sample_masked": [s.split(":")[0].rsplit(".", 1)[0] + ".x:" + s.split(":")[1]
                                    if ":" in s else s for s in proxy_sample]},
        "note": ("izvestaj_voter je dnevni agregat (iv_glasanja) bez kolone države — "
                 "država se izvodi iz portala (eksplicitni spisak + TLD). Proxy veza "
                 "(portal) je eksplicitna: svih 133 proxyja konfigurisano za vijesti.me."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Strani glasovi: {foreign_votes:,} ({round(out['foreign_share']*100,1)}% od ukupnih)")
    for d in countries:
        print(f"  {d['country']:<12} glas={d['votes']:>14,} kom={d['comments']:>9,} ({d['portals']} portala)")
    print(f"Proxy: {total_proxy} servera ({distinct_ip} distinct IP), svi za: {list(proxy_by_portal)}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
