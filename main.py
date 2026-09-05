import os
import re
import json
import uuid
import time
import threading
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Force load environment variables from .env file overriding system vars
load_dotenv(override=True)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
import uvicorn
import requests

from src.agent_service import extract_text_from_image, extract_text_from_images, transcribe_audio_dictation, get_model_status
from src.doc_builder import create_docx

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    cleanup_expired_docs()
    if os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL"):
        t = threading.Thread(target=keep_alive_worker, daemon=True)
        t.start()
        print("[KeepAlive] 24/7 Render Keep-Alive background thread active.")
    yield

app = FastAPI(title="Tehsil AI Document Operator MVP", lifespan=lifespan)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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

class SendToWordRequest(BaseModel):
    text: str
    stamp_paper: bool = False
    station_id: str
    pin: str = ""

# Active WebSocket Sessions for Desktop/MS Word Sync
# Key: user_id (e.g. Gmail), Value: list of {"ws": WebSocket, "pin": str}
active_connections: dict[str, list[dict]] = {}

# Active shared documents for 1-click downloads and Word sync
# Key: doc_id, Value: {"text": str, "stamp_paper": bool, "created_at": float}
shared_documents: dict[str, dict] = {}

DOC_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "doc_cache")
os.makedirs(DOC_CACHE_DIR, exist_ok=True)
CACHE_TTL_SECONDS = 172800  # 48 hours

def cleanup_expired_docs():
    """Removes expired documents (> 48 hours) from memory and deletes cache files from disk."""
    now = time.time()
    expired_mem = [k for k, v in list(shared_documents.items()) if now - v.get('created_at', now) > CACHE_TTL_SECONDS]
    for k in expired_mem:
        shared_documents.pop(k, None)

    try:
        if os.path.exists(DOC_CACHE_DIR):
            for fname in os.listdir(DOC_CACHE_DIR):
                if fname.endswith(".json"):
                    fpath = os.path.join(DOC_CACHE_DIR, fname)
                    try:
                        if now - os.path.getmtime(fpath) > CACHE_TTL_SECONDS:
                            os.remove(fpath)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[DocCache] Cleanup warning: {e}")

def save_doc_to_cache(doc_id: str, data: dict):
    """Saves document data in memory and to disk so restarts/reloads never lose view links."""
    shared_documents[doc_id] = data
    try:
        cache_file = os.path.join(DOC_CACHE_DIR, f"{doc_id}.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to cache document {doc_id}: {e}")

def get_doc_from_cache(doc_id: str) -> dict | None:
    """Retrieves document data from memory or disk cache, strictly enforcing 48-hour expiration."""
    clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '', doc_id.strip())
    if not clean_id:
        return None
    now = time.time()
    
    # Check in-memory first
    if clean_id in shared_documents:
        data = shared_documents[clean_id]
        if now - data.get('created_at', now) > CACHE_TTL_SECONDS:
            shared_documents.pop(clean_id, None)
            cache_file = os.path.join(DOC_CACHE_DIR, f"{clean_id}.json")
            if os.path.exists(cache_file):
                try: os.remove(cache_file)
                except Exception: pass
            return None
        return data

    # Check disk cache
    cache_file = os.path.join(DOC_CACHE_DIR, f"{clean_id}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                created_at = data.get('created_at', now)
                if now - created_at > CACHE_TTL_SECONDS:
                    os.remove(cache_file)
                    return None
                shared_documents[clean_id] = data
                return data
        except Exception:
            pass
    return None

@app.websocket("/ws/desktop/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, pin: str = ""):
    """
    Handles WebSocket connections from Desktop Agent and Word Web Add-in with PIN authentication.
    Supports multiple concurrent sessions per user with race-condition-free cleanup.
    """
    await websocket.accept()
    from urllib.parse import unquote
    clean_user_id = unquote(user_id).strip().lower()
    clean_pin = pin.strip()
    
    session_info = {
        "ws": websocket,
        "pin": clean_pin
    }
    if clean_user_id not in active_connections:
        active_connections[clean_user_id] = []
    active_connections[clean_user_id].append(session_info)
    print(f"Desktop client connected: {clean_user_id} (Active sessions: {len(active_connections[clean_user_id])})")
    
    # Send welcome status
    await websocket.send_json({
        "event": "connection_status",
        "status": "connected",
        "user_id": clean_user_id
    })
    
    try:
        while True:
            # Keep connection open, receive heartbeats
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        print(f"Desktop client disconnected normally: {clean_user_id}")
    except Exception as e:
        print(f"Desktop client connection closed ({e}): {clean_user_id}")
    finally:
        # Race-condition-free cleanup: ONLY evict this specific websocket instance
        if clean_user_id in active_connections:
            active_connections[clean_user_id] = [
                s for s in active_connections[clean_user_id] if s.get("ws") is not websocket
            ]
            if not active_connections[clean_user_id]:
                del active_connections[clean_user_id]
        print(f"Desktop client session cleaned up: {clean_user_id}")

@app.get("/api/connection-status/{user_id}")
async def get_connection_status(user_id: str):
    """
    Checks if there is an active desktop/MS Word WebSocket connection for a user.
    """
    clean_user_id = user_id.strip().lower()
    sessions = active_connections.get(clean_user_id, [])
    is_connected = len(sessions) > 0
    return {"user_id": clean_user_id, "connected": is_connected, "sessions": len(sessions)}

@app.post("/api/send-to-word")
async def send_to_word(req: SendToWordRequest):
    """
    Securely sends a formatted deed directly to the user's Desktop MS Word.
    Protected by PIN / Password verification and broadcasts to all active sessions.
    """
    clean_station_id = req.station_id.strip().lower()
    clean_pin = req.pin.strip()

    if not clean_station_id:
        return JSONResponse(status_code=400, content={
            "success": False,
            "connected": False,
            "message": "कृपया स्टेशन ID / Gmail दर्ज करें।"
        })

    sessions = active_connections.get(clean_station_id, [])
    if not sessions:
        return JSONResponse(status_code=404, content={
            "success": False,
            "connected": False,
            "message": "कंप्यूटर पर Desktop Agent कनेक्ट नहीं है! कृपया पहले कंप्यूटर पर ऐप चालू करें।"
        })

    # Verify PIN if configured on any active Desktop Agent session
    configured_pins = [s.get("pin", "") for s in sessions if s.get("pin")]
    if configured_pins and clean_pin not in configured_pins:
        return JSONResponse(status_code=401, content={
            "success": False,
            "connected": True,
            "message": "सुरक्षा पिन / पासवर्ड गलत है! कृपया सही पिन दर्ज करें।"
        })

    # Evict expired documents (> 48 hours) from memory and disk to prevent memory/disk leaks
    cleanup_expired_docs()
    now = time.time()

    # Store document for clean DOCX stream download with disk cache persistence
    doc_id = str(uuid.uuid4())[:8]
    doc_info = {
        "text": req.text,
        "stamp_paper": req.stamp_paper,
        "created_at": now
    }
    save_doc_to_cache(doc_id, doc_info)

    # Broadcast to all active sessions (both Desktop Agent and Word Add-in)
    dead_sessions = []
    sent_count = 0
    payload = {
        "event": "open_in_word",
        "doc_id": doc_id,
        "stamp_paper": req.stamp_paper,
        "text": req.text
    }
    ready_payload = {
        "event": "transcription_ready",
        "doc_id": doc_id,
        "stamp_paper": req.stamp_paper,
        "text": req.text
    }

    for s in list(sessions):
        try:
            ws = s["ws"]
            await ws.send_json(payload)
            await ws.send_json(ready_payload)
            sent_count += 1
        except Exception:
            dead_sessions.append(s)

    # Evict dead sessions if any failed
    if dead_sessions and clean_station_id in active_connections:
        active_connections[clean_station_id] = [
            s for s in active_connections[clean_station_id] if s not in dead_sessions
        ]
        if not active_connections[clean_station_id]:
            del active_connections[clean_station_id]

    if sent_count > 0:
        return {
            "success": True,
            "connected": True,
            "doc_id": doc_id,
            "message": "दस्तावेज़ सफलतापूर्वक कंप्यूटर पर भेजा गया! MS Word में नई फ़ाइल खुल रही है..."
        }
    else:
        return JSONResponse(status_code=500, content={
            "success": False,
            "connected": False,
            "message": "कंप्यूटर से कनेक्शन टूट गया था। कृपया पुनः प्रयास करें।"
        })

@app.get("/download/agent")
async def download_desktop_agent():
    """Direct 1-click download of the Desktop Background Agent for PC (.exe)."""
    if os.path.exists("SmartTyping_Agent.exe"):
        return FileResponse(
            "SmartTyping_Agent.exe",
            filename="SmartTyping_Agent.exe",
            media_type="application/vnd.microsoft.portable-executable"
        )
    # High-speed direct CDN download from official GitHub Release (100% .exe)
    release_url = "https://github.com/marketingsuccess89-dot/smartwork-tehsil/releases/download/v1.0.0/SmartTyping_Agent.exe"
    return RedirectResponse(url=release_url, status_code=302)

async def auto_sync_to_word(user_id: str | None, text: str, stamp_paper: bool = False):
    """
    Automatically broadcasts freshly generated document to connected MS Word / Desktop Agent sessions.
    """
    if not user_id:
        return
    clean_user_id = user_id.strip().lower()
    sessions = active_connections.get(clean_user_id, [])
    if not sessions:
        return

    now = time.time()
    doc_id = str(uuid.uuid4())[:8]
    doc_info = {
        "text": text,
        "stamp_paper": stamp_paper,
        "created_at": now
    }
    save_doc_to_cache(doc_id, doc_info)

    payload_open = {
        "event": "open_in_word",
        "doc_id": doc_id,
        "stamp_paper": stamp_paper,
        "text": text
    }
    payload_ready = {
        "event": "transcription_ready",
        "doc_id": doc_id,
        "stamp_paper": stamp_paper,
        "text": text
    }

    dead_sessions = []
    for s in list(sessions):
        try:
            ws = s["ws"]
            await ws.send_json(payload_open)
            await ws.send_json(payload_ready)
            print(f"[AutoSync] Document {doc_id} successfully auto-sent to MS Word for user: {clean_user_id}")
        except Exception:
            dead_sessions.append(s)

    if dead_sessions and clean_user_id in active_connections:
        active_connections[clean_user_id] = [
            s for s in active_connections[clean_user_id] if s not in dead_sessions
        ]
        if not active_connections[clean_user_id]:
            del active_connections[clean_user_id]

@app.post("/api/process-image")
async def process_image(
    files: list[UploadFile] = File(None),
    file: UploadFile = File(None),
    user_id: str = Form(None)
):
    """
    Receives single or multiple document page images and runs Gemini Vision OCR.
    Auto-syncs to MS Word if user has connected station.
    """
    target_files = []
    if files:
        target_files.extend(files)
    elif file:
        target_files.append(file)
        
    if not target_files:
        raise HTTPException(status_code=400, detail="कोई फ़ोटो प्राप्त नहीं हुई। कृपया कम से कम एक फ़ोटो चुनें।")

    bytes_list = []
    for f in target_files:
        is_img = (
            (f.content_type and f.content_type.startswith("image/"))
            or f.content_type == "application/octet-stream"
            or (f.filename and f.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.heic', '.tiff')))
        )
        if is_img:
            contents = await f.read()
            if len(contents) > 0:
                bytes_list.append(contents)

    if not bytes_list:
        raise HTTPException(status_code=400, detail="वैध इमेज फ़ाइल नहीं मिली।")

    try:
        result = await run_in_threadpool(extract_text_from_images, bytes_list)
        # Automatic MS Word sync if station is connected
        await auto_sync_to_word(user_id, result.transcribed_text, getattr(result, "stamp_paper_detected", False))
        return result
    except ValueError as ve:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process images: {str(e)}")

@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...), user_id: str = Form(None)):
    """
    Receives dictation audio and transcribes/formats it via Gemini.
    Auto-syncs to MS Word if user has connected station.
    """
    # Accept standard audio formats, generic octet-stream, or common file extensions
    is_audio = (
        (file.content_type and file.content_type.startswith("audio/")) 
        or file.content_type == "application/octet-stream"
        or (file.filename and file.filename.lower().endswith(('.wav', '.webm', '.mp3', '.m4a', '.ogg', '.aac', '.mp4')))
    )
    if not is_audio:
        raise HTTPException(status_code=400, detail="Uploaded file must be an audio file.")
        
    try:
        contents = await file.read()
        mime_type = file.content_type if (file.content_type and file.content_type.startswith("audio/")) else "audio/wav"
        result = await run_in_threadpool(transcribe_audio_dictation, contents, mime_type=mime_type)
        # Automatic MS Word sync if station is connected
        await auto_sync_to_word(user_id, result.transcribed_text, getattr(result, "stamp_paper_detected", False))
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

@app.post("/api/create-share-link")
async def create_share_link(req: DocxRequest):
    """Creates an instant 1-click download link for WhatsApp sharing."""
    # Evict expired documents (> 48 hours) from memory and disk cache
    cleanup_expired_docs()
    now = time.time()

    doc_id = str(uuid.uuid4())[:8]
    doc_info = {
        'text': req.text,
        'stamp_paper': req.stamp_paper,
        'created_at': now
    }
    save_doc_to_cache(doc_id, doc_info)
    return {"doc_id": doc_id}

@app.get("/d/{doc_id}")
async def download_shared_doc(doc_id: str):
    """Direct 1-click download of the MS Word (.docx) document."""
    doc_data = get_doc_from_cache(doc_id)
    if not doc_data:
        raise HTTPException(status_code=404, detail="दस्तावेज़ लिंक समाप्त हो चुका है।")
    file_stream = create_docx(doc_data['text'], stamp_paper=doc_data['stamp_paper'])
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=Document_{doc_id}.docx",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@app.get("/print/{doc_id}", response_class=HTMLResponse)
@app.get("/v/{doc_id}", response_class=HTMLResponse)
async def view_shared_doc(doc_id: str):
    """Mobile & Desktop A4 Document Viewer with direct Word download and Print to PDF options."""
    doc_data = get_doc_from_cache(doc_id)
    if not doc_data:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="hi">
        <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>दस्तावेज़ समाप्त</title><script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-slate-50 flex items-center justify-center min-h-screen p-4 text-center font-sans">
            <div class="bg-white p-8 rounded-2xl shadow-md max-w-md border border-slate-200">
                <div class="text-4xl mb-3">⏳</div>
                <h2 class="text-lg font-bold text-slate-800 mb-2">दस्तावेज़ लिंक समाप्त हो चुका है</h2>
                <p class="text-xs text-slate-500">सुरक्षा कारणों से शेयरिंग लिंक 48 घंटे बाद स्वतः निष्क्रिय हो जाते हैं।</p>
            </div>
        </body></html>
        """, status_code=404)

    raw_text = doc_data['text']
    stamp_paper = doc_data['stamp_paper']

    # Convert markdown to clean HTML
    import html as html_lib
    from src.doc_builder import unwrap_paragraphs

    unwrapped = unwrap_paragraphs(raw_text)

    # Smart Multi-Document vs Single Document Detection:
    # If the text has multiple H1 titles (# Title) or multiple separate recipient blocks (सेवा में),
    # it represents distinct letters/applications (e.g. 3 distinct letters). In that case, split by '---'
    # so each letter starts on its own fresh A4 sheet.
    # Otherwise, if it's a single topic/deed (e.g. Sale Deed, Partition Deed, Partnership Deed, Agreement),
    # keep it as ONE continuous document so it flows naturally without leaving huge empty gaps on pages.
    h1_count = len(re.findall(r'(?m)^#\s+[^\n]+', unwrapped))
    seva_count = len(re.findall(r'(?m)^सेवा में', unwrapped))
    raw_sections = [p.strip() for p in re.split(r'\n\s*-{3,}\s*\n', '\n' + unwrapped.strip() + '\n') if p.strip()]

    is_multi_doc = len(raw_sections) > 1 and (h1_count > 1 or seva_count > 1)

    if is_multi_doc:
        page_texts = raw_sections
    else:
        page_texts = [unwrapped.strip()]

    total_pages = len(page_texts)
    rendered_pages = []

    for page_idx, p_text in enumerate(page_texts):
        p_lines = p_text.split('\n')
        content_parts = []

        if page_idx == 0:
            content_parts.append('<div id="stamp-spacer-box" class="hidden w-full h-[2.7in] mb-4 border-2 border-dashed border-emerald-300 rounded-xl bg-emerald-50/50 flex items-center justify-center text-emerald-800 font-bold text-xs select-none">📜 स्टाम्प पेपर प्रिंट एरिया (3.0" Space Reserved)</div>')

        if total_pages > 1:
            content_parts.append(f'<div class="no-print flex items-center justify-between pb-2 mb-4 border-b border-slate-200 text-xs font-semibold text-emerald-800"><span>📄 पृष्ठ {page_idx + 1} / {total_pages}</span><span class="text-slate-400 font-normal">A4 साइज़ (1.0" मार्जिन)</span></div>')

        i = 0
        in_recipient = False
        closing_lines = []
        in_closing = False

        def flush_closing():
            nonlocal closing_lines, in_closing
            if closing_lines:
                c_html = ['<div class="doc-closing-block" style="margin-top: 14px; text-align: right; page-break-inside: avoid; break-inside: avoid;">']
                for c_idx, cl in enumerate(closing_lines):
                    c_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(cl))
                    is_title_line = (c_idx == 0 or 'हस्ताक्षर' in cl or 'आवेदक' in cl or 'प्रार्थी' in cl or 'भवदीय' in cl or 'शिष्य' in cl)
                    weight = 'font-weight: bold;' if is_title_line else ''
                    c_html.append(f'<p style="margin: 2px 0; font-size: 14px; line-height: 1.35; {weight}">{c_esc}</p>')
                c_html.append('</div>')
                content_parts.append(''.join(c_html))
                closing_lines = []
                in_closing = False

        while i < len(p_lines):
            line = p_lines[i].strip()
            if not line or re.match(r'^-{3,}$', line):
                i += 1
                continue

            # If the current line is a table, heading, or divider, flush any previous closing block immediately
            if line.startswith('|') or line.startswith('#') or re.match(r'^-{3,}$', line):
                flush_closing()

            clean_l = re.sub(r'[*#_]', '', line).strip()

            # Check if this line starts or continues the closing / signature / applicant block
            # Closing labels are short (e.g. "हस्ताक्षर:", "भवदीय,", "आवेदक / प्रार्थी:", "प्रार्थी:")
            # Never full sentences like "प्रार्थी/निगरानीकर्ता सादर निवेदन करता है कि:"
            is_sentence = bool(re.search(r'(?:कि:|है[।\.]|हूँ[।\.]|था[।\.]|करें[।\.]|गया[।\.]|जाएगा[।\.])$', clean_l))
            is_closing_start = False

            if not is_sentence and len(clean_l) < 45:
                # Always-closing keywords
                if re.match(r'^(?:द्वारा अधिवक्ता|अधिवक्ता|हस्ताक्षर|भवदीय|निवेदक|शपथी|शपथकर्ता|विनीत|आपका आज्ञाकारी|आज्ञाकारी|स्वीकृत व प्रस्तुतकर्ता|Sincerely|Regards|Yours obediently|Yours faithfully)\b', clean_l, re.IGNORECASE):
                    is_closing_start = True
                # Conditional keywords — only short closing labels
                elif re.match(r'^(?:आवेदक|प्रार्थी)\s*(?:[/:,।\-]|बनाम|$)', clean_l) and not re.search(r'(?:सादर|निवेदन|प्रार्थना|करता|करती)', clean_l):
                    is_closing_start = True

            if in_closing:
                # Close the closing block if line is too long, or a clause, or a new section
                if is_sentence or len(clean_l) > 60 or re.match(r'^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+', clean_l) or len(closing_lines) >= 6:
                    flush_closing()
                else:
                    closing_lines.append(line)
                    i += 1
                    continue

            if is_closing_start:
                in_closing = True
                closing_lines.append(line)
                i += 1
                continue

            # Markdown Table
            if line.startswith('|') and line.endswith('|'):
                tbl_lines = []
                while i < len(p_lines) and p_lines[i].strip().startswith('|') and p_lines[i].strip().endswith('|'):
                    tbl_lines.append(p_lines[i].strip())
                    i += 1

                rows = []
                for tl in tbl_lines:
                    if not re.match(r'^[\|\s\-:]+$', tl):
                        cells = [c.strip() for c in tl.split('|')[1:-1]]
                        rows.append(cells)

                if rows:
                    sig_kws = [
                        'हस्ताक्षर', 'हसताक्षर', 'हस्तक्षर', 'हस्ताक्षरी', 'साक्षी', 'साक्क्षी', 'गवाह',
                        'प्रथम पक्ष', 'परथम पक्ष', 'द्वितीय पक्ष', 'दवतीय पक्ष', 'क्रेता', 'विक्रेता',
                        'शपथकर्ता', 'आवेदक', 'प्रार्थी', 'निवेदक', 'भवदीय', 'signature', 'witness',
                        'party', 'landlord', 'tenant', 'deponent', 'applicant', 'पहचानकर्ता', 'अधिवक्ता', 'नोटरी'
                    ]
                    is_sig = any(any(kw in cell.lower() for kw in sig_kws) for r in rows for cell in r)
                    cols = max(len(r) for r in rows)
                    if cols == 2 and not is_sig and len(rows) <= 4:
                        is_sig = True
                    border_style = 'border: none;' if is_sig else 'border: 1.5px solid #06281e;'
                    t_html = [f'<table style="width: 100%; border-collapse: collapse; margin: 12px 0; {border_style} page-break-inside: avoid; break-inside: avoid;">']
                    for r_idx, r in enumerate(rows):
                        is_h = (r_idx == 0 and not is_sig)
                        bg = 'background-color: #f0fdf4; font-weight: bold;' if is_h else ''
                        t_html.append(f'<tr style="{bg}">')
                        for c_idx in range(cols):
                            c_val = r[c_idx] if c_idx < len(r) else ''
                            c_esc = html_lib.escape(c_val)
                            # Support <br> inside table cells
                            c_esc = re.sub(r'&lt;br\s*/?&gt;', '<br>', c_esc, flags=re.IGNORECASE)
                            c_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', c_esc)
                            cell_border = 'border: 1px solid #cbd5e1;' if not is_sig else ''
                            align = 'text-align: left;'
                            w_style = ''
                            if is_sig and cols == 2:
                                align = 'text-align: left;' if c_idx == 0 else 'text-align: right;'
                                w_style = 'width: 50%;'
                            elif is_sig:
                                align = 'text-align: center;'
                            elif is_h:
                                align = 'text-align: center;'
                            t_html.append(f'<td style="padding: 5px 8px; vertical-align: top; font-size: 14px; {cell_border} {align} {w_style}">{c_esc}</td>')
                        t_html.append('</tr>')
                    t_html.append('</table>')
                    content_parts.append(''.join(t_html))
                continue

            # Title (# Title)
            if line.startswith('# '):
                t_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line[2:].strip()))
                content_parts.append(f'<h1 style="text-align: center; font-size: 22px; font-weight: bold; color: #06281e; margin: 0 0 14px 0; page-break-after: avoid; break-after: avoid;">{t_esc}</h1>')
                i += 1
                continue

            # Heading (## Heading)
            if line.startswith('## '):
                h_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line[3:].strip()))
                content_parts.append(f'<h2 style="font-size: 15px; font-weight: bold; color: #0a1914; margin: 10px 0 4px 0; page-break-after: avoid; break-after: avoid;">{h_esc}</h2>')
                i += 1
                continue

            # Sub-Heading (### Sub-Heading)
            if line.startswith('### '):
                h3_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line[4:].strip()))
                content_parts.append(f'<h3 style="font-size: 14.5px; font-weight: bold; color: #06281e; margin: 8px 0 3px 0; page-break-after: avoid; break-after: avoid;">{h3_esc}</h3>')
                i += 1
                continue

            # Numbered Clause
            num_match = re.match(r'^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+(.*)$', clean_l)
            if num_match:
                num = num_match.group(1) or num_match.group(2)
                raw_content_match = re.match(r'^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+(.*)$', line)
                raw_c_text = raw_content_match.group(3) if raw_content_match else num_match.group(3)
                c_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(raw_c_text))
                content_parts.append(f'<div style="text-align: justify; margin-bottom: 6px; font-size: 14.5px; line-height: 1.5; page-break-inside: avoid; break-inside: avoid;"><strong>{num}.</strong> {c_text}</div>')
                i += 1
                continue

            # Recipient block (सेवा में, / To:)
            if clean_l.startswith('सेवा में') or clean_l.startswith('To:'):
                in_recipient = True
                p_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line))
                content_parts.append(f'<p style="margin: 0 0 4px 0; font-weight: bold; font-size: 15px; line-height: 1.4;">{p_esc}</p>')
                i += 1
                continue

            if in_recipient:
                if clean_l.startswith('विषय:') or clean_l.startswith('Subject:') or re.match(r'^(?:महोदय|महोदया|मान्यवर|Respected|Dear)\b', clean_l):
                    in_recipient = False
                else:
                    p_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line))
                    content_parts.append(f'<p style="margin: 0 0 2px 0; padding-left: 24px; font-size: 14.5px; line-height: 1.35;">{p_esc}</p>')
                    i += 1
                    continue

            # Subject line (विषय:)
            if clean_l.startswith('विषय:') or clean_l.startswith('Subject:'):
                p_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line))
                content_parts.append(f'<p style="margin: 8px 0 6px 0; font-weight: bold; font-size: 14.5px; line-height: 1.4;">{p_esc}</p>')
                i += 1
                continue

            # Salutation (महोदय, / मान्यवर,)
            if re.match(r'^(?:महोदय|महोदया|मान्यवर|श्रीमान|Respected|Dear)\b', clean_l):
                p_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line))
                content_parts.append(f'<p style="margin: 8px 0 4px 0; font-weight: 600; font-size: 14.5px; line-height: 1.4;">{p_esc}</p>')
                i += 1
                continue

            # Date / Place line
            if re.match(r'^(?:दिनांक|स्थान|Date:|Place:)', clean_l, re.IGNORECASE):
                p_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line))
                content_parts.append(f'<p style="margin: 8px 0 3px 0; font-size: 14px; line-height: 1.4;">{p_esc}</p>')
                i += 1
                continue

            # Standard Paragraph
            p_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line))
            content_parts.append(f'<p style="text-align: justify; margin-bottom: 6px; font-size: 14.5px; line-height: 1.5; page-break-inside: avoid; break-inside: avoid;">{p_esc}</p>')
            i += 1

        # Flush any remaining closing lines at the end of the page
        flush_closing()

        page_body = '\n'.join(content_parts)
        rendered_pages.append(f'''<div class="doc-page-wrapper">
<table class="print-table">
  <thead><tr><td class="print-margin-cell"></td></tr></thead>
  <tfoot><tr><td class="print-margin-cell"></td></tr></tfoot>
  <tbody><tr><td class="page-content-cell">{page_body}</td></tr></tbody>
</table>
</div>''')

    all_pages_html = '\n'.join(rendered_pages)

    page_html = f"""<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>तहसील विलेख दस्तावेज़</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            font-family: 'Noto Sans Devanagari', 'Nirmala UI', system-ui, sans-serif;
            background: #f1f5f9;
            color: #0f172a;
        }}
        /* Screen View: Clean A4 Paper Simulation */
        .doc-page-wrapper {{
            background: #ffffff;
            width: 100%;
            max-width: 760px;
            min-height: 1050px;
            margin: 20px auto;
            padding: 44px 50px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 14.5px;
            line-height: 1.5;
        }}
        /* On screen: print-table acts as transparent block */
        .print-table {{
            display: block;
            width: 100%;
            border-collapse: collapse;
            border: none;
        }}
        .print-table > thead, .print-table > tfoot {{
            display: none;
        }}
        .print-table > tbody, .print-table > tbody > tr, .print-table > tbody > tr > td {{
            display: block;
            width: 100%;
            padding: 0;
            border: none;
        }}

        @media (max-width: 640px) {{
            .doc-page-wrapper {{
                margin: 10px auto;
                padding: 24px 20px;
                font-size: 13.5px;
            }}
        }}

        /* Print Media Styles */
        @media print {{
            html, body {{
                background: #ffffff !important;
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
            }}
            .no-print {{
                display: none !important;
            }}
            /* Margin 0 suppresses browser auto header (URL, localhost) and footer (date, time) */
            @page {{
                size: A4 portrait;
                margin: 0 !important;
            }}
            .doc-page-wrapper {{
                box-shadow: none !important;
                border: none !important;
                border-radius: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                max-width: 100% !important;
                width: 100% !important;
                min-height: 0 !important;
                page-break-after: always !important;
                break-after: page !important;
            }}
            .doc-page-wrapper:last-child {{
                page-break-after: avoid !important;
                break-after: avoid !important;
            }}
            /* Print Table with thead/tfoot to provide consistent page margins across page breaks */
            .print-table {{
                display: table !important;
                width: 100% !important;
                border-collapse: collapse !important;
                border: none !important;
            }}
            .print-table > thead {{
                display: table-header-group !important;
            }}
            .print-table > tfoot {{
                display: table-footer-group !important;
            }}
            .print-table > tbody {{
                display: table-row-group !important;
            }}
            .print-table > tbody > tr {{
                display: table-row !important;
            }}
            .print-table > tbody > tr > td.page-content-cell {{
                display: table-cell !important;
                padding: 0 25.4mm !important; /* Authentic 1.0 inch left/right margin */
                vertical-align: top !important;
                border: none !important;
            }}
            .print-margin-cell {{
                height: 20mm !important; /* Top and bottom margin repeated on every printed sheet */
                padding: 0 !important;
                border: none !important;
                line-height: 0 !important;
                font-size: 0 !important;
            }}
            .page-content-cell h1 {{
                font-size: 16pt !important;
                margin: 0 0 10pt 0 !important;
                line-height: 1.25 !important;
            }}
            .page-content-cell h2 {{
                font-size: 13pt !important;
                margin: 8pt 0 4pt 0 !important;
                line-height: 1.25 !important;
            }}
            .page-content-cell p {{
                font-size: 11.5pt !important;
                line-height: 1.35 !important;
                margin-bottom: 4pt !important;
            }}
            .page-content-cell .doc-closing-block {{
                margin-top: 10pt !important;
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            .page-content-cell .doc-closing-block p {{
                margin-bottom: 1.5pt !important;
                line-height: 1.25 !important;
                font-size: 11.5pt !important;
            }}
        }}
        </style>
    <script>
        // Completely clears page title during print so browser NEVER prints "तहसील विलेख दस्तावेज़" or URL
        window.addEventListener('beforeprint', function() {{
            document.title = '';
        }});
        window.addEventListener('afterprint', function() {{
            document.title = 'तहसील विलेख दस्तावेज़';
        }});
        function toggleStampSpace() {{
            const box = document.getElementById('stamp-spacer-box');
            const txt = document.getElementById('stamp-toggle-text');
            if (box) {{
                if (box.classList.contains('hidden')) {{
                    box.classList.remove('hidden');
                    txt.innerText = 'स्टाम्प स्पेस हटाएं';
                }} else {{
                    box.classList.add('hidden');
                    txt.innerText = 'स्टाम्प स्पेस जोड़ें';
                }}
            }}
        }}
    </script>
</head>
<body class="min-h-screen flex flex-col items-center">
    <!-- Top Floating Sticky Action Bar -->
    <header class="no-print sticky top-0 z-30 w-full bg-[#06281e] text-white py-3 px-4 shadow-md flex flex-wrap justify-between items-center gap-3">
        <div class="flex items-center space-x-2 font-bold text-xs sm:text-sm">
            <span class="bg-emerald-600 p-1.5 rounded-lg"><i class="fa-solid fa-file-contract"></i></span>
            <span>तहसील विलेख दस्तावेज़</span>
        </div>
        <div class="flex items-center space-x-2">
            <button onclick="toggleStampSpace()" id="stamp-toggle-btn" class="bg-emerald-800 hover:bg-emerald-700 text-emerald-200 font-semibold py-2 px-3 rounded-xl text-xs flex items-center space-x-1.5 transition shadow-sm cursor-pointer">
                <i class="fa-solid fa-stamp"></i>
                <span id="stamp-toggle-text">स्टाम्प स्पेस जोड़ें</span>
            </button>
            <a href="/d/{doc_id}" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2 px-3 rounded-xl text-xs flex items-center space-x-1.5 transition shadow-sm">
                <i class="fa-solid fa-file-word"></i>
                <span>Word (.DOCX) डाउनलोड</span>
            </a>
            <button onclick="window.print()" class="bg-white hover:bg-slate-100 text-slate-900 font-bold py-2 px-3 rounded-xl text-xs flex items-center space-x-1.5 transition shadow-sm cursor-pointer">
                <i class="fa-solid fa-print text-emerald-700"></i>
                <span>A4 प्रिंट / PDF सेव</span>
            </button>
        </div>
    </header>

    <!-- A4 Paper Document Sheets -->
    <main class="w-full px-2 sm:px-4 flex flex-col items-center justify-center pb-12 space-y-6">
        {all_pages_html}
    </main>
</body>
</html>
"""
    return HTMLResponse(page_html)

# Model status and failover monitor
@app.get("/api/model-status")
async def model_status():
    """Returns active Gemini model, primary/secondary ranking, and failover state."""
    return get_model_status()

# Health check endpoint for Render keep-alive bot and uptime monitoring
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "smartwork-tehsil",
        "timestamp": time.time(),
        "ai_model": get_model_status()
    }

# Serve Static Files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    should_reload = os.getenv("UVICORN_RELOAD", "false").lower() in ("true", "1", "yes")
    if should_reload:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["src"])
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
