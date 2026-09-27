import pandas as pd
import networkx as nx

def detect_astroturfing(csv_path, min_in_degree=50):
    """
    Detects 'star graph' bot networks (Astroturfing).
    Identifies central accounts being artificially amplified by bot accounts 
    that have high out-degree towards the central account but low overall connectivity.
    """
    print(f"--- Modul za Mrežnu Analizu (Network Graph) ---")
    df = pd.read_csv(csv_path)
    
    # Filter only retweets since they form the directed edges
    retweets = df[df['is_retweet'] == True].dropna(subset=['retweeted_author_id'])
    print(f"Pravljenje grafa od {len(retweets)} retvitova...")
    
    # Initialize a directed graph
    G = nx.DiGraph()
    
    # Add edges from retweeter to retweeted author
    # e.g. bot_0 -> TargetUser
    for _, row in retweets.iterrows():
        source = row['author_id']
        target = row['retweeted_author_id']
        
        if G.has_edge(source, target):
            G[source][target]['weight'] += 1
        else:
            G.add_edge(source, target, weight=1)
            
    print(f"Graf kreiran: Čvorova={G.number_of_nodes()}, Ivica={G.number_of_edges()}")
    
    suspicious_bots = set()
    
    # Calculate In-Degree (how many unique accounts retweeted a user)
    in_degrees = dict(G.in_degree())
    
    # Find users who are being amplified (high in-degree)
    amplified_users = {user: degree for user, degree in in_degrees.items() if degree >= min_in_degree}
    
    if not amplified_users:
        print("Nije pronađena sumnjiva mrežna aktivnost (Astroturfing).")
        return suspicious_bots
        
    print(f"\n[!] ANOMALIJA MREŽNOG GRAFA: Detektovani centralni 'Influenser' nalozi")
    for target_user, in_deg in amplified_users.items():
        print(f"  -> Nalog '{target_user}' je retvitovan od strane {in_deg} različitih naloga.")
        
        # Look at the accounts retweeting this target user
        retweeters = [n for n in G.predecessors(target_user)]
        
        bots_for_this_target = []
        for retweeter in retweeters:
            # If an account ONLY retweets this target user and nobody else, it's highly suspicious
            out_deg = G.out_degree(retweeter)
            if out_deg == 1:
                bots_for_this_target.append(retweeter)
                
        if len(bots_for_this_target) > (in_deg * 0.8): # If 80% of retweeters are dedicated bots
            print(f"  -> UPOZORENJE: {len(bots_for_this_target)} od {in_deg} retvitera prate SAMO ovog naloga (Star Graph Pattern).")
            suspicious_bots.update(bots_for_this_target)
            
    print(f"\n--- Rezultati ---")
    print(f"Ukupan broj botova iz mrežne analize: {len(suspicious_bots)}")
    if len(suspicious_bots) > 0:
        sample = list(suspicious_bots)[:10]
        print(f"Uzorak ID-jeva: {sample} ...")
        
    return suspicious_bots

if __name__ == "__main__":
    detect_astroturfing("../../data/mock_tweets.csv")
