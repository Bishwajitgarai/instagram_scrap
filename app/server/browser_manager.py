import asyncio
import json
import os
import time
from typing import Dict, List, Optional
import httpx
from app.core.config import settings

class InstagramScraper:
    def __init__(self):
        self.headless = settings.HEADLESS
        self.user_data_dir = settings.USER_DATA_DIR
        self.session_file = os.path.join(self.user_data_dir, "instagram_session.json")
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "X-IG-App-ID": "936619743392459",
                "X-ASBD-ID": "129477",
                "Origin": "https://www.instagram.com",
                "Referer": "https://www.instagram.com/",
            }
        )
        self.is_initialized = False

    async def initialize(self):
        """Initialize session and login if needed"""
        if self.is_initialized:
            return True
        
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        if os.path.exists(self.session_file):
            print("💾 Loading existing session...")
            try:
                with open(self.session_file, "r") as f:
                    cookies_data = json.load(f)
                    self.client.cookies.update(cookies_data)
                
                # Verify session
                if await self.check_logged_in():
                    print("✅ Session valid and logged in")
                    self.is_initialized = True
                    return True
            except Exception as e:
                print(f"⚠️ Failed to load session: {e}")

        # Perform fresh login
        print("🔐 Performing fresh login...")
        login_success = await self.perform_login()
        if login_success:
            self.is_initialized = True
            return True
        
        return False

    async def perform_login(self):
        """Standard AJAX login for Instagram"""
        username = settings.INSTAGRAM_USERNAME
        password = settings.INSTAGRAM_PASSWORD

        # 1. Get initial CSRF token
        resp = await self.client.get("https://www.instagram.com/accounts/login/")
        csrftoken = self.client.cookies.get("csrftoken")
        
        # 2. Prepare login
        login_url = "https://www.instagram.com/api/v1/web/accounts/login/ajax/"
        login_data = {
            "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}",
            "username": username,
            "queryParams": "{}",
            "optIntoOneTap": "false"
        }
        
        login_headers = {
            "X-CSRFToken": csrftoken or "",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/accounts/login/",
        }

        resp = await self.client.post(login_url, data=login_data, headers=login_headers)
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("authenticated"):
                print("✅ Login successful")
                # Save session
                with open(self.session_file, "w") as f:
                    json.dump(dict(self.client.cookies), f)
                return True
            else:
                print(f"❌ Login failed: {result}")
        else:
            print(f"❌ Login request failed: {resp.status_code}")
        
        return False

    async def check_logged_in(self) -> bool:
        """Check if currently logged in"""
        try:
            resp = await self.client.get("https://www.instagram.com/api/v1/web/accounts/edit_tree/")
            return resp.status_code == 200
        except:
            return False

    async def redirect(self, url: str, **kwargs):
        """
        Fetch profile data via a multi-stage GraphQL sequence to mimic 
        the data captured by a real browser render.
        """
        if not self.is_initialized:
            await self.initialize()

        username = url.strip("/").split("/")[-1]
        print(f"🎯 Creating Virtual Browser session for: {username}")

        result = {
            "url": url,
            "graphql_calls": [],
            "navigation_success": False,
            "page_content_preview": f"<html><body>Virtual Render for {username}</body></html>",
            "scraped_at": time.time()
        }

        try:
            # 1. Stage 1: Fetch Base Profile Info
            print(f"📡 Stage 1: Fetching Profile Meta for {username}...")
            profile_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            resp = await self.client.get(profile_url)
            
            if resp.status_code != 200:
                print(f"❌ Failed to fetch profile: {resp.status_code}")
                return result

            profile_data = resp.json()
            result["graphql_calls"].append({
                "url": profile_url,
                "response_body": profile_data
            })
            result["navigation_success"] = True
            
            user_id = profile_data.get("data", {}).get("user", {}).get("id")
            if not user_id:
                print("⚠️ Could not find user_id in profile data")
                return result

            # 2. Stage 2: Fetch Reels/Clips (Capturing "after render" behavior)
            print(f"📡 Stage 2: Fetching Reels for user_id {user_id}...")
            reels_url = "https://www.instagram.com/graphql/query/"
            reels_vars = {
                "count": 12,
                "target_user_id": user_id,
                "include_grid_info": True
            }
            # Latest doc_id for clips_user_clips_graphql
            reels_data = await self._fetch_graphql("7033737073356019", reels_vars)
            if reels_data:
                result["graphql_calls"].append({
                    "url": reels_url + "?query_hash=clips_reels",
                    "response_body": reels_data
                })

            # 3. Stage 3: Fetch Timeline/Posts
            print(f"📡 Stage 3: Fetching Timeline for user_id {user_id}...")
            timeline_vars = {
                "id": user_id,
                "first": 12
            }
            # Latest doc_id for edge_owner_to_timeline_media
            timeline_data = await self._fetch_graphql("7238241892874114", timeline_vars)
            if timeline_data:
                result["graphql_calls"].append({
                    "url": reels_url + "?query_hash=timeline_media",
                    "response_body": timeline_data
                })

            print(f"✅ Virtual Rendering complete. Captured {len(result['graphql_calls'])} GraphQL calls.")

        except Exception as e:
            print(f"❌ Error during Virtual Browser session: {e}")

        return result

    async def _fetch_graphql(self, doc_id: str, variables: Dict) -> Optional[Dict]:
        """Helper to perform internal Instagram GraphQL queries"""
        try:
            url = "https://www.instagram.com/graphql/query/"
            data = {
                "doc_id": doc_id,
                "variables": json.dumps(variables)
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": self.client.cookies.get("csrftoken") or "",
            }
            resp = await self.client.post(url, data=data, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"⚠️ GraphQL query {doc_id} failed: {e}")
            return None

    async def scrape_user_reels_by_username(self, username: str, **kwargs):
        """Reuse redirect logic which now captures Reels automatically"""
        return await self.redirect(f"https://www.instagram.com/{username}/reels/")

    async def close(self):
        """Cleanup client"""
        await self.client.aclose()
        self.is_initialized = False