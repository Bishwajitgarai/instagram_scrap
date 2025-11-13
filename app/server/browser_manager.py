import asyncio
import json
import os
import time
from typing import Dict, List, Optional
from urllib.parse import parse_qs
from dotenv import load_dotenv
import httpx
from playwright.async_api import async_playwright
from undetected_playwright import Tarnished
from app.core.config import settings

# Load environment variables
load_dotenv()

class InstagramScraper:
    def __init__(self):
        self.headless = settings.HEADLESS
        self.user_data_dir = settings.USER_DATA_DIR
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
            args=settings.BROWSER_ARGS,
            timeout=settings.BROWSER_TIMEOUT
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
    
    async def redirect(self, url: str, wait_until: str = 'domcontentloaded', timeout: Optional[int] = None):
        """Redirect to a specific URL"""
        if not self.is_initialized:
            raise Exception("Scraper not initialized. Call initialize() first.")
        
        timeout = timeout or settings.NAVIGATION_TIMEOUT
        print(f"🔗 Redirecting to: {url}")
        
        self.graphql_calls.clear()

        navigation_success = False
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=45000)
            navigation_success = True
        except Exception as e:
            result = {
                'url': url,
                'page_content_preview': "Navigation failed",
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
            'url': url,
            'page_content_preview': content_preview,
            'graphql_calls': self.graphql_calls,
            'total_graphql_calls': len(self.graphql_calls),
            'scraped_at': time.time(),
            'navigation_success': navigation_success
        }
        
        print(f"✅ Scraping completed: {len(self.graphql_calls)} GraphQL calls captured")
        return result

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
    
    async def scrape_user_reels_by_username(self, username: str, redirect_url: str = None) -> Dict:
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
            result = {
                'profile_url': redirect_url,
                'username': username,
                'page_content_preview': "Navigation failed",
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