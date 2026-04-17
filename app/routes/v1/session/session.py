from fastapi import APIRouter, HTTPException, Request
from app import scraper
import json
import os

router = APIRouter()

@router.post("/import")
async def import_session(request: Request):
    """
    Import a session cookie list.
    Expected format: A JSON array of cookie objects or a dict of {name: value}
    """
    try:
        cookies_data = await request.json()
        
        # Normalize format (handle both list of dicts and simple dict)
        session_cookies = {}
        if isinstance(cookies_data, list):
            for cookie in cookies_data:
                session_cookies[cookie['name']] = cookie['value']
        elif isinstance(cookies_data, dict):
            session_cookies = cookies_data
        else:
            raise ValueError("Invalid cookie format. Provide a List of cookie dicts or a Name/Value dict.")

        # Save to session file
        os.makedirs(scraper.user_data_dir, exist_ok=True)
        with open(scraper.session_file, "w") as f:
            json.dump(session_cookies, f)

        # Reload scraper and verify
        await scraper.close()
        success = await scraper.initialize()
        
        return {
            "success": success,
            "message": "Session cookies imported successfully",
            "logged_in": await scraper.check_logged_in()
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import session: {str(e)}")

@router.get("/status")
async def session_status():
    """Check current session health"""
    return {
        "is_initialized": scraper.is_initialized,
        "logged_in": await scraper.check_logged_in() if scraper.is_initialized else False,
        "session_file": scraper.session_file,
        "exists": os.path.exists(scraper.session_file)
    }
