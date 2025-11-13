import asyncio
import json
import os
import time
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import uvicorn
from contextlib import asynccontextmanager
import httpx
from playwright.async_api import async_playwright
from undetected_playwright import Tarnished


# Load environment variables
load_dotenv()

class InstagramScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.user_data_dir = "./instagram_profile"
        self.browser = None
        self.context = None
        self.page = None
        self.graphql_calls = []
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize browser and login once"""
        if self.is_initialized:
            return True
            
        playwright = await async_playwright().start()
        
        # Create user data directory for persistent sessions
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        # Launch browser with optimized settings
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-translate',
                '--disable-web-security',
                '--disable-features=site-per-process',
                '--disable-ipc-flooding-protection',
                '--aggressive-cache-discard',
                '--max_old_space_size=4096',
            ],
            timeout=60000
        )
        
        # Create persistent context
        self.context = await self.browser.new_context(
            storage_state=os.path.join(self.user_data_dir, 'auth.json') if os.path.exists(os.path.join(self.user_data_dir, 'auth.json')) else None,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            ignore_https_errors=True,
            java_script_enabled=True,
            has_touch=False
        )
        
        # Set default timeouts for context
        self.context.set_default_timeout(45000)
        self.context.set_default_navigation_timeout(60000)
        # Injecting Context
        Tarnished.apply_stealth(self.context)
        # Add stealth techniques manually
        self.page = await self.context.new_page()
        
        # Set page timeouts
        self.page.set_default_timeout(45000)
        self.page.set_default_navigation_timeout(60000)
        
        # Remove webdriver property
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            if (!window.chrome) {
                window.chrome = {};
            }
            
            Object.defineProperty(navigator, 'language', {
                get: () => 'en-US',
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)
        
        # Intercept GraphQL API calls
        await self.setup_interception()
        
        # Login if not already logged in
        
        await self.page.goto('https://www.instagram.com/challenge/?next=https%3A%2F%2Fwww.instagram.com%2Faccounts%2Fonetap%2F%3Fnext%3D%252F%26__coig_challenged%3D1', wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(3)
        await self.page.goto('https://www.instagram.com/accounts/login/', wait_until='domcontentloaded', timeout=60000)
        
        if not await self.check_logged_in():
            print("🔐 Not logged in, attempting to login...")
            login_success = await self.perform_login()
            if not login_success:
                raise Exception("Login failed")
        else:
            print("✅ Already logged in")
        
        self.is_initialized = True
        return True

    async def handle_challenge_page(self) -> bool:
        """Handle Instagram challenge pages that appear after login"""
        print("🛡️ Handling challenge page...")
        
        # Wait for page to load completely
        await asyncio.sleep(5)
        
        # Check if we're still on challenge page
        if not await self.is_on_challenge_page():
            print("✅ Challenge page resolved automatically")
            return True
        
        print("🎯 Looking for Dismiss button...")
        
        # SIMPLE APPROACH: Just click the button with the exact structure from your HTML
        try:
            # Method 1: Direct click using the exact structure
            dismiss_button = await self.page.query_selector('div[data-bloks-name="bk.components.Flexbox"][aria-label="Dismiss"]')
            if dismiss_button:
                print("✅ Found exact Dismiss button")
                await dismiss_button.click()
                await asyncio.sleep(3)
                print("✅ Dismiss button clicked")
                return True
        except Exception as e:
            print(f"⚠️ Exact button click failed: {e}")
        
        # Method 2: Click by text content
        try:
            dismiss_by_text = await self.page.query_selector('text="Dismiss"')
            if dismiss_by_text:
                print("✅ Found Dismiss by text")
                await dismiss_by_text.click()
                await asyncio.sleep(3)
                print("✅ Dismiss text clicked")
                return True
        except Exception as e:
            print(f"⚠️ Text click failed: {e}")
        
        # Method 3: Force JavaScript click
        try:
            print("🔧 Trying force JavaScript click...")
            js_result = await self.page.evaluate("""
            function clickDismiss() {
                // Try exact match first
                const exactButtons = Array.from(document.querySelectorAll('*')).filter(el => 
                    el.textContent && el.textContent.trim() === 'Dismiss'
                );
                
                for (let btn of exactButtons) {
                    try {
                        btn.click();
                        console.log('Clicked exact Dismiss button');
                        return true;
                    } catch(e) {
                        console.log('Failed exact click:', e);
                    }
                }
                
                // Try partial match
                const partialButtons = Array.from(document.querySelectorAll('*')).filter(el => 
                    el.textContent && el.textContent.includes('Dismiss')
                );
                
                for (let btn of partialButtons) {
                    try {
                        btn.click();
                        console.log('Clicked partial Dismiss button');
                        return true;
                    } catch(e) {
                        console.log('Failed partial click:', e);
                    }
                }
                
                return false;
            }
            clickDismiss();
            """)
            
            if js_result:
                print("✅ JavaScript click successful")
                await asyncio.sleep(3)
                return True
        except Exception as e:
            print(f"⚠️ JavaScript click failed: {e}")
        
        # Method 4: Try multiple selectors
        selectors = [
            'div[data-bloks-name="bk.components.Flexbox"][aria-label="Dismiss"]',
            'div[role="button"][aria-label="Dismiss"]',
            'button:has-text("Dismiss")',
            'div:has-text("Dismiss")',
            '//span[text()="Dismiss"]',
            '//div[contains(@style, "background: rgb(0, 149, 246)")]'
        ]
        
        for selector in selectors:
            try:
                if selector.startswith('//'):
                    element = await self.page.wait_for_selector(f'xpath={selector}', timeout=5000)
                else:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                
                if element:
                    print(f"✅ Found button with selector: {selector}")
                    await element.click()
                    await asyncio.sleep(3)
                    print("✅ Button clicked successfully")
                    return True
            except Exception as e:
                print(f"⚠️ Selector {selector} failed: {e}")
                continue
        
        print("❌ All challenge resolution attempts failed")
        return False

    async def is_on_challenge_page(self) -> bool:
        """Check if currently on a challenge page"""
        try:
            current_url = self.page.url
            print(f"🔍 Current URL: {current_url}")
            
            # Check URL for challenge indicators
            if 'challenge' in current_url.lower() or '__coig_challenged' in current_url:
                print("🔍 Challenge detected in URL")
                return True
            
            # Check page content
            page_text = await self.page.evaluate("() => document.body.innerText")
            if 'dismiss' in page_text.lower():
                print("🔍 Challenge detected in page content (Dismiss text found)")
                return True
                
            return False
        except Exception as e:
            print(f"⚠️ Error checking challenge page: {e}")
            return False
    
    async def perform_login(self):
        """Perform login with credentials from environment"""
        INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
        INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
        
        if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
            raise Exception("Instagram credentials not found in environment variables")
        
        print(f"👤 Attempting login for: {INSTAGRAM_USERNAME}")
        
        # Navigate to login
        await self.page.goto(
            'https://www.instagram.com/accounts/login/', 
            wait_until='domcontentloaded', 
            timeout=60000
        )
        
        # Wait for login form
        try:
            await self.page.wait_for_selector('input[name="username"]', timeout=15000)
        except:
            if await self.check_logged_in():
                print("✅ Already logged in")
                return True
            raise Exception("Login form not found")
        
        # Fill login form
        await self.page.fill('input[name="username"]', INSTAGRAM_USERNAME)
        await self.page.fill('input[name="password"]', INSTAGRAM_PASSWORD)
        
        await asyncio.sleep(2)
        
        # Click login button
        try:
            await self.page.click('button[type="submit"]')
            print("✅ Login button clicked")
        except:
            try:
                await self.page.click('button:has-text("Log in")')
                print("✅ Login button clicked (alternative)")
            except:
                raise Exception("Could not click login button")
        
        # Wait for login to complete - with proper challenge handling
        print("⏳ Waiting for login completion...")
        
        # Wait for navigation to complete
        try:
            await self.page.wait_for_load_state('networkidle', timeout=30000)
        except:
            pass
        
        await asyncio.sleep(5)
        
        # CRITICAL FIX: Always check for challenge page after login
        current_url = self.page.url
        print(f"🔍 Post-login URL: {current_url}")
        
        # If we're on challenge page, handle it
        if await self.is_on_challenge_page():
            print("🛡️ Challenge page detected after login, handling...")
            challenge_success = await self.handle_challenge_page()
            if challenge_success:
                print("✅ Challenge handled successfully")
                # Verify we're actually logged in now
                if await self.check_logged_in():
                    print("✅ Verified: Properly logged in after challenge")
                    await self.context.storage_state(path=os.path.join(self.user_data_dir, 'auth.json'))
                    return True
                else:
                    print("❌ Not properly logged in after challenge")
                    return False
            else:
                print("❌ Failed to handle challenge")
                return False
        
        # Check if we're properly logged in (not on challenge page)
        if await self.check_logged_in():
            print("✅ Login successful!")
            await self.context.storage_state(path=os.path.join(self.user_data_dir, 'auth.json'))
            return True
        
        print("❌ Login failed - unknown reason")
        return False
    
    async def setup_interception(self):
        """Intercept GraphQL API calls"""
        self.graphql_calls = []

        async def on_response(response):
            if "graphql" in response.url:
                try:
                    graphql_data = {
                        "timestamp": time.time(),
                        "url": response.url,
                        "status": response.status,
                        "status_text": response.status_text,
                        "ok": response.ok,
                        "headers": dict(response.headers),
                        "request": {},
                        "response_body": None,
                    }

                    req = response.request
                    graphql_data["request"] = {
                        "method": req.method,
                        "headers": dict(req.headers),
                        "post_data": req.post_data,
                    }

                    try:
                        graphql_data["response_body"] = await response.json()
                    except Exception:
                        text = await response.text()
                        graphql_data["response_body"] = text[:500]

                    self.graphql_calls.append(graphql_data)

                except Exception as e:
                    print(f"⚠️ Error processing GraphQL response: {e}")

        self.page.on("response", on_response)
        print("✅ GraphQL response interception setup complete.")
    
    async def check_logged_in(self) -> bool:
        """Check if user is logged in - properly checks if NOT on challenge page"""
        try:
            await asyncio.sleep(1) 
            # First check if we're on a challenge page
            if await self.is_on_challenge_page():
                print("🔍 Check logged in: Currently on challenge page")
                return False
            
            # Then check for login indicators
            selectors = [
                'svg[aria-label="Home"]',
                'a[href="/"]',
                'nav',
                'a[href*="direct/inbox"]',
                '[data-testid="user-avatar"]',
            ]
            
            for selector in selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        print(f"🔍 Check logged in: Found {selector}")
                        return True
                except:
                    continue
            
            # Check URL
            current_url = self.page.url
            if ('instagram.com' in current_url and 
                '/accounts/login' not in current_url and
                'login' not in current_url.lower() and
                'challenge' not in current_url.lower()):
                print("🔍 Check logged in: Valid Instagram URL")
                return True
                
            return False
        except Exception as e:
            print(f"⚠️ Error checking login status: {e}")
            return False
    
    async def scrape_user_reels_by_username(self, username: str,redirect_url:str=None) -> Dict:
        """Scrape user profile and capture all GraphQL API calls"""
        print(f"🎯 Scraping profile: {username}")
        
        self.graphql_calls.clear()
        redirect_url = f'https://www.instagram.com/{username}/reels/' if not redirect_url else redirect_url

        
        navigation_success = False
        try:
            print(f"🔗 Trying URL: {redirect_url}")
            await self.page.goto(redirect_url, wait_until='domcontentloaded', timeout=45000)
            navigation_success = True
        except Exception as e:
            result= {
                    'profile_url': redirect_url,
                    'username': username,
                    'page_content_preview': content_preview,
                    'graphql_calls': self.graphql_calls,
                    'total_graphql_calls': len(self.graphql_calls),
                    'scraped_at': time.time(),
                    'navigation_success': navigation_success
                }
        
            print(f"✅ Scraping Failed: {e.args} GraphQL calls captured")
            return result
        
        if not navigation_success:
            print("❌ All navigation attempts failed")
        
        await asyncio.sleep(2)
        
        try:
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(1)
            await self.page.evaluate("window.scrollTo(0, 0);")
            await asyncio.sleep(0.5)
        except Exception as e:
            pass
        
        try:
            page_content = await self.page.content()
            content_preview = page_content[:500] + '...' if len(page_content) > 500 else page_content
        except:
            content_preview = "Could not retrieve page content"
        
        result = {
            'profile_url': redirect_url,
            'username': username,
            'page_content_preview': content_preview,
            'graphql_calls': self.graphql_calls,
            'total_graphql_calls': len(self.graphql_calls),
            'scraped_at': time.time(),
            'navigation_success': navigation_success
        }
        
        print(f"✅ Scraping completed: {len(self.graphql_calls)} GraphQL calls captured")
        return result
    
    async def close(self):
        """Close browser and cleanup"""
        if self.browser:
            await self.browser.close()
            self.is_initialized = False

# Global scraper instance
scraper = InstagramScraper(headless=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Instagram Scraper...")
    try:
        await scraper.initialize()
        print("✅ Instagram Scraper ready!")
    except Exception as e:
        print(f"❌ Failed to initialize scraper: {e}")
        print("⚠️  API will start but scraper may not be functional")
    yield
    print("🛑 Shutting down Instagram Scraper...")
    await scraper.close()

app = FastAPI(
    title="Instagram GraphQL Scraper",
    description="High-performance Instagram GraphQL API scraper with persistent sessions",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "message": "Instagram GraphQL Scraper API is running",
        "status": "ready" if scraper.is_initialized else "initializing",
        "endpoints": {
            "scrape": "GET /scrape/{username}",
            "status": "GET /status",
            "reload": "POST /reload",
            "docs": "GET /docs"
        }
    }

TOP_DEFAULT = 12
# {
#     "data": {
#         "user": {
#             "pk": "63956813063",

@app.get("/scrape/reels/{username}")
async def scrape_user(username: str, top_reels_count: Optional[int] = TOP_DEFAULT):
    start_time = time.time()
    try:
        if not scraper.is_initialized:
            try:
                await scraper.initialize()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Scraper not initialized: {str(e)}")

        print(f"📥 Received request to scrape: {username}")
        result = await scraper.scrape_user_reels_by_username(username)

        DOC_REELS = "24127588873492897"
        DOC_PROFILE = "24718565464492867"
        filter_doc_ids = [DOC_REELS]

        

        filtered_calls = []
        target_user_id = None
        user_data={}
        reels_data={}

        for call in result['graphql_calls']:
            post_data = call.get('request', {}).get('post_data', '') or ""
            response_body = call.get('response_body', {})
            # if any(doc_id in post_data for doc_id in [DOC_PROFILE]):?
            if not user_data:
                user__tempdata=response_body.get("data", {}).get("user", {})
                if user__tempdata.get("biography_with_entities") or  user__tempdata.get("account_type"):
                    target_user_id = response_body.get("data", {}).get("user", {}).get("id") or response_body.get("data", {}).get("user", {}).get("pk")
                    user_data=user__tempdata
            # if any(doc_id in post_data for doc_id in filter_doc_ids):
            #     filtered_calls.append(call)
            if not reels_data:
                reels_tem_data=response_body.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("edges", [])
                # xdt_api__v1__clips__user__connection_v2

                if reels_tem_data  and target_user_id:
                    filtered_calls.append(call)
                    reels_data=reels_tem_data
                    medias = []
                    remaining_count = top_reels_count
                    
                    # Extract initial edges from the first response
                    edges = response_body.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("edges", [])
                    for edge in edges:
                        if remaining_count <= 0:
                            break
                        medias.append(edge.get("node", {}))
                        remaining_count -= 1
                    
                    page_info = response_body.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("page_info", {})
                    has_next_page = page_info.get("has_next_page", False)
                    end_cursor = page_info.get("end_cursor")
                    current_cursor = end_cursor
                    max_iterations = 50
                    iteration = 0

                    # print("medias",len(medias))

                    while remaining_count > 0 and iteration < max_iterations and has_next_page and current_cursor:
                        iteration += 1

                        # Get the original post data from the intercepted call
                        original_post_data = call.get('request', {}).get('post_data', '')
                        
                        if not original_post_data:
                            print("❌ No original post data found for pagination")
                            break
                        
                        # Parse the original form data to get all required parameters
                        try:
                            parsed_data = parse_qs(original_post_data)
                        except Exception as e:
                            print(f"❌ Error parsing post data: {e}")
                            break
                        
                        # Update only the variables parameter with new cursor and page size
                        variables_dict = {
                            "after": current_cursor,
                            "before": None,
                            "data": {
                                "include_feed_video": True,
                                "page_size": min(remaining_count, 12),
                                "target_user_id": target_user_id
                            },
                            "first": min(remaining_count, 12),
                            "last": None
                        }
                        
                        # Update the variables in the parsed data
                        parsed_data['variables'] = [json.dumps(variables_dict)]
                        
                        # Ensure we're using the correct doc_id from the working request
                        parsed_data['doc_id'] = ['9905035666198614']  # Use the working doc_id
                        
                        # Rebuild the form data with ALL original parameters
                        form_data_parts = []
                        for key, values in parsed_data.items():
                            for value in values:
                                # URL encode the values
                                form_data_parts.append(f"{key}={value}")
                        
                        payload = '&'.join(form_data_parts)

                        # Prepare cookies from the browser context
                        cookies = {}
                        try:
                            browser_cookies = await scraper.context.cookies()
                            for cookie in browser_cookies:
                                cookies[cookie['name']] = cookie['value']
                        except Exception as e:
                            print(f"⚠️ Error getting cookies: {e}")
                            # Fallback to cookies from request headers
                            cookie_header = call.get('request', {}).get('headers', {}).get('cookie', '')
                            if cookie_header:
                                for cookie_part in cookie_header.split(';'):
                                    if '=' in cookie_part:
                                        name, value = cookie_part.strip().split('=', 1)
                                        cookies[name] = value
                        
                        # Ensure we have essential cookies
                        essential_cookies = ['csrftoken', 'sessionid']
                        missing_cookies = [c for c in essential_cookies if c not in cookies]
                        if missing_cookies:
                            print(f"⚠️ Missing essential cookies: {missing_cookies}")
                        
                        async with httpx.AsyncClient() as client:
                            # Use the exact same headers from the original request
                            headers = call.get('request', {}).get('headers', {}).copy()
                            
                            # Update critical headers
                            headers.update({
                                'content-type': 'application/x-www-form-urlencoded',
                                'x-fb-friendly-name': 'PolarisProfileReelsTabContentQuery_connection',
                                'sec-fetch-dest': 'empty',
                                'sec-fetch-mode': 'cors', 
                                'sec-fetch-site': 'same-origin',
                                'priority': 'u=1, i',
                                'origin': 'https://www.instagram.com',
                                'referer': f'https://www.instagram.com/{username}/reels/',
                            })
                            
                            # Remove content-length as it will be recalculated
                            headers.pop('content-length', None)
                            
                            request = client.build_request(
                                method="POST",
                                url="https://www.instagram.com/graphql/query",
                                headers=headers,
                                cookies=cookies,
                                data=payload,
                                timeout=30.0
                            )
                            
                            print(f"🔍 Pagination request #{iteration}: cursor={current_cursor}, remaining={remaining_count}")
                            try:
                                resp = await client.send(request)
                                resp.raise_for_status()
                            except Exception as e:
                                print(f"❌ HTTP request failed: {e}")
                                break

                        try:
                            resp_json = resp.json()
                            
                            # Check for errors
                            if 'errors' in resp_json:
                                print(f"❌ GraphQL error: {resp_json['errors']}")
                                break
                            
                            if 'data' not in resp_json:
                                print(f"❌ No data in response: {resp_json}")
                                break
                                
                            edges = resp_json.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("edges", [])
                            page_info = resp_json.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("page_info", {})
                            has_next_page = page_info.get("has_next_page", False)
                            end_cursor = page_info.get("end_cursor")

                            print(f"✅ Got {len(edges)} reels, has_next_page: {has_next_page}")

                            # Add edges to paginated media
                            for edge in edges:
                                if remaining_count <= 0:
                                    break
                                medias.append(edge.get("node", {}))
                                remaining_count -= 1

                            if not has_next_page or not end_cursor:
                                print("ℹ️ No more pages available")
                                break

                            current_cursor = end_cursor
                            await asyncio.sleep(1)  # Small delay between requests

                        except json.JSONDecodeError as e:
                            print(f"❌ JSON decode error: {e}")
                            print(f"Response text: {resp.text[:500]}")
                            break
                        except Exception as e:
                            print(f"❌ Error parsing reels response: {e}")
                            break

                    # Update the original call with paginated data
                    call["paginated_media"] = medias
                    # Create a copy of response_body to avoid modifying the original
                    updated_response = response_body.copy()
                    if "data" not in updated_response:
                        updated_response["data"] = {}
                    updated_response["data"]["xdt_api__v1__clips__user__connection_v2"] = {
                        "edges": medias,
                        "page_info": page_info
                    }
                    call["response_body"] = updated_response

        processing_time = time.time() - start_time

        return {
            "success": True,
            "username": username,
            "processing_time_seconds": round(processing_time, 2),
            "total_graphql_calls": len(filtered_calls),
            "navigation_success": result.get("navigation_success", True),
            "scraped_at": result.get("scraped_at"),
            "reels_count": sum(len(call.get("paginated_media", [])) for call in filtered_calls if call.get("paginated_media")),
            "reels_data": [
                call.get("response_body", {}) 
                for call in filtered_calls 
            ],
            "user_data":user_data,
            "metadata": {
                "profile_url": result.get("profile_url"),
                "target_user_id": target_user_id,
                "page_content_preview": result.get("page_content_preview")[:200] if result.get("page_content_preview") else None
            }
        }

    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "processing_time_seconds": round(processing_time, 2),
                "username": username
            }
        )
    
@app.get("/status")
async def get_status():
    status_info = {
        "status": "ready" if scraper.is_initialized else "not_initialized",
        "is_initialized": scraper.is_initialized,
        "user_data_dir": scraper.user_data_dir,
        "headless": scraper.headless,
        "timestamp": time.time()
    }
    
    auth_file = os.path.join(scraper.user_data_dir, 'auth.json')
    status_info['auth_file_exists'] = os.path.exists(auth_file)
    
    return status_info

@app.post("/reload")
async def reload_scraper():
    try:
        await scraper.close()
        await asyncio.sleep(2)
        await scraper.initialize()
        return {
            "success": True,
            "message": "Scraper reloaded successfully",
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
        )

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=9010,
        access_log=True,
        timeout_keep_alive=60,
        timeout_graceful_shutdown=30
    )