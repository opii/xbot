#!/usr/bin/env python3
"""
GeoIP analiza voter infrastrukture (voter_racunari.vr_ip) — OFFLINE.

Koristi besplatni iptoasn dataset (data/geo/ip2asn-v4.tsv.gz: opseg_start,
opseg_end, ASN, država, opis/provajder). IP-jevi se NE šalju nikuda — samo
lokalno mapiranje. Daje raspodelu po državama i ASN/provajderima.

Pokretanje:  ./venv/bin/python src/analysis/voter_geoip.py
"""
import bisect
import gzip
import json
import os
from collections import Counter

import psycopg2

HERE = os.path.dirname(os.path.abspath(__file__))
TSV = os.path.join(HERE, "..", "..", "data", "geo", "ip2asn-v4.tsv.gz")
OUT = os.path.join(HERE, "..", "..", "data", "geo", "voter_geoip.json")
PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"


def ip2int(ip):
    try:
        a, b, c, d = (int(x) for x in ip.strip().split(":")[0].split("."))
        if max(a, b, c, d) > 255:
            return None
        return (a << 24) | (b << 16) | (c << 8) | d
    except (ValueError, AttributeError):
        return None


def load_ranges():
    starts, ranges = [], []
    with gzip.open(TSV, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 5:
                continue
            s, e = ip2int(p[0]), ip2int(p[1])
            if s is None or e is None:
                continue
            starts.append(s)
            ranges.append((e, p[2], p[3], p[4]))  # end, asn, cc, descr
    print(f"iptoasn opsega: {len(starts):,}", flush=True)
    return starts, ranges


def lookup(ipi, starts, ranges):
    i = bisect.bisect_right(starts, ipi) - 1
    if i < 0:
        return None
    end, asn, cc, descr = ranges[i]
    if ipi > end or asn == "0":
        return None
    return cc, asn, descr


def main():
    starts, ranges = load_ranges()
    cur = psycopg2.connect(PG).cursor()
    cur.execute("SET search_path TO progress")
    cur.execute("SELECT vr_ip, vr_srbija FROM voter_racunari "
                "WHERE vr_ip IS NOT NULL AND vr_ip <> ''")
    rows = cur.fetchall()

    by_country, by_asn, by_country_ip = Counter(), Counter(), {}
    srb_flag = Counter()
    total, matched, foreign = 0, 0, 0
    seen_ip_country = {}
    for ip, srb in rows:
        total += 1
        ipi = ip2int(ip)
        if ipi is None:
            continue
        r = lookup(ipi, starts, ranges)
        if not r:
            continue
        cc, asn, descr = r
        matched += 1
        by_country[cc] += 1
        by_asn[f"AS{asn} · {descr} ({cc})"] += 1
        by_country_ip.setdefault(cc, set()).add(ip)
        seen_ip_country[ip] = cc
        srb_flag[(cc == "RS", srb)] += 1
        if cc != "RS":
            foreign += 1

    rs_ip = len(by_country_ip.get("RS", set()))
    all_ip = len(seen_ip_country)
    print(f"\nvoter zapisa: {total:,} · mapirano: {matched:,} · "
          f"van RS: {foreign:,} ({100*foreign/matched:.0f}%)", flush=True)
    print(f"distinct IP: {all_ip:,} · od toga RS: {rs_ip:,} "
          f"({100*rs_ip/all_ip:.0f}%)\n", flush=True)
    print("TOP DRŽAVE (po zapisima):")
    for cc, n in by_country.most_common(12):
        print(f"  {cc}: {n:,} ({len(by_country_ip[cc]):,} IP)")
    print("\nTOP ASN / PROVAJDERI:")
    for a, n in by_asn.most_common(15):
        print(f"  {n:>5,}  {a[:70]}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({
            "total": total, "matched": matched, "foreign": foreign,
            "distinct_ip": all_ip, "rs_ip": rs_ip,
            "countries": dict(by_country.most_common()),
            "country_ip": {k: len(v) for k, v in by_country_ip.items()},
            "asn": dict(by_asn.most_common(50)),
        }, fh, ensure_ascii=False, indent=2)
    print(f"\n[OK] sažetak: {OUT}")


if __name__ == "__main__":
    main()
