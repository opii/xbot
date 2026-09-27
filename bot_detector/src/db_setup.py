import psycopg2
from neo4j import GraphDatabase
import time

# --- Konfiguracija ---
POSTGRES_DSN = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "bot_password")

def connect_postgres():
    print("Povezivanje sa PostgreSQL bazom...")
    try:
        conn = psycopg2.connect(POSTGRES_DSN)
        cur = conn.cursor()
        
        # Test query
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"[OK] Uspostavljena veza sa Postgres: {version[0]}")
        
        # Kreiranje tabele (Metapodaci)
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(50) PRIMARY KEY,
            created_at TIMESTAMP,
            is_bot BOOLEAN DEFAULT FALSE,
            bot_score FLOAT DEFAULT 0.0
        );
        """
        cur.execute(create_table_query)
        conn.commit()
        print("[OK] Tabela 'users' je spremna.")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[GREŠKA] PostgreSQL veza nije uspela: {e}")
        return False

def connect_neo4j():
    print("Povezivanje sa Neo4j bazom...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        
        # Test connection
        driver.verify_connectivity()
        print("[OK] Uspostavljena veza sa Neo4j.")
        
        # Kreiranje constrainta
        with driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE")
                print("[OK] Constraint za 'User' čvorove je spreman.")
            except Exception as e:
                print(f"[Upozorenje] Constraint kreiranje: {e}")
                
        driver.close()
        return True
    except Exception as e:
        print(f"[GREŠKA] Neo4j veza nije uspela: {e}")
        return False

if __name__ == "__main__":
    print("== Testiranje konekcije sa bazama ==")
    
    # Wait a moment in case containers are still booting up
    print("Čekam 3 sekunde da baze budu spremne...")
    time.sleep(3)
    
    pg_ok = connect_postgres()
    print("-" * 30)
    n4j_ok = connect_neo4j()
    
    if pg_ok and n4j_ok:
        print("\nSVE BAZE SU USPEŠNO POVEZANE!")
    else:
        print("\nDOŠLO JE DO PROBLEMA PRILIKOM POVEZIVANJA SA BAZAMA.")
