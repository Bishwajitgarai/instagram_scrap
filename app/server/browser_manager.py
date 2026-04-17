import asyncio
import json
import os
import time
from typing import Dict, List, Optional
from curl_cffi import requests
from app.core.config import settings

class InstagramScraper:
    def __init__(self):
        self.headless = settings.HEADLESS
        self.user_data_dir = settings.USER_DATA_DIR
        self.session_file = os.path.join(self.user_data_dir, "instagram_session.json")
        self.is_initialized = False
        # Initialize the session with chrome impersonation
        self.session = requests.AsyncSession(
            impersonate="chrome120",
            timeout=30.0,
            headers={
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "X-IG-App-ID": "936619743392459",
                "X-ASBD-ID": "129477",
                "Origin": "https://www.instagram.com",
                "Referer": "https://www.instagram.com/",
            }
        )

    async def import_cookies_from_header(self, cookie_str: str):
        """
        Parses a raw cookie string from a request header and applies it to the session.
        This allows real-time session updates via API headers.
        """
        if not cookie_str:
            return
        
        cookies = {}
        try:
            parts = cookie_str.split(';')
            for part in parts:
                if '=' in part:
                    name, value = part.strip().split('=', 1)
                    cookies[name] = value
            
            if cookies:
                self.session.cookies.update(cookies)
                # Save to file for persistence
                os.makedirs(self.user_data_dir, exist_ok=True)
                with open(self.session_file, "w") as f:
                    json.dump(self.session.cookies.get_dict(), f)
                print(f"Dynamically imported {len(cookies)} cookies from header")
                self.is_initialized = True
        except Exception as e:
            print(f"Error importing cookies from header: {e}")

    async def initialize(self):
        """Initialize session and load existing if available"""
        if self.is_initialized:
            return True
        
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        if os.path.exists(self.session_file):
            print("Loading existing session...")
            try:
                with open(self.session_file, "r") as f:
                    cookies_data = json.load(f)
                    # curl_cffi handles cookies via a dict
                    self.session.cookies.update(cookies_data)
                
                # Verify session
                if await self.check_logged_in():
                    print("Session valid and logged in")
                    self.is_initialized = True
                    return True
            except Exception as e:
                print(f"Failed to load session: {e}")

        # Perform fresh login
        print("Attempting login...")
        login_success = await self.perform_login()
        if login_success:
            self.is_initialized = True
            return True
        
        print("Proceeding without login (Public mode)")
        self.is_initialized = True
        return True

    async def perform_login(self):
        """Standard AJAX login for Instagram using curl_cffi"""
        username = settings.INSTAGRAM_USERNAME
        password = settings.INSTAGRAM_PASSWORD

        try:
            # 1. Get initial CSRF token
            resp = await self.session.get("https://www.instagram.com/accounts/login/")
            csrftoken = self.session.cookies.get("csrftoken")
            
            # 2. Prepare login (Using simple #PWD prefix as fallback if login works)
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

            resp = await self.session.post(login_url, data=login_data, headers=login_headers)
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("authenticated"):
                    print("Login successful")
                    # Save session
                    with open(self.session_file, "w") as f:
                        json.dump(self.session.cookies.get_dict(), f)
                    return True
                else:
                    print(f"Login failed: {result}")
            else:
                print(f"Login request failed: {resp.status_code}")
        except Exception as e:
            print(f"Login error: {e}")
        
        return False

    async def check_logged_in(self) -> bool:
        """Check if currently logged in"""
        try:
            resp = await self.session.get("https://www.instagram.com/api/v1/web/accounts/edit_tree/")
            return resp.status_code == 200
        except:
            return False

    async def redirect(self, url: str, **kwargs):
        """Fetch profile data via a multi-stage GraphQL sequence"""
        if not self.is_initialized:
            await self.initialize()

        username = url.strip("/").split("/")[-1]
        print(f"Creating Virtual Browser session for: {username}")

        result = {
            "url": url,
            "graphql_calls": [],
            "navigation_success": False,
            "page_content_preview": f"<html><body>Virtual Render for {username}</body></html>",
            "scraped_at": time.time()
        }

        try:
            # 1. Stage 1: Fetch Base Profile Info
            print(f"Stage 1: Fetching Profile Meta for {username}...")
            profile_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            resp = await self.session.get(profile_url)
            
            if resp.status_code != 200:
                print(f"Failed to fetch profile: {resp.status_code}")
                return result

            profile_data = resp.json()
            # Standardize to data.user format if needed
            if "data" not in profile_data and "user" in profile_data:
                profile_data = {"data": profile_data}

            result["graphql_calls"].append({
                "url": profile_url,
                "response_body": profile_data
            })
            result["navigation_success"] = True
            result["profile_url"] = url
            
            user_id = profile_data.get("data", {}).get("user", {}).get("id")
            if not user_id:
                print("Could not find user_id in profile data")
                return result

            # 2. Stage 2: Fetch Reels/Clips
            print(f"Stage 2: Fetching Reels for user_id {user_id}...")
            reels_url = "https://www.instagram.com/graphql/query"
            reels_vars = {
                "count": 12,
                "target_user_id": user_id,
                "include_grid_info": True
            }
            reels_doc_id = "7033737073356019"
            reels_data = await self._fetch_graphql(reels_doc_id, reels_vars)
            if reels_data:
                result["graphql_calls"].append({
                    "url": reels_url,
                    "response_body": reels_data,
                    "request": {
                        "post_data": f"doc_id={reels_doc_id}&variables={json.dumps(reels_vars)}",
                        "headers": {
                            "x-ig-app-id": "936619743392459",
                            "x-csrftoken": self.session.cookies.get("csrftoken", "")
                        }
                    }
                })
            else:
                # FAIL-BACK: Extract initial reels from profile_data
                print("Specialized Reels fetch failed. Using fall-back from profile meta.")
                initial_reels = profile_data.get("data", {}).get("user", {}).get("edge_felix_video_timeline", {})
                if initial_reels:
                    result["graphql_calls"].append({
                        "url": reels_url + "/fall-back",
                        "response_body": {"data": {"xdt_api__v1__clips__user__connection_v2": initial_reels}}
                    })

            # 3. Stage 3: Fetch Timeline/Posts
            print(f"Stage 3: Fetching Timeline for user_id {user_id}...")
            timeline_vars = {"id": user_id, "first": 12}
            timeline_doc_id = "7238241892874114"
            timeline_data = await self._fetch_graphql(timeline_doc_id, timeline_vars)
            if timeline_data:
                result["graphql_calls"].append({
                    "url": reels_url,
                    "response_body": timeline_data,
                    "request": {
                        "post_data": f"doc_id={timeline_doc_id}&variables={json.dumps(timeline_vars)}",
                        "headers": {
                            "x-ig-app-id": "936619743392459",
                            "x-csrftoken": self.session.cookies.get("csrftoken", "")
                        }
                    }
                })
            else:
                # FAIL-BACK: Extract initial posts from profile_data
                print("Specialized Timeline fetch failed. Using fall-back from profile meta.")
                initial_posts = profile_data.get("data", {}).get("user", {}).get("edge_owner_to_timeline_media", {})
                if initial_posts:
                    result["graphql_calls"].append({
                        "url": reels_url + "/fall-back-timeline",
                        "response_body": {"data": {"edge_owner_to_timeline_media": initial_posts}}
                    })

            print(f"Virtual Rendering complete. Captured {len(result['graphql_calls'])} GraphQL calls.")

        except Exception as e:
            print(f"Error during Virtual Browser session: {e}")

        return result

    async def _fetch_graphql(self, doc_id: str, variables: Dict) -> Optional[Dict]:
        """Helper for GraphQL queries using curl_cffi"""
        try:
            url = "https://www.instagram.com/graphql/query"
            data = {
                "doc_id": doc_id,
                "variables": json.dumps(variables)
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": self.session.cookies.get("csrftoken") or "",
                "X-IG-App-ID": "936619743392459",
                "X-ASBD-ID": "129477",
                "X-IG-WWW-Claim": "0",
                "X-Requested-With": "XMLHttpRequest",
            }
            resp = await self.session.post(url, data=data, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"GraphQL query {doc_id} failed: {e}")
            return None

    async def scrape_user_reels_by_username(self, username: str, **kwargs):
        """Reuse redirect logic"""
        return await self.redirect(f"https://www.instagram.com/{username}/reels/")

    async def close(self):
        """Cleanup session"""
        await self.session.close()
        self.is_initialized = False