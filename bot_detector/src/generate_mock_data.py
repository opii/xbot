import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta

def generate_mock_data(output_path):
    print("Generating mock data...")
    data = []
    
    # 1. Generate normal random activity (organic users)
    base_time = datetime(2023, 10, 1, 12, 0, 0)
    for i in range(1000):
        # random time within 2 hours
        created_at = base_time + timedelta(seconds=np.random.randint(0, 7200))
        author_id = f"user_organic_{np.random.randint(1, 100)}"
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": "Ovo je neki random organski tvit.",
            "is_retweet": False,
            "retweeted_tweet_id": None
        })

    # 2. Generate a BOT ATTACK (Temporal Anomaly / Burst)
    # Target tweet to be amplified
    target_tweet_id = "TWEET_TARGET_123"
    target_tweet_time = base_time + timedelta(minutes=30)
    
    # Bot farm activates 5 seconds after the target tweet and retweets it 100 times within a 3-second window
    bot_activation_time = target_tweet_time + timedelta(seconds=5)
    
    for i in range(100):
        # 100 bots retweet within just 3000 milliseconds (3 seconds)
        offset_ms = np.random.randint(0, 3000)
        created_at = bot_activation_time + timedelta(milliseconds=offset_ms)
        author_id = f"bot_{i}"
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": "RT @TargetUser Ovo je fantastična vest!",
            "is_retweet": True,
            "retweeted_tweet_id": target_tweet_id
        })

    # Add a few more organic retweets to the same target tweet but spread over 1 hour
    for i in range(15):
        created_at = target_tweet_time + timedelta(minutes=np.random.randint(5, 60))
        author_id = f"user_organic_{np.random.randint(1, 100)}"
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": "RT @TargetUser Ovo je fantastična vest!",
            "is_retweet": True,
            "retweeted_tweet_id": target_tweet_id
        })

    # Create DataFrame and save
    df = pd.DataFrame(data)
    # Sort by time
    df = df.sort_values(by="created_at").reset_index(drop=True)
    
    df.to_csv(output_path, index=False)
    print(f"Mock data saved to {output_path}. Total records: {len(df)}")

if __name__ == "__main__":
    generate_mock_data("../data/mock_tweets.csv")
