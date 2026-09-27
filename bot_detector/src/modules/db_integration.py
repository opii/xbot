import psycopg2
from neo4j import GraphDatabase
import pandas as pd
from datetime import datetime

POSTGRES_DSN = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "bot_password")

def save_to_postgres(results_df):
    print("\n--- Čuvanje rezultata u PostgreSQL ---")
    try:
        conn = psycopg2.connect(POSTGRES_DSN)
        cur = conn.cursor()
        
        # Obezbeđujemo da tabela ima potrebne kolone
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reasons TEXT;")
        
        upsert_query = """
        INSERT INTO users (user_id, is_bot, bot_score, reasons, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE 
        SET is_bot = EXCLUDED.is_bot, 
            bot_score = EXCLUDED.bot_score,
            reasons = EXCLUDED.reasons;
        """
        
        for user_id, row in results_df.iterrows():
            is_bot = row['score'] >= 60.0
            score = row['score']
            reasons = ", ".join(row['reasons'])
            now = datetime.now()
            
            cur.execute(upsert_query, (user_id, is_bot, float(score), reasons, now))
            
        conn.commit()
        cur.close()
        conn.close()
        print(f"[OK] {len(results_df)} naloga uspešno ažurirano/upisano u Postgres bazu.")
    except Exception as e:
        print(f"[GREŠKA] PostgreSQL upis nije uspeo: {e}")

def save_to_neo4j(csv_path, results_df):
    print("\n--- Čuvanje mrežnog grafa u Neo4j ---")
    try:
        df = pd.read_csv(csv_path)
        retweets = df[df['is_retweet'] == True].dropna(subset=['retweeted_author_id'])
        
        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        
        def create_graph_tx(tx, source, target, source_score):
            tx.run("""
                MERGE (s:User {user_id: $source})
                SET s.bot_score = $source_score
                MERGE (t:User {user_id: $target})
                MERGE (s)-[:RETWEETED]->(t)
                """, source=source, target=target, source_score=source_score)

        with driver.session() as session:
            count = 0
            for _, row in retweets.iterrows():
                source = row['author_id']
                target = row['retweeted_author_id']
                score = 0.0
                if source in results_df.index:
                    score = float(results_df.loc[source, 'score'])
                    
                session.execute_write(create_graph_tx, source, target, score)
                count += 1
                
        driver.close()
        print(f"[OK] {count} relacija retvitovanja (edges) upisano u Neo4j.")
        print("Sada možete otvoriti http://localhost:7474 u browseru i izvršiti Query: MATCH (n) RETURN n")
    except Exception as e:
        print(f"[GREŠKA] Neo4j upis nije uspeo: {e}")
