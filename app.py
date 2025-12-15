from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from urllib.parse import urlencode

app = FastAPI(
    title="Mowafy Sender Web API",
    description="Facebook Pages Messaging Tool",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FB_APP_ID = os.getenv("FB_APP_ID", "856582480115080")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "44d1bad3e4de8561401aef37c5")
FB_REDIRECT_URI = os.getenv("FB_REDIRECT_URI", "https://balanced-education-production.up.railway.app/auth/facebook/callback")

@app.get("/")
def root():
    return {
        "message": "Mowafy Sender Web API",
        "status": "running",
        "docs": "/docs",
        "app_id": FB_APP_ID
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/auth/login")
def facebook_login():
    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": FB_REDIRECT_URI,
        "response_type": "code",
        "scope": "pages_show_list,pages_read_engagement,pages_manage_metadata,pages_messaging,business_management",
    }
    auth_url = f"https://www.facebook.com/v21.0/dialog/oauth?{urlencode(params)}"
    return {"auth_url": auth_url, "message": "Redirect to this URL to login with Facebook"}

@app.get("/auth/facebook/callback")
def facebook_callback(code: str = None, error: str = None):
    if error:
        return {"error": error}
    if code:
        return {
            "code": code,
            "message": "Authorization code received! Exchange this for tokens.",
            "next_step": "POST /auth/exchange-token with this code"
        }
    return {"error": "No authorization code received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
