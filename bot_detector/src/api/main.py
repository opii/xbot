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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
