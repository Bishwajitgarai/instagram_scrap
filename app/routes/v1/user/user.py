from fastapi import APIRouter, HTTPException
import time
from app import scraper

router = APIRouter()

@router.post("/by/username")
async def user_detials(username: str):
    """Scrape user profile data"""
    try:
        start_time = time.time()
        result = await scraper.redirect( f"https://www.instagram.com/{username}/")
        user_data={}
        for call in result['graphql_calls']:
            response_body = call.get('response_body', {})
            
            if not user_data:
                user_temp_data = response_body.get("data", {}).get("user", {})
                if user_temp_data.get("biography_with_entities") or user_temp_data.get("account_type"):
                    user_data = user_temp_data
                    break
        processing_time = time.time() - start_time
        return {
                "success": True,
                "username": username,
                "processing_time_seconds": round(processing_time, 2),
                "total_graphql_calls": len(result.get("graphql_calls", [])),
                "user_data":user_data,
                "navigation_success": result.get("navigation_success", True),
                "scraped_at": result.get("scraped_at"),
                "profile_data": {
                    "profile_url": result.get("profile_url"),
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