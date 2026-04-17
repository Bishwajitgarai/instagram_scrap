from fastapi import APIRouter, HTTPException, Request
from app.core.config import limiter
import time
from app import scraper

router = APIRouter()

@router.post("/by/{username}")
@limiter.limit("5/minute")
async def user_detials(username: str, request: Request):
    """Scrape user profile data"""
    try:
        start_time = time.time()
        result = await scraper.redirect( f"https://www.instagram.com/{username}/")
        user_data = {}
        for call in result.get('graphql_calls', []):
            response_body = call.get('response_body', {})
            
            # Find user info in any GraphQL response
            data = response_body.get("data", {})
            if not data and "user" in response_body: # Handle flattened responses
                data = response_body
            
            user_temp_data = data.get("user", {})
            if user_temp_data and (user_temp_data.get("biography_with_entities") or user_temp_data.get("full_name") or user_temp_data.get("pk")):
                user_data = user_temp_data
                # If we found rich data, we can stop, otherwise keep looking
                if user_data.get("biography_with_entities"):
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

@router.post("/full/{username}")
@limiter.limit("5/minute")
async def full_scrape(username: str, request: Request):
    """
    Unified endpoint for all data: Profile, Reels, and Timeline.
    Includes Dynamic Cookie support and automated fail-backs.
    """
    try:
        start_time = time.time()
        result = await scraper.redirect(f"https://www.instagram.com/{username}/")
        
        # Data Extraction
        user_data = {}
        reels_data = []
        timeline_data = []

        for call in result.get('graphql_calls', []):
            body = call.get('response_body', {})
            data = body.get("data", {})
            if not data and "user" in body: 
                data = body # Handle flat structure
            
            # Profile Identification
            u = data.get("user", {})
            if u and (u.get("biography") or u.get("full_name")):
                user_data = u
            
            # Reels Extraction
            clips = data.get("xdt_api__v1__clips__user__connection_v2", {})
            if clips:
                reels_data.extend([e.get("node") for e in clips.get("edges", [])])
            
            # Timeline Extraction
            timeline = data.get("edge_owner_to_timeline_media", {})
            if timeline:
                timeline_data.extend([e.get("node") for e in timeline.get("edges", [])])

        processing_time = time.time() - start_time
        return {
            "success": True,
            "username": username,
            "processing_time_seconds": round(processing_time, 2),
            "user_data": user_data,
            "reels": reels_data,
            "timeline": timeline_data,
            "total_graphql_calls": len(result.get("graphql_calls", [])),
            "status": "Success" if user_data else "Profile Not Found",
            "scraped_at": result.get("scraped_at")
        }

    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": str(e), "username": username}
        )