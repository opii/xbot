#!/usr/bin/env python3
"""
Detektor organizatora (centroida) u grafu koordinacije.

Za svaki sloj (twitter=CO_ACTED, comments=CO_COMMENTED):
  1. Povuče veze (a,b,shared) iz Neo4j.
  2. ODSECANJE: zadrži samo veze čija je težina (shared) između p5 i p95.
     Tako izbacujemo masovne "svi-sa-svima" spone (gore) i najslabije
     slučajne (dole), pa centroidi nisu trivijalni mega-habovi.
  3. networkx: Louvain zajednice + težinski PageRank + betweenness (broker).
  4. organizer_score = 0.5*norm(pagerank) + 0.5*norm(betweenness).
  5. Centroid = najveći organizer_score u svojoj zajednici (is_organizer).
  6. Upiše nazad u Neo4j: {p}_community, {p}_pagerank, {p}_betweenness,
     {p}_org, {p}_organizer   (p = 'tw' za twitter, 'cc' za comments).

Pokretanje:  ./venv/bin/python src/graph/detect_organizers.py
Opcije: --lo 5 --hi 95 (percentili odsecanja)
"""
import argparse
import os

import networkx as nx
from networkx.algorithms import community as nxcom
from neo4j import GraphDatabase

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.environ.get("NEO4J_USER", "neo4j"),
              os.environ.get("NEO4J_PASSWORD", "bot_password"))

LAYERS = {"tw": "CO_ACTED", "cc": "CO_COMMENTED"}


def percentile(sorted_vals, q):
    if not sorted_vals:
        return 0
    i = max(0, min(len(sorted_vals) - 1, int(round(q / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def norm(d):
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    rng = hi - lo or 1
    return {k: (v - lo) / rng for k, v in d.items()}


def process(drv, prefix, rel, lo, hi):
    with drv.session() as s:
        edges = [(r["a"], r["b"], r["w"]) for r in s.run(
            f"MATCH (a:Operator)-[c:{rel}]-(b:Operator) WHERE a.id < b.id "
            "RETURN a.id AS a, b.id AS b, c.shared AS w")]
    if not edges:
        print(f"[{prefix}] nema veza ({rel})"); return
    weights = sorted(e[2] for e in edges)
    p_lo, p_hi = percentile(weights, lo), percentile(weights, hi)
    kept = [(a, b, w) for a, b, w in edges if p_lo <= w <= p_hi]
    print(f"[{prefix}] {rel}: veza {len(edges):,} -> posle odsecanja "
          f"[p{lo}={p_lo}, p{hi}={p_hi}] {len(kept):,}", flush=True)

    G = nx.Graph()
    for a, b, w in kept:
        G.add_edge(a, b, weight=w)
    if G.number_of_nodes() == 0:
        print(f"[{prefix}] prazan graf posle odsecanja"); return

    # Zajednice (Louvain, težinski, deterministički)
    comms = nxcom.louvain_communities(G, weight="weight", seed=42)
    comm_of = {}
    for ci, nodes in enumerate(comms):
        for n in nodes:
            comm_of[n] = ci
    print(f"[{prefix}] zajednica: {len(comms)}", flush=True)

    # Centralnost
    pr = nx.pagerank(G, weight="weight")
    k = None if G.number_of_nodes() <= 1500 else 500
    bet = nx.betweenness_centrality(G, k=k, weight=None, seed=42)
    prn, betn = norm(pr), norm(bet)
    org = {n: round(0.5 * prn.get(n, 0) + 0.5 * betn.get(n, 0), 6) for n in G.nodes()}

    # Centroid = max organizer_score u svojoj zajednici
    best = {}  # comm -> (node, score)
    for n, sc in org.items():
        c = comm_of[n]
        if c not in best or sc > best[c][1]:
            best[c] = (n, sc)
    centroids = {node for node, _ in best.values()}
    print(f"[{prefix}] centroida (organizatora): {len(centroids)}", flush=True)

    rows = [{"id": n, "comm": comm_of[n], "pr": round(pr[n], 6),
             "bet": round(bet[n], 6), "org": org[n],
             "is_org": n in centroids} for n in G.nodes()]
    with drv.session() as s:
        # resetuj stare vrednosti sloja
        s.run(f"MATCH (o:Operator) SET o.{prefix}_community=null, "
              f"o.{prefix}_organizer=false, o.{prefix}_org=0")
        for i in range(0, len(rows), 5000):
            s.run(f"""
                UNWIND $rows AS r
                MATCH (o:Operator {{id:r.id}})
                SET o.{prefix}_community=r.comm, o.{prefix}_pagerank=r.pr,
                    o.{prefix}_betweenness=r.bet, o.{prefix}_org=r.org,
                    o.{prefix}_organizer=r.is_org
            """, rows=rows[i:i + 5000])
    top = sorted(rows, key=lambda r: -r["org"])[:5]
    with drv.session() as s:
        for r in top:
            nm = s.run("MATCH (o:Operator {id:$id}) RETURN o.ime AS ime",
                       id=r["id"]).single()["ime"]
            print(f"    organizator: {nm or r['id']}  org={r['org']} "
                  f"(zajednica {r['comm']})", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=float, default=5)
    ap.add_argument("--hi", type=float, default=95)
    args = ap.parse_args()
    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    for prefix, rel in LAYERS.items():
        process(drv, prefix, rel, args.lo, args.hi)
    drv.close()
    print("\n[OK] Detekcija organizatora završena.")


if __name__ == "__main__":
    main()
