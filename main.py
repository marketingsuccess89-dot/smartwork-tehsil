import os
import json
from dotenv import load_dotenv

# Force load environment variables from .env file overriding system vars
load_dotenv(override=True)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from src.agent_service import extract_text_from_image, transcribe_audio_dictation
from src.doc_builder import create_docx

app = FastAPI(title="Tehsil AI Document Operator MVP")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# API Endpoint models
class DocxRequest(BaseModel):
    text: str
    stamp_paper: bool = False

# Active WebSocket Sessions for Desktop/MS Word Sync
# Key: user_id (e.g. Gmail), Value: WebSocket connection
active_connections: dict[str, WebSocket] = {}

@app.websocket("/ws/desktop/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    Handles WebSocket connections from the MS Word Add-in / Desktop clients.
    """
    await websocket.accept()
    # Decode user_id in case it is URL-encoded (like emails)
    from urllib.parse import unquote
    clean_user_id = unquote(user_id).strip().lower()
    
    active_connections[clean_user_id] = websocket
    print(f"Desktop client connected: {clean_user_id}")
    
    # Send welcome status
    await websocket.send_json({
        "event": "connection_status",
        "status": "connected",
        "user_id": clean_user_id
    })
    
    try:
        while True:
            # Keep connection open, receive any client messages/heartbeats
            data = await websocket.receive_text()
            # Respond to ping/heartbeats
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        print(f"Desktop client disconnected: {clean_user_id}")
        if clean_user_id in active_connections:
            del active_connections[clean_user_id]

@app.get("/api/connection-status/{user_id}")
async def get_connection_status(user_id: str):
    """
    Checks if there is an active desktop/MS Word WebSocket connection for a user.
    Called by the mobile device to verify connection state.
    """
    clean_user_id = user_id.strip().lower()
    is_connected = clean_user_id in active_connections
    return {"user_id": clean_user_id, "connected": is_connected}

@app.post("/api/process-image")
async def process_image(file: UploadFile = File(...), user_id: str = Form(None)):
    """
    Receives an image file, runs Gemini Vision OCR, and broadcasts the result 
    to the user's active MS Word desktop connection.
    """
    # Allow standard image MIME types, application/octet-stream, or common image extensions
    is_img = (
        (file.content_type and file.content_type.startswith("image/"))
        or file.content_type == "application/octet-stream"
        or (file.filename and file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.heic', '.tiff')))
    )
    if not is_img:
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")
        
    try:
        contents = await file.read()
        mime_type = file.content_type if (file.content_type and file.content_type.startswith("image/")) else "image/jpeg"
        result = extract_text_from_image(contents, mime_type=mime_type)
        
        # Sync to Desktop MS Word if user_id is provided and active
        if user_id:
            clean_user_id = user_id.strip().lower()
            if clean_user_id in active_connections:
                websocket = active_connections[clean_user_id]
                try:
                    await websocket.send_json({
                        "event": "transcription_ready",
                        "text": result.transcribed_text
                    })
                    print(f"Synced image text to desktop for: {clean_user_id}")
                except Exception as ws_err:
                    print(f"Failed to send websocket message to {clean_user_id}: {ws_err}")
                    
        return result
    except ValueError as ve:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...), user_id: str = Form(None)):
    """
    Receives dictation audio, transcribes/formats it via Gemini, and broadcasts 
    the result to the user's active MS Word desktop connection.
    """
    # Accept standard audio formats, generic octet-stream, or common file extensions
    is_audio = (
        file.content_type.startswith("audio/") 
        or file.content_type == "application/octet-stream"
        or file.filename.endswith(('.wav', '.webm', '.mp3', '.m4a', '.ogg', '.aac', '.mp4'))
    )
    if not is_audio:
        raise HTTPException(status_code=400, detail="Uploaded file must be an audio file.")
        
    try:
        contents = await file.read()
        mime_type = file.content_type if file.content_type.startswith("audio/") else "audio/wav"
        result = transcribe_audio_dictation(contents, mime_type=mime_type)
        
        # Sync to Desktop MS Word if user_id is provided and active
        if user_id:
            clean_user_id = user_id.strip().lower()
            if clean_user_id in active_connections:
                websocket = active_connections[clean_user_id]
                try:
                    await websocket.send_json({
                        "event": "transcription_ready",
                        "text": result.transcribed_text
                    })
                    print(f"Synced audio text to desktop for: {clean_user_id}")
                except Exception as ws_err:
                    print(f"Failed to send websocket message to {clean_user_id}: {ws_err}")
                    
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process audio: {str(e)}")

@app.post("/api/generate-docx")
async def generate_docx(req: DocxRequest):
    """
    Generates a structured MS Word document (.docx) from raw text.
    """
    try:
        file_stream = create_docx(req.text, stamp_paper=req.stamp_paper)
        return StreamingResponse(
            file_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": "attachment; filename=Smart_Typing_Document.docx",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Word document: {str(e)}")

@app.post("/api/download-docx")
async def download_docx_form(text: str = Form(...), stamp_paper: bool = Form(False)):
    """
    Direct form download fallback for mobile browsers that block blob URLs.
    """
    try:
        file_stream = create_docx(text, stamp_paper=stamp_paper)
        return StreamingResponse(
            file_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": "attachment; filename=Smart_Typing_Document.docx",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Word document: {str(e)}")

import uuid
import time

shared_documents = {}

@app.post("/api/create-share-link")
async def create_share_link(req: DocxRequest):
    """Creates an instant 1-click download link for WhatsApp sharing."""
    # Evict expired documents (> 48 hours) to prevent memory leak
    now = time.time()
    expired = [k for k, v in shared_documents.items() if now - v.get('created_at', now) > 172800]
    for k in expired:
        shared_documents.pop(k, None)

    doc_id = str(uuid.uuid4())[:8]
    shared_documents[doc_id] = {
        'text': req.text,
        'stamp_paper': req.stamp_paper,
        'created_at': now
    }
    return {"doc_id": doc_id}

@app.get("/d/{doc_id}")
async def download_shared_doc(doc_id: str):
    """Direct 1-click download of the MS Word (.docx) document."""
    if doc_id not in shared_documents:
        raise HTTPException(status_code=404, detail="दस्तावेज़ लिंक समाप्त हो चुका है।")
    doc_data = shared_documents[doc_id]
    file_stream = create_docx(doc_data['text'], stamp_paper=doc_data['stamp_paper'])
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=Document_{doc_id}.docx",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

# Health check endpoint for Render keep-alive bot and uptime monitoring
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "smartwork-tehsil",
        "timestamp": time.time()
    }

import threading
import requests

def keep_alive_worker():
    """
    Background daemon that pings Render's public URL every 9 minutes (540s)
    to reset Render's 15-minute free-tier sleep timer, ensuring 24/7 uptime.
    """
    time.sleep(30)  # Initial boot buffer
    app_url = os.getenv("RENDER_EXTERNAL_URL", "https://thesmartwork.onrender.com").rstrip("/")
    ping_url = f"{app_url}/api/health"
    print(f"[KeepAlive] 24/7 Watchdog daemon started. Target: {ping_url}")
    while True:
        try:
            time.sleep(540)  # Ping every 9 minutes (well before 15-min sleep cutoff)
            res = requests.get(ping_url, timeout=25)
            print(f"[KeepAlive] Ping to {ping_url} -> Status {res.status_code}")
        except Exception as e:
            print(f"[KeepAlive] Heartbeat ping notice: {e}")

@app.on_event("startup")
def on_app_startup():
    if os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL"):
        t = threading.Thread(target=keep_alive_worker, daemon=True)
        t.start()
        print("[KeepAlive] 24/7 Render Keep-Alive background thread active.")

# Serve Static Files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
