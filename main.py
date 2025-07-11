import requests
import json
import uvicorn
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any

# --- Load Environment Variables ---
# Create a .env file in the same directory as this script
# and add your credentials like this:
# ZAWA_INSTANCE_ID=your_instance_id_here
# ZAWA_SESSION_ID=your_session_id_here
load_dotenv()

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Zawa Message Sender API",
    description="An API to send generic messages or specific stock notifications via the Zawa service. Reads credentials from a .env file.",
    version="1.2.0"
)

# --- Retrieve Credentials from Environment ---
ZAWA_INSTANCE_ID = os.getenv("ZAWA_INSTANCE_ID")
ZAWA_SESSION_ID = os.getenv("ZAWA_SESSION_ID")

# --- Startup Validation ---
@app.on_event("startup")
async def startup_event():
    """Check for environment variables on startup."""
    if not ZAWA_INSTANCE_ID or not ZAWA_SESSION_ID:
        raise RuntimeError(
            "FATAL: ZAWA_INSTANCE_ID and ZAWA_SESSION_ID must be set "
            "in the environment or a .env file."
        )

# --- Internal Function to Call Zawa API ---
from typing import Optional

def call_zawa_api(instance_id: Optional[str], session_id: Optional[str], body: Dict[str, Any]):
    """
    Internal function to make the actual call to the Zawa API.
    
    Args:
        instance_id (str): The instance ID for the header.
        session_id (str): The session ID for the header.
        body (Dict[str, Any]): The request body to be sent as JSON.

    Returns:
        A dictionary with the JSON response from the Zawa API.
        
    Raises:
        HTTPException: If the request to the Zawa API fails.
    """
    if instance_id is None or session_id is None:
        raise HTTPException(
            status_code=500,
            detail="ZAWA_INSTANCE_ID and ZAWA_SESSION_ID must be set in the environment or .env file."
        )
    api_url = "https://api-zawa.azickri.com/message"
    headers = {
        'id': instance_id,
        'session-id': session_id,
        'Content-Type': 'application/json',
        'Accept': '*/*'
    }
    
    print("--- Forwarding Request to Zawa API ---")
    print(f"URL: {api_url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Body: {json.dumps(body, indent=2)}")
    print("------------------------------------")

    try:
        response = requests.post(api_url, headers=headers, json=body)
        response.raise_for_status()  # Raise an exception for 4xx/5xx status codes
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        raise HTTPException(
            status_code=http_err.response.status_code,
            detail=f"Error from Zawa API: {http_err.response.text}"
        )
    except requests.exceptions.RequestException as req_err:
        raise HTTPException(
            status_code=503, # Service Unavailable
            detail=f"Could not connect to Zawa API: {req_err}"
        )

# --- Pydantic Models for Request Body Validation ---

class GenericMessagePayload(BaseModel):
    """Defines the structure for a generic message request."""
    phone: str = Field(..., example="6281234567890", description="Recipient's phone number.")
    message_type: str = Field(..., alias="type", example="text", description="Type of message (text, image, etc.).")
    content: Dict[str, Any] = Field(..., description="The actual message content object, e.g., {'text': 'Hello'}.")

class StockNotificationPayload(BaseModel):
    """Defines the structure for a stock level notification."""
    phone: str = Field(..., example="6281234567890", description="Recipient's phone number (e.g., the PIC's number).")
    pic_name: str = Field(..., example="Budi", description="Name of the Person In Charge.")
    material_id: str = Field(..., example="CHEM-0042", description="The unique ID of the material.")
    short_desc: str = Field(..., example="Hydrochloric Acid", description="A short description of the material.")
    stock: int = Field(..., example=5, description="The current stock level.")


# --- API Endpoints ---

@app.post("/send-message/", summary="Send a generic message via Zawa", tags=["Generic"])
async def send_generic_message_endpoint(payload: GenericMessagePayload):
    """
    Receives generic message details and forwards them to the Zawa API.
    
    The structure of the `content` object should match the `message_type`.
    - For `text`: `{"text": "Your message"}`
    - For `image`: `{"image": {"url": "...", "mimetype": "..."}}`
    """
    zawa_body = {
        "phone": payload.phone,
        "type": payload.message_type,
        **payload.content 
    }
    if not ZAWA_INSTANCE_ID or not ZAWA_SESSION_ID:
        raise HTTPException(
            status_code=500,
            detail="ZAWA_INSTANCE_ID and ZAWA_SESSION_ID must be set in the environment or .env file."
        )
    response_data = call_zawa_api(
        instance_id=ZAWA_INSTANCE_ID,
        session_id=ZAWA_SESSION_ID,
        body=zawa_body
    )
    return {"status": "success", "zawa_response": response_data}

@app.post("/send-stock-notification/", summary="Send a formatted stock level notification", tags=["Notifications"])
async def send_stock_notification_endpoint(payload: StockNotificationPayload):
    """
    Takes specific stock details, formats a notification message, and sends it.
    """
    # Format the notification message string as requested
    message = (
        f"⚠️ *MINIMUM STOCK ALERT* ⚠️\n\n"
        f"Hello *{payload.pic_name}*,\n\n"
        f"The following material has fallen below the minimum stock level:\n\n"
        f"*- Material:* {payload.short_desc}\n"
        f"*- Material ID:* {payload.material_id}\n"
        f"*- CURRENT STOCK:* *{payload.stock}*\n\n"
        f"Please take *IMMEDIATE ACTION* to replenish the stock."
    )
    # Construct the body for the Zawa API call
    zawa_body = {
        "phone": payload.phone,
        "type": "text",
        "text": message
    }

    # Call the internal function to interact with the Zawa API
    response_data = call_zawa_api(
        instance_id=ZAWA_INSTANCE_ID,
        session_id=ZAWA_SESSION_ID,
        body=zawa_body
    )
    
    return {"status": "success", "zawa_response": response_data}


# --- Main entry point to run the server ---
if __name__ == "__main__":
    # Run the FastAPI server on localhost at port 9876
    print("Starting FastAPI server at http://localhost:9876")
    print("See API documentation at http://localhost:9876/docs")
    uvicorn.run(app, host="0.0.0.0", port=9876)