import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta

def simulate_massive_dataset(output_path):
    print("🚀 Generisanje masivnog 'Real-World' simuliranog dataseta...")
    data = []
    base_time = datetime(2023, 11, 1, 8, 0, 0)
    
    # 1. ORGANSKI KORISNICI (1000 korisnika, 8000 tvitova)
    print("-> Generisanje organskog saobraćaja...")
    organic_topics = [
        "Vreme je danas prelepo, konačno malo sunca!",
        "Da li neko zna dobar restoran u centru?",
        "Ne mogu da verujem kakva utakmica sinoć...",
        "Gužva na gazeli je nepodnošljiva.",
        "Pročitao sam odličnu knjigu preporučujem svima.",
        "Spremam se za posao, jedva čekam vikend.",
        "Novi film je apsolutno razočarenje.",
        "Jel vama radi internet kako treba danas?"
    ]
    for _ in range(8000):
        created_at = base_time + timedelta(seconds=np.random.randint(0, 86400)) # over 24 hours
        author_id = f"real_user_{np.random.randint(1, 1001)}"
        text = np.random.choice(organic_topics) + " " + str(uuid.uuid4())[:8]
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": text,
            "is_retweet": False,
            "retweeted_tweet_id": None,
            "retweeted_author_id": None
        })

    # 2. TEMPORAL & NETWORK BOT MREŽA (Politicka bot farma - 150 botova pumpa 2 političara)
    print("-> Ubrzgavanje Astroturfing bot mreže (Temporal + Network)...")
    politicians = ["@PoliticarA", "@PoliticarB"]
    for pol in politicians:
        pol_tweet_id = f"TWEET_POL_{pol}"
        # burst starts at a specific time
        burst_time = base_time + timedelta(hours=np.random.randint(2, 20))
        for i in range(150):
            author_id = f"bot_farm_{i}"
            # they all retweet within 10 seconds!
            created_at = burst_time + timedelta(milliseconds=np.random.randint(0, 10000))
            data.append({
                "tweet_id": str(uuid.uuid4()),
                "author_id": author_id,
                "created_at": created_at,
                "text": f"RT {pol} Apsolutno se slažem, ovo je jedini pravi put za nas!",
                "is_retweet": True,
                "retweeted_tweet_id": pol_tweet_id,
                "retweeted_author_id": pol
            })

    # 3. NLP SPAM BOTOVI (Kripto prevare - 100 botova)
    print("-> Ubrzgavanje Kripto spambotova (NLP)...")
    spam_templates = [
        "Uložio sam 50$ i zaradio 5000$ preko ove nove platforme! Link u opisu! #kripto",
        "Uložio sam 50$ i dobio 5000$ preko ove sjajne platforme! Link u opisu! #kripto",
        "Neverovatno, uložio sam 50$ i zaradio 5000$! Link u opisu! #kripto",
        "Ova platforma je luda! Uložio sam 50$ i zaradio 5000$. Link u opisu! #kripto"
    ]
    for i in range(500):
        created_at = base_time + timedelta(seconds=np.random.randint(0, 86400))
        author_id = f"crypto_scam_bot_{np.random.randint(1, 101)}"
        data.append({
            "tweet_id": str(uuid.uuid4()),
            "author_id": author_id,
            "created_at": created_at,
            "text": np.random.choice(spam_templates),
            "is_retweet": False,
            "retweeted_tweet_id": None,
            "retweeted_author_id": None
        })

    # Shuffle and save
    df = pd.DataFrame(data)
    df = df.sort_values(by="created_at").reset_index(drop=True)
    df.to_csv(output_path, index=False)
    print(f"✅ Generisano {len(df)} tvitova u fajl: {output_path}")

if __name__ == "__main__":
    simulate_massive_dataset("../../data/massive_mock_tweets.csv")
