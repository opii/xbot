# Jednokratni servis koji gradi Neo4j graf iz Postgres šeme `progress`.
# Pretpostavlja da je `progress` već popunjen (src/import_progress_db.py je
# host-side korak jer čita 4.8GB SQLite fajl).
FROM python:3.11-slim
RUN pip install --no-cache-dir psycopg2-binary "neo4j>=5,<6" "networkx>=3,<4"
WORKDIR /app
# src se montira kao volumen (vidi docker-compose.yml), pa image ostaje mali.
CMD ["python", "src/graph/load_graph.py"]
