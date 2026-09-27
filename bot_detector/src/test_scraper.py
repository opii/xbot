from ntscraper import Nitter

def scrape_test():
    print("Inicijalizacija Nitter scrapera...")
    scraper = Nitter(log_level=1, skip_instance_check=False)
    
    print("Skrejpovanje tvitova za termin 'Srbija'...")
    # Get 100 recent tweets mentioning Srbija
    results = scraper.get_tweets("Srbija", mode='term', number=100)
    
    tweets = results.get('tweets', [])
    print(f"Uspešno povučeno {len(tweets)} tvitova.")
    
    if len(tweets) > 0:
        print("\nPrvih par tvitova:")
        for t in tweets[:3]:
            print(f"- @{t['link'].split('/')[1] if 'link' in t else 'Unknown'}: {t['text'][:100]}...")

if __name__ == "__main__":
    scrape_test()
