import pandas as pd

def detect_temporal_bursts(csv_path, time_window_seconds=5, min_retweets_in_window=20):
    """
    Detects abnormal bursts of retweets within a specific time window.
    """
    print(f"--- Modul za Vremensku Analizu (Temporal Analysis) ---")
    print(f"Učitavanje podataka sa: {csv_path}")
    
    # Load data and parse dates
    df = pd.read_csv(csv_path)
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Filter only retweets (we are looking for coordinated amplification)
    retweets = df[df['is_retweet'] == True].copy()
    
    print(f"Ukupno retvitova za analizu: {len(retweets)}")
    
    # We will analyze retweets grouped by the original tweet they are retweeting
    # Set the time index for rolling window operations
    retweets = retweets.set_index('created_at')
    
    suspicious_bots = set()
    anomalies_detected = 0

    # Group by the target tweet to see if a specific tweet is being astroturfed
    for target_id, group in retweets.groupby('retweeted_tweet_id'):
        # Sort by time just in case
        group = group.sort_index()
        
        # Count the number of retweets in a rolling window (e.g., 5 seconds)
        rolling_count = group.rolling(f'{time_window_seconds}s')['author_id'].count()
        
        # Find moments where the count in the window exceeds our threshold
        bursts = rolling_count[rolling_count >= min_retweets_in_window]
        
        if not bursts.empty:
            anomalies_detected += 1
            print(f"\n[!] ANOMALIJA DETEKTOVANA za Tweet ID: {target_id}")
            
            # For each burst, extract the exact accounts involved
            for burst_time in bursts.index:
                # The window starts time_window_seconds before the burst_time
                window_start = burst_time - pd.Timedelta(seconds=time_window_seconds)
                # Get the accounts that retweeted within this window
                bots_in_window = group.loc[window_start:burst_time]['author_id'].tolist()
                
                suspicious_bots.update(bots_in_window)
                
            print(f"  -> U prozoru od {time_window_seconds} sekundi, detektovano je do {int(bursts.max())} koordinisanih akcija.")
            print(f"  -> Izolovano {len(suspicious_bots)} potencijalnih bot naloga.")
            
    print(f"\n--- Rezultati ---")
    print(f"Ukupan broj jedinstvenih identifikovanih botova: {len(suspicious_bots)}")
    if len(suspicious_bots) > 0:
        # Print a sample of 10 bots
        sample = list(suspicious_bots)[:10]
        print(f"Uzorak ID-jeva: {sample} ...")
        
    return suspicious_bots

if __name__ == "__main__":
    detect_temporal_bursts("../../data/mock_tweets.csv")
