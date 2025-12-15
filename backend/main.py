"""Mowafy Sender - Facebook Pages Messaging Application
Basic structure from scratch
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Mowafy Sender Web API",
    description="Facebook Pages Messaging Tool",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
FB_API_VERSION = "v18.0"
FB_GRAPH_URL = f"https://graph.facebook.com/{FB_API_VERSION}"

# Models
class FacebookPage(BaseModel):
    id: str
    name: str
    category: Optional[str] = None

class ConversationMessage(BaseModel):
    id: str
    sender_name: str
    sender_id: str
    message: str
    created_time: str

class MessageSendConfig(BaseModel):
    page_id: str
    access_token: str
    message_text: str
    recipient_ids: List[str]
    delay_between_messages: int = 5  # seconds between messages
    batch_size: int = 10  # number of messages before batch delay
    batch_delay: int = 30  # seconds between batches

# Health Check
@app.get("/")
async def root():
    return {
        "status": "ok",
        "app": "Mowafy Sender",
        "version": "1.0.0"
    }

# OAuth Endpoints
@app.get("/api/auth/facebook/redirect")
async def facebook_auth_redirect():
    scope = "pages_manage_messages,pages_read_engagement,pages_manage_metadata"
    redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/api/auth/facebook/callback")
    
    auth_url = (
        f"https://www.facebook.com/{FB_API_VERSION}/dialog/oauth?"
        f"client_id={FB_APP_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={scope}&"
        f"display=popup&"
        f"response_type=code"
    )
    
    return {"auth_url": auth_url}

@app.get("/api/auth/facebook/callback")
async def facebook_auth_callback(code: str):
    try:
        redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/api/auth/facebook/callback")
        token_url = f"{FB_GRAPH_URL}/oauth/access_token"
        params = {
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "redirect_uri": redirect_uri,
            "code": code
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(token_url, params=params)
            data = response.json()
            
            if "access_token" not in data:
                raise HTTPException(status_code=400, detail="Failed to get access token")
            
            return {
                "access_token": data["access_token"],
                "token_type": data.get("token_type", "bearer")
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Pages Endpoints
@app.get("/api/pages")
async def get_user_pages(access_token: str) -> List[FacebookPage]:
    try:
        url = f"{FB_GRAPH_URL}/me/accounts"
        params = {
            "access_token": access_token,
            "fields": "id,name,category"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise HTTPException(status_code=400, detail=data["error"]["message"])
            
            pages = [FacebookPage(**page) for page in data.get("data", [])]
            return pages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Conversations Endpoints
@app.get("/api/conversations")
async def get_page_conversations(page_id: str, access_token: str):
    try:
        url = f"{FB_GRAPH_URL}/{page_id}/conversations"
        params = {
            "access_token": access_token,
            "fields": "id,participants,senders,created_time",
            "limit": 100
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise HTTPException(status_code=400, detail=data["error"]["message"])
            
            return data.get("data", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversation-messages")
async def get_conversation_messages(conversation_id: str, access_token: str) -> List[ConversationMessage]:
    try:
        url = f"{FB_GRAPH_URL}/{conversation_id}/messages"
        params = {
            "access_token": access_token,
            "fields": "id,from{name},message,created_time",
            "limit": 100
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if "error" in data:
                raise HTTPException(status_code=400, detail=data["error"]["message"])
            
            messages = []
            for msg in data.get("data", []):
                message = ConversationMessage(
                    id=msg["id"],
                    sender_name=msg["from"]["name"],
                    sender_id=msg["from"]["id"],
                    message=msg.get("message", ""),
                    created_time=msg["created_time"]
                )
                messages.append(message)
            
            return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Send Messages Endpoints
@app.post("/api/send-messages")
async def send_messages(
    config: MessageSendConfig,
    background_tasks: BackgroundTasks
):
    try:
        background_tasks.add_task(send_messages_task, config)
        return {
            "status": "processing",
            "message": f"Started sending {len(config.recipient_ids)} messages",
            "total_recipients": len(config.recipient_ids)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def send_messages_task(config: MessageSendConfig):
    url = f"{FB_GRAPH_URL}/{config.page_id}/messages"
    
    successful = 0
    failed = 0
    
    try:
        async with httpx.AsyncClient() as client:
            for index, recipient_id in enumerate(config.recipient_ids):
                payload = {
                    "recipient": {"id": recipient_id},
                    "message": {"text": config.message_text}
                }
                params = {"access_token": config.access_token}
                
                try:
                    response = await client.post(url, json=payload, params=params)
                    if response.status_code == 200:
                        successful += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                
                # Delay logic
                if (index + 1) % config.batch_size == 0 and (index + 1) < len(config.recipient_ids):
                    await asyncio.sleep(config.batch_delay)
                else:
                    await asyncio.sleep(config.delay_between_messages)
        
    except Exception as e:
        print(f"Error in send_messages_task: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
