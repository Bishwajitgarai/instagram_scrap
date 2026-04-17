import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.server.browser_manager import InstagramScraper
from app.core.config import settings

async def verify_user(username: str):
    print(f"Starting Real-World Verification for: {username}")
    print(f"Using Username: {settings.INSTAGRAM_USERNAME}")
    
    scraper = InstagramScraper()
    try:
        # 1. Initialize
        print("Initializing Scraper...")
        success = await scraper.initialize()
        if not success:
            print("Failed to initialize scraper (Login Failed)")
            return

        # 2. Redirect/Fetch
        print(f"Fetching data for {username}...")
        url = f"https://www.instagram.com/{username}/"
        result = await scraper.redirect(url)
        
        # 3. Analyze Results
        print("\n--- Verification Results ---")
        print(f"Success: {result['navigation_success']}")
        print(f"Total GraphQL Calls: {len(result['graphql_calls'])}")
        
        for i, call in enumerate(result['graphql_calls']):
            url_part = call['url'].split('/')[-1]
            body = call.get('response_body', {})
            data_keys = body.get('data', {}).keys() if isinstance(body.get('data'), dict) else "No Data"
            print(f"Call {i+1}: {url_part} -> Keys found: {list(data_keys)}")

        # Check for Reels specifically
        reels_found = any("clips" in call.get('url', '').lower() or "clips" in str(call.get('response_body', '')).lower() for call in result['graphql_calls'])
        print(f"Reels Data Found: {reels_found}")

        # Check for Timeline specifically
        timeline_found = any("timeline" in str(call.get('response_body', '')).lower() for call in result['graphql_calls'])
        print(f"Timeline Data Found: {timeline_found}")

    except Exception as e:
        print(f"Verification Error: {e}")
    finally:
        await scraper.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user = sys.argv[1]
    else:
        user = "picpac23"
    asyncio.run(verify_user(user))
