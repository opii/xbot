import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def detect_nlp_anomalies(csv_path, similarity_threshold=0.85, cluster_min_size=10):
    """
    Detects bots that post highly similar or identical original tweets (astroturfing).
    """
    print(f"--- Modul za NLP Analizu (Tekstualni Šabloni) ---")
    df = pd.read_csv(csv_path)
    
    # We only look at original tweets, not retweets
    originals = df[df['is_retweet'] == False].copy()
    print(f"Ukupno originalnih tvitova za NLP analizu: {len(originals)}")
    
    if len(originals) == 0:
        return set()

    # Calculate TF-IDF vectors for all texts
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(originals['text'])
    
    # Compute pair-wise cosine similarity
    # similarity_matrix[i][j] gives the similarity between tweet i and tweet j
    similarity_matrix = cosine_similarity(tfidf_matrix)
    
    # Fill diagonal with 0 so a tweet is not similar to itself
    np.fill_diagonal(similarity_matrix, 0)
    
    suspicious_bots = set()
    visited_indices = set()
    
    for i in range(len(similarity_matrix)):
        if i in visited_indices:
            continue
            
        # Find all tweets that are highly similar to tweet i
        similar_indices = np.where(similarity_matrix[i] >= similarity_threshold)[0]
        
        # If we find a large enough cluster of similar tweets
        if len(similar_indices) + 1 >= cluster_min_size:
            # Include the current tweet's index
            cluster_indices = [i] + list(similar_indices)
            visited_indices.update(cluster_indices)
            
            # Extract the bots involved
            cluster_df = originals.iloc[cluster_indices]
            bots_in_cluster = cluster_df['author_id'].unique().tolist()
            
            suspicious_bots.update(bots_in_cluster)
            
            print(f"\n[!] NLP ANOMALIJA DETEKTOVANA")
            print(f"  -> Pronađeno {len(cluster_df)} tvitova sa preko {similarity_threshold*100}% sličnosti.")
            print(f"  -> Primer teksta iz klastera: '{cluster_df.iloc[0]['text']}'")
            print(f"  -> Izolovano {len(bots_in_cluster)} potencijalnih bot naloga.")

    print(f"\n--- Rezultati ---")
    print(f"Ukupan broj NLP botova: {len(suspicious_bots)}")
    if len(suspicious_bots) > 0:
        sample = list(suspicious_bots)[:10]
        print(f"Uzorak NLP bot ID-jeva: {sample} ...")
        
    return suspicious_bots

if __name__ == "__main__":
    detect_nlp_anomalies("../../data/mock_tweets.csv")
