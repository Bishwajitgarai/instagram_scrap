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
        """Fetch profile data via GraphQL to mimic the old redirect/interception logic"""
        if not self.is_initialized:
            await self.initialize()

        username = url.strip("/").split("/")[-1]
        print(f"🎯 Scraping profile via API: {username}")

        api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        
        # Mimic graphql calls structure for compatibility with user.py
        result = {
            "url": url,
            "graphql_calls": [],
            "navigation_success": False,
            "page_content_preview": "",
            "scraped_at": time.time()
        }

        try:
            resp = await self.client.get(api_url)
            if resp.status_code == 200:
                data = resp.json()
                result["graphql_calls"].append({
                    "url": api_url,
                    "response_body": data
                })
                result["navigation_success"] = True
                print(f"✅ Successfully fetched profile data for {username}")
            else:
                print(f"❌ Failed to fetch profile: {resp.status_code}")
        except Exception as e:
            print(f"❌ Error during API request: {e}")

        return result

    async def scrape_user_reels_by_username(self, username: str, **kwargs):
        """To be implemented if needed, can reuse redirect for now"""
        return await self.redirect(f"https://www.instagram.com/{username}/reels/")

    async def close(self):
        """Cleanup client"""
        await self.client.aclose()
        self.is_initialized = False