import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta

def generate_mock_data(output_path):
    print("Generating mock data...")
    data = []
    
    base_time = datetime(2023, 10, 1, 12, 0, 0)
    
    # 1. Generate normal random activity (organic users)
    organic_texts = [
        "Kakav prelep dan danas! ",
        "Idem na kafu, vidimo se kasnije. ",
        "Da li je neko gledao novu epizodu serije? ",
        "Opet gužva u saobraćaju... ",
        "Ne mogu da verujem šta se dešava u svetu. ",
        "Danas pravim sarmu po bakinom receptu. "
    ]
    for i in range(1000):
        created_at = base_time + timedelta(seconds=np.random.randint(0, 7200))
        author_id = f"user_organic_{np.random.randint(1, 100)}"
        text = np.random.choice(organic_texts) + str(uuid.uuid4())
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": text,
            "is_retweet": False,
            "retweeted_tweet_id": None,
            "retweeted_author_id": None
        })

    # 2. TEMPORAL ANOMALY: Bot farm retweeting target tweet in a burst
    target_tweet_id = "TWEET_TARGET_123"
    target_tweet_time = base_time + timedelta(minutes=30)
    bot_activation_time = target_tweet_time + timedelta(seconds=5)
    for i in range(100):
        offset_ms = np.random.randint(0, 3000)
        created_at = bot_activation_time + timedelta(milliseconds=offset_ms)
        author_id = f"bot_temporal_{i}"
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": "RT @TargetUser Ovo je fantastična vest!",
            "is_retweet": True,
            "retweeted_tweet_id": target_tweet_id,
            "retweeted_author_id": "TargetUser"
        })

    # 3. NLP ANOMALY: Bot farm spamming identical/similar text (Astroturfing)
    bot_texts = [
        "Ova nova inicijativa je fenomenalna stvar za našu zajednicu! Podrška! #napredak",
        "Ova nova inicijativa je fenomenalna stvar za našu zajednicu! Podrška #napredak",
        "Ova nova inicijativa je fenomenalna za našu zajednicu! Podrška! #napredak",
        "Ova nova inicijativa je fantastična stvar za našu zajednicu. Podrška! #napredak"
    ]
    nlp_activation_time = base_time + timedelta(minutes=60)
    for i in range(50):
        created_at = nlp_activation_time + timedelta(minutes=np.random.randint(0, 60))
        author_id = f"bot_nlp_{i}"
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": np.random.choice(bot_texts),
            "is_retweet": False,
            "retweeted_tweet_id": None,
            "retweeted_author_id": None
        })

    df = pd.DataFrame(data)
    df = df.sort_values(by="created_at").reset_index(drop=True)
    df.to_csv(output_path, index=False)
    print(f"Mock data saved to {output_path}. Total records: {len(df)}")

if __name__ == "__main__":
    generate_mock_data("../../data/mock_tweets.csv")
