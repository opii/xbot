from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2

app = FastAPI()

# Allow CORS for the Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

POSTGRES_DSN = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"

def get_db_connection():
    return psycopg2.connect(POSTGRES_DSN)

@app.get("/api/stats")
def get_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users;")
    total_bots = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM users WHERE bot_score > 60;")
    high_risk = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    return {
        "totalBots": total_bots,
        "highRisk": high_risk,
        "mediumRisk": total_bots - high_risk
    }

@app.get("/api/bots")
def get_bots():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Fetch top 50 bots
    cur.execute("SELECT user_id, bot_score, reasons, created_at FROM users ORDER BY bot_score DESC LIMIT 50;")
    rows = cur.fetchall()
    
    bots = []
    for row in rows:
        bots.append({
            "id": row[0],
            "score": row[1],
            "reasons": row[2].split(", ") if row[2] else [],
            "detectedAt": row[3].strftime("%Y-%m-%d %H:%M:%S")
        })
        
        cur.close()
    conn.close()
    return bots

# --- NEO4J GRAPH ENDPOINT ---
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "bot_password")

@app.get("/api/graph")
def get_graph():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    
    nodes_dict = {}
    links = []
    
    query = """
    MATCH (s:User)-[r:RETWEETED]->(t:User)
    RETURN s.user_id AS source, s.bot_score AS source_score, t.user_id AS target, t.bot_score AS target_score
    LIMIT 500
    """
    
    try:
        with driver.session() as session:
            result = session.run(query)
            for record in result:
                s_id = record["source"]
                t_id = record["target"]
                s_score = record["source_score"] or 0
                
                # group 1 = Bot, group 0 = Normal, group 2 = Target Influencer
                if s_id not in nodes_dict:
                    nodes_dict[s_id] = {"id": s_id, "group": 1 if s_score >= 30 else 0, "val": 1}
                if t_id not in nodes_dict:
                    nodes_dict[t_id] = {"id": t_id, "group": 2, "val": 3}
                    
                links.append({"source": s_id, "target": t_id})
    except Exception as e:
        print(f"Neo4j Error: {e}")
    finally:
        driver.close()
    
    return {
        "nodes": list(nodes_dict.values()),
        "links": links
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
