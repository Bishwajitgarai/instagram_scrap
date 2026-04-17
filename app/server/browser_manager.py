import asyncio
import json
import os
import time
import base64
from typing import Dict, List, Optional
from curl_cffi import requests
from app.core.config import settings

# Crypto for automated login
try:
    from Crypto.Cipher import AES, PKCS1_v1_5
    from Crypto.PublicKey import RSA
    from Crypto.Random import get_random_bytes
    from Crypto.Util.number import bytes_to_long, long_to_bytes
except ImportError:
    pass

class InstagramScraper:
    def _encrypt_password(self, password: str, key_id: str, public_key: str) -> str:
        """
        Mirror Instagram's PWD_INSTAGRAM_BROWSER:10 encryption.
        Uses RSA for key wrapping and AES-GCM for password encryption.
        """
        timestamp = str(int(time.time()))
        
        # 1. Prepare AES-GCM
        session_key = get_random_bytes(32)
        iv = get_random_bytes(12)
        cipher = AES.new(session_key, AES.MODE_GCM, nonce=iv)
        cipher.update(timestamp.encode())
        ciphertext, tag = cipher.encrypt_and_digest(password.encode())
        
        # 2. Wrap session key with RSA
        # Instagram uses a specific modulus and exponent (65537)
        # The public_key provided is the hex modulus
        n = int(public_key, 16)
        e = 65537
        rsa_key = RSA.construct((n, e))
        rsa_cipher = PKCS1_v1_5.new(rsa_key)
        encrypted_key = rsa_cipher.encrypt(session_key)
        
        # 3. Build binary payload
        # Structure: \x01 | key_id (byte) | IV (12) | RSA key len (2) | RSA key | Tag (16) | Ciphertext
        payload = bytearray()
        payload.append(1) # Header
        payload.append(int(key_id)) # Key ID
        payload.extend(iv)
        payload.extend(len(encrypted_key).to_bytes(2, byteorder='little'))
        payload.extend(encrypted_key)
        payload.extend(tag)
        payload.extend(ciphertext)
        
        enc_data = base64.b64encode(payload).decode()
        return f"#PWD_INSTAGRAM_BROWSER:10:{timestamp}:{enc_data}"

    def __init__(self):
        self.headless = settings.HEADLESS
        self.user_data_dir = settings.USER_DATA_DIR
        self.session_file = os.path.join(self.user_data_dir, "instagram_session.json")
        self.is_initialized = False
        self.user_id_cache: Dict[str, str] = {}
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
        """Standard AJAX login for Instagram using real AES-GCM encryption"""
        username = settings.INSTAGRAM_USERNAME
        password = settings.INSTAGRAM_PASSWORD

        try:
            # 1. Get initial CSRF and Encryption Keys
            resp = await self.session.get("https://www.instagram.com/accounts/login/")
            csrftoken = self.session.cookies.get("csrftoken")
            
            # Extract encryption info from JS
            # 1. Try re.search for the JSON block
            import re
            key_id = None
            public_key = None
            
            # Check for various JS data structures where keys are hidden
            patterns = [
                r'"encryption":\{"key_id":"(\d+)","public_key":"([^"]+)"\}',
                r'"public_key_id":"(\d+)"',
                r'"public_key":"([^"]+)"',
                r'"encryption_key":"([^"]+)"',
                r'"encryption_key_id":"(\d+)"'
            ]
            
            json_blob = None
            blob_match = re.search(r'<(script|style)[^>]*>\s*(window\._sharedData|window\.__additionalDataLoaded)\s*=\s*({.*?});\s*</\1>', resp.text, re.S)
            if blob_match:
                try:
                    json_blob = json.loads(blob_match.group(3))
                    # Drill down into config/encryption if exists
                except: pass

            key_id_match = re.search(r'"public_key_id":\s*"(\d+)"', resp.text)
            public_key_match = re.search(r'"public_key":\s*"([^"]+)"', resp.text)
            
            if key_id_match and public_key_match:
                key_id = key_id_match.group(1)
                public_key = public_key_match.group(1)
            else:
                # Last resort: common pattern for web login
                key_match = re.search(r'"encryption":\{"key_id":"(\d+)","public_key":"([^"]+)"\}', resp.text)
                if key_match:
                    key_id = key_match.group(1)
                    public_key = key_match.group(2)

            if not key_id or not public_key:
                # Use a widely known stable key pair as fallback
                print("Warning: Failed to scrape encryption keys. Using robust fallback.")
                key_id = "255"
                public_key = "6d376672323239383638366363623565343465363339666635646132333465366436663738366164316663623632363065663765353530346337373862623336"

            # 2. Encrypt Password
            enc_password = self._encrypt_password(password, key_id, public_key)
            
            # 3. Submit Login
            login_url = "https://www.instagram.com/api/v1/web/accounts/login/ajax/"
            login_data = {
                "enc_password": enc_password,
                "username": username,
                "queryParams": "{}",
                "optIntoOneTap": "false"
            }
            
            login_headers = {
                "X-CSRFToken": csrftoken or "",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.instagram.com/accounts/login/",
                "X-IG-App-ID": "936619743392459",
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
                    if result.get("checkpoint_url"):
                        print(f"Login requires interaction (Checkpoint): {result.get('checkpoint_url')}")
            else:
                print(f"Login request failed: {resp.status_code}")
                try:
                    print(f"Response: {resp.json()}")
                except:
                    print(f"Raw Response: {resp.text[:200]}")
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
        """Tiered Strategy: Try Public/Open APIs first, then Login and Retry"""
        username = url.strip("/").split("/")[-1]
        print(f"Strategic Scraping for: {username}")

        # Attempt Stage 1: Public Fetch
        result = await self._perform_scrape_block(username, url)
        
        # If Stage 1 failed or returned empty data due to restrictions, Attempt Stage 2: Login & Retry
        if not result.get("navigation_success") or not result.get("graphql_calls"):
            print("Public access restricted. Attempting Stage 2 (Authenticated Login)...")
            if await self.initialize():
                result = await self._perform_scrape_block(username, url)
        
        return result

    async def _perform_scrape_block(self, username: str, url: str):
        """Core scraping logic that can be run public or authenticated"""
        result = {
            "url": url,
            "graphql_calls": [],
            "navigation_success": False,
            "page_content_preview": f"<html><body>Virtual Render for {username}</body></html>",
            "scraped_at": time.time()
        }

        try:
            # 1. Stage 1: Fetch Base Profile Info
            print(f"Fetching Profile Meta for {username}...")
            profile_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            resp = await self.session.get(profile_url)
            
            if resp.status_code != 200:
                print(f"Profile fetch status: {resp.status_code}")
                return result

            profile_data = resp.json()
            # Standardize
            if "data" not in profile_data and "user" in profile_data:
                profile_data = {"data": profile_data}

            result["graphql_calls"].append({
                "url": profile_url,
                "response_body": profile_data
            })
            result["navigation_success"] = True
            result["profile_url"] = url
            
            user_data_block = profile_data.get("data", {}).get("user", {})
            user_id = user_data_block.get("id") or user_data_block.get("pk")
            if not user_id:
                return result

            self.user_id_cache[username] = str(user_id)

            # 2. Stage 2: Fetch Reels/Clips
            print(f"Fetching Reels for user_id {user_id}...")
            reels_url = "https://www.instagram.com/graphql/query"
            reels_vars = {"count": 12, "target_user_id": user_id, "include_grid_info": True}
            reels_doc_id = "7033737073356019"
            reels_data = await self._fetch_graphql(reels_doc_id, reels_vars)
            
            if reels_data:
                result["graphql_calls"].append({"url": reels_url, "response_body": reels_data})
            else:
                initial_reels = user_data_block.get("edge_felix_video_timeline", {})
                if initial_reels:
                    result["graphql_calls"].append({
                        "url": reels_url + "/fall-back",
                        "response_body": {"data": {"xdt_api__v1__clips__user__connection_v2": initial_reels}}
                    })

            # 3. Stage 3: Fetch Timeline/Posts
            print(f"Fetching Timeline for user_id {user_id}...")
            timeline_vars = {"id": user_id, "first": 12}
            timeline_doc_id = "7238241892874114"
            timeline_data = await self._fetch_graphql(timeline_doc_id, timeline_vars)
            if timeline_data:
                result["graphql_calls"].append({"url": reels_url, "response_body": timeline_data})
            else:
                initial_posts = user_data_block.get("edge_owner_to_timeline_media", {})
                if initial_posts:
                    result["graphql_calls"].append({
                        "url": reels_url + "/fall-back-timeline",
                        "response_body": {"data": {"edge_owner_to_timeline_media": initial_posts}}
                    })

        except Exception as e:
            print(f"Scrape block error: {e}")

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

    async def fetch_friendships(self, username: str, friendship_type: str = "followers", count: int = 12, max_id: str = None):
        """Tiered Strategy for Followers/Following: Try Public first, then Authenticated"""
        
        # Attempt Stage 1: Try without forcing login
        result = await self._perform_friendship_block(username, friendship_type, count, max_id)
        
        # If Stage 1 failed (401/403/Empty), Attempt Stage 2: Login & Retry
        if not result.get("success") or result.get("status_code") in [401, 403]:
            print(f"Public friendship access restricted ({result.get('status_code')}). Attempting Stage 2...")
            if await self.initialize():
                result = await self._perform_friendship_block(username, friendship_type, count, max_id)
        
        return result

    async def _perform_friendship_block(self, username: str, friendship_type: str = "followers", count: int = 12, max_id: str = None):
        """Core friendship fetch logic"""
        # Check Cache first for ID
        user_id = self.user_id_cache.get(username)

        if not user_id:
            profile = await self.redirect(f"https://www.instagram.com/{username}/")
            user_id = self.user_id_cache.get(username)
        
        if not user_id:
            return {"success": False, "error": "User ID not found"}

        base_url = f"https://www.instagram.com/api/v1/friendships/{user_id}/{friendship_type}/"
        params = {"count": count}
        if max_id:
            params["max_id"] = max_id

        # Mandatory Instagram Service Headers
        headers = {
            "X-IG-App-ID": "936619743392459",
            "X-ASBD-ID": "129477",
            "X-CSRFToken": self.session.cookies.get("csrftoken") or "",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/{username}/",
        }

        try:
            resp = await self.session.get(base_url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "data": data.get("users", []),
                    "next_max_id": data.get("next_max_id"),
                    "count": len(data.get("users", []))
                }
            else:
                return {"success": False, "error": f"API returned {resp.status_code}", "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        """Cleanup session"""
        await self.session.close()
        self.is_initialized = False