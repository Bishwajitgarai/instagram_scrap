import asyncio
import json
import time
from typing import Optional
from urllib.parse import parse_qs
from fastapi import APIRouter, HTTPException
import httpx
from app import scraper
from app.core.config import settings

router = APIRouter()



@router.get("/reels/by/username")
async def scrape_user_reels(username: str, top_reels_count: Optional[int] = settings.TOP_DEFAULT):
    start_time = time.time()
    try:
        
        result = await scraper.redirect( f'https://www.instagram.com/{username}/reels/')

        filtered_calls = []
        target_user_id = None
        user_data = {}
        reels_data = {}

        for call in result['graphql_calls']:
            response_body = call.get('response_body', {})
            
            if not user_data:
                user_temp_data = response_body.get("data", {}).get("user", {})
                if user_temp_data.get("biography_with_entities") or user_temp_data.get("account_type"):
                    target_user_id = response_body.get("data", {}).get("user", {}).get("id") or response_body.get("data", {}).get("user", {}).get("pk")
                    user_data = user_temp_data
                    
            if not reels_data:
                reels_temp_data = response_body.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("edges", [])
                if reels_temp_data and target_user_id:
                    filtered_calls.append(call)
                    reels_data = reels_temp_data
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

                    while remaining_count > 0 and iteration < max_iterations and has_next_page and current_cursor:
                        iteration += 1

                        # Get the original post data from the intercepted call
                        original_post_data = call.get('request', {}).get('post_data', '')
                        
                        if not original_post_data:
                            print("No original post data found for pagination")
                            break
                        
                        # Parse the original form data to get all required parameters
                        try:
                            parsed_data = parse_qs(original_post_data)
                        except Exception as e:
                            print(f"Error parsing post data: {e}")
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
                                form_data_parts.append(f"{key}={value}")
                        
                        payload = '&'.join(form_data_parts)

                        # Prepare cookies from the browser context
                        cookies = {}
                        try:
                            browser_cookies = await scraper.context.cookies()
                            for cookie in browser_cookies:
                                cookies[cookie['name']] = cookie['value']
                        except Exception as e:
                            print(f"Error getting cookies: {e}")
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
                            print(f"Missing essential cookies: {missing_cookies}")
                        
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
                            
                            print(f"Pagination request #{iteration}: cursor={current_cursor}, remaining={remaining_count}")
                            try:
                                resp = await client.send(request)
                                resp.raise_for_status()
                            except Exception as e:
                                print(f"HTTP request failed: {e}")
                                break

                        try:
                            resp_json = resp.json()
                            
                            # Check for errors
                            if 'errors' in resp_json:
                                print(f"GraphQL error: {resp_json['errors']}")
                                break
                            
                            if 'data' not in resp_json:
                                print(f"No data in response: {resp_json}")
                                break
                                
                            edges = resp_json.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("edges", [])
                            page_info = resp_json.get("data", {}).get("xdt_api__v1__clips__user__connection_v2", {}).get("page_info", {})
                            has_next_page = page_info.get("has_next_page", False)
                            end_cursor = page_info.get("end_cursor")

                            print(f"Got {len(edges)} reels, has_next_page: {has_next_page}")

                            # Add edges to paginated media
                            for edge in edges:
                                if remaining_count <= 0:
                                    break
                                medias.append(edge.get("node", {}))
                                remaining_count -= 1

                            if not has_next_page or not end_cursor:
                                print("No more pages available")
                                break

                            current_cursor = end_cursor
                            await asyncio.sleep(1)  # Small delay between requests

                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e}")
                            print(f"Response text: {resp.text[:500]}")
                            break
                        except Exception as e:
                            print(f"Error parsing reels response: {e}")
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
            "user_data": user_data,
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

@router.get("/status")
async def get_status():
    """Get scraper status"""
    import os
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

@router.post("/reload")
async def reload_scraper():
    """Reload the scraper"""
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