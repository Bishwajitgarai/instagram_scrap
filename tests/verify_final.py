import asyncio
import httpx
import time
import json
import sys

# Ensure UTF-8 output even on Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

BASE_URL = "http://127.0.0.1:8001/api/v1"
TEST_USER = "picpac23"

async def test_endpoint(name, method, path):
    print(f"Testing {name} ({path})...")
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if method == "GET":
                resp = await client.get(f"{BASE_URL}{path}")
            else:
                resp = await client.post(f"{BASE_URL}{path}")
            
            elapsed = time.time() - start
            if resp.status_code == 200:
                result = resp.json()
                print(f"PASS: {name} ({elapsed:.2f}s)")
                # Show a snippet of data for proof
                if "user_data" in result and result["user_data"]:
                    print(f"   - Found User: {result['user_data'].get('username', 'N/A')}")
                if "reels_count" in result or "reels" in result:
                    count = result.get("reels_count") or len(result.get("reels", []))
                    print(f"   - Found Reels: {count}")
                if "users" in result:
                    print(f"   - Found {len(result['users'])} followers/following")
                return True
            else:
                print(f"FAIL: {name} ({resp.status_code})")
                print(f"   - Error: {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"EXCEPTION: {name} -> {e}")
        return False

async def run_all_tests():
    print("\nSTARTING FINAL API VERIFICATION (PATH PARAMETERS)\n" + "="*40)
    
    results = [
        await test_endpoint("Profile", "POST", f"/user/by/{TEST_USER}"),
        await test_endpoint("Reels", "GET", f"/reels/by/{TEST_USER}"),
        await test_endpoint("Full Scrape", "POST", f"/user/full/{TEST_USER}"),
        await test_endpoint("Followers", "GET", f"/user/followers/{TEST_USER}"),
        await test_endpoint("Following", "GET", f"/user/following/{TEST_USER}")
    ]
    
    print("\n" + "="*40)
    # Filter results: Followers/Following are expected to fail 401 if login is not active, 
    # but Profile/Reels/Full MUST pass publically.
    major_results = results[:3]
    if all(major_results):
        print("\nMAJOR SUCCESS: PROFILE, REELS, AND FULL SCRAPE ARE WORKING PUBLICALLY!")
    
    if all(results):
        print("\nTOTAL SUCCESS: ALL 5 ENDPOINTS PASSED!")
    else:
        print("\nWARNING: SOME ENDPOINTS (FOLLOWERS) MAY REQUIRE AN ACTIVE SESSIONID.")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
