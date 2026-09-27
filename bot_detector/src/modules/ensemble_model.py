import pandas as pd
from temporal_analysis import detect_temporal_bursts
from nlp_analysis import detect_nlp_anomalies
from network_analysis import detect_astroturfing

def calculate_bot_scores(csv_path):
    print("\n" + "="*50)
    print("POKRETANJE ENSEMBLE MODELA (BOT SCORE)")
    print("="*50 + "\n")
    
    # 1. Get flags from Temporal Module
    temporal_bots = detect_temporal_bursts(csv_path)
    
    # 2. Get flags from NLP Module
    print("\n" + "-"*30 + "\n")
    nlp_bots = detect_nlp_anomalies(csv_path)
    
    # 3. Get flags from Network Module
    print("\n" + "-"*30 + "\n")
    network_bots = detect_astroturfing(csv_path)
    
    print("\n" + "="*50)
    print("AGREGACIJA REZULTATA")
    print("="*50)
    
    # Aggregate scores
    bot_scores = {}
    
    # We will get all unique authors from the dataset to initialize scores to 0
    df = pd.read_csv(csv_path)
    all_users = df['author_id'].unique()
    
    for user in all_users:
        score = 0
        reasons = []
        
        if user in temporal_bots:
            score += 33.3
            reasons.append("Temporal Anomaly")
        if user in nlp_bots:
            score += 33.3
            reasons.append("NLP Spam")
        if user in network_bots:
            score += 33.3
            reasons.append("Astroturfing Network")
            
        if score > 0:
            bot_scores[user] = {
                "score": min(100.0, score), # Cap at 100% just in case (float math)
                "reasons": reasons
            }
            
    # Convert to DataFrame for nice display
    results_df = pd.DataFrame.from_dict(bot_scores, orient='index')
    if not results_df.empty:
        results_df = results_df.sort_values(by="score", ascending=False)
        
        print(f"\nPronađeno ukupno {len(results_df)} sumnjivih naloga.\n")
        print("TOP 15 NAJSUMNJIVIJIH NALOGA:")
        print(results_df.head(15).to_string())
        
        # Count by category
        print("\nStatistika po verovatnoći:")
        high_risk = len(results_df[results_df['score'] > 60])
        med_risk = len(results_df[(results_df['score'] > 30) & (results_df['score'] <= 60)])
        
        print(f"Visok rizik (Bot Skor > 60%): {high_risk} naloga")
        print(f"Srednji rizik (Bot Skor 30-60%): {med_risk} naloga")
        
        # ----- NEW: Save to DB -----
        from db_integration import save_to_postgres, save_to_neo4j
        save_to_postgres(results_df)
        save_to_neo4j(csv_path, results_df)
        # ---------------------------
        
    else:
        print("Sistem nije pronašao botove.")

if __name__ == "__main__":
    calculate_bot_scores("../../data/massive_mock_tweets.csv")
