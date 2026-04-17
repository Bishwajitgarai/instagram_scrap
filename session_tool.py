import json
import os
import sys

# Standard location for session data
USER_DATA_DIR = "instagram_profile"
SESSION_FILE = os.path.join(USER_DATA_DIR, "instagram_session.json")

def import_from_cookie_string(cookie_str: str):
    """
    Parses a raw cookie string into a dict and saves it.
    Example: 'csrftoken=xyz; sessionid=123; ...'
    """
    cookies = {}
    try:
        # Step 1: Split by semicolon
        parts = cookie_str.split(';')
        for part in parts:
            if '=' in part:
                name, value = part.strip().split('=', 1)
                cookies[name] = value
        
        if not cookies:
            print(" Error: No valid cookies found in that string.")
            return

        # Step 2: Save to file
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        with open(SESSION_FILE, "w") as f:
            json.dump(cookies, f, indent=4)
        
        print(f" Successfully imported {len(cookies)} cookies to {SESSION_FILE}")
        print(" Your scraper is now authorized and ready for Vercel!")

    except Exception as e:
        print(f" Error parsing cookies: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python session_tool.py \"csrftoken=...; sessionid=...;\"")
    else:
        import_from_cookie_string(sys.argv[1])
