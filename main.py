from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
from contextlib import asynccontextmanager
from email_service import EmailService
from config import Config

email_service = EmailService()
config = Config()

class EmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    message: str
    from_name: Optional[str] = None

class EmailResponse(BaseModel):
    success: bool
    message: str
    email_id: Optional[str] = None

API_KEY = os.getenv("API_KEY")

async def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if not API_KEY:
        # If not configured, deny to avoid open relay
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured"
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize email service on startup"""
    await email_service.initialize()
    yield

app = FastAPI(title="Email API Service", version="1.0.0", lifespan=lifespan)

@app.post("/send-email", response_model=EmailResponse, dependencies=[Depends(require_api_key)])
async def send_email(email_request: EmailRequest, background_tasks: BackgroundTasks):
    """
    Send an email using Gmail SMTP
    """
    try:
        # Add email sending to background tasks for better performance
        background_tasks.add_task(
            email_service.send_email,
            email_request.to_email,
            email_request.subject,
            email_request.message,
            email_request.from_name
        )

        return EmailResponse(
            success=True,
            message="Email queued for sending",
            email_id=f"{email_request.to_email}_{hash(email_request.subject)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue email: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "email-api"}

@app.get("/config/status")
async def config_status():
    """Check if Gmail configuration is set up"""
    is_configured = config.is_gmail_configured()
    return {
        "gmail_configured": is_configured,
        "message": "Gmail is configured and ready" if is_configured else "Gmail configuration needed"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)