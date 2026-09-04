import os
import re
import json
import uuid
import time
from dotenv import load_dotenv

# Force load environment variables from .env file overriding system vars
load_dotenv(override=True)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from src.agent_service import extract_text_from_image, extract_text_from_images, transcribe_audio_dictation
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

class SendToWordRequest(BaseModel):
    text: str
    stamp_paper: bool = False
    station_id: str
    pin: str = ""

# Active WebSocket Sessions for Desktop/MS Word Sync
# Key: user_id (e.g. Gmail), Value: {"ws": WebSocket, "pin": str}
active_connections: dict[str, dict] = {}

@app.websocket("/ws/desktop/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, pin: str = ""):
    """
    Handles WebSocket connections from Desktop Agent with optional PIN authentication.
    """
    await websocket.accept()
    from urllib.parse import unquote
    clean_user_id = unquote(user_id).strip().lower()
    clean_pin = pin.strip()
    
    active_connections[clean_user_id] = {
        "ws": websocket,
        "pin": clean_pin
    }
    print(f"Desktop client connected: {clean_user_id} (PIN configured: {bool(clean_pin)})")
    
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
        print(f"Desktop client disconnected: {clean_user_id}")
        if clean_user_id in active_connections:
            del active_connections[clean_user_id]

@app.get("/api/connection-status/{user_id}")
async def get_connection_status(user_id: str):
    """
    Checks if there is an active desktop/MS Word WebSocket connection for a user.
    """
    clean_user_id = user_id.strip().lower()
    is_connected = clean_user_id in active_connections
    return {"user_id": clean_user_id, "connected": is_connected}

@app.post("/api/send-to-word")
async def send_to_word(req: SendToWordRequest):
    """
    Securely sends a formatted deed directly to the user's Desktop MS Word.
    Protected by PIN / Password verification.
    """
    clean_station_id = req.station_id.strip().lower()
    clean_pin = req.pin.strip()

    if not clean_station_id:
        return JSONResponse(status_code=400, content={
            "success": False,
            "connected": False,
            "message": "कृपया स्टेशन ID / Gmail दर्ज करें।"
        })

    if clean_station_id not in active_connections:
        return JSONResponse(status_code=404, content={
            "success": False,
            "connected": False,
            "message": "कंप्यूटर पर Desktop Agent कनेक्ट नहीं है! कृपया पहले कंप्यूटर पर ऐप चालू करें।"
        })

    conn_info = active_connections[clean_station_id]
    stored_pin = conn_info.get("pin", "")

    # Verify PIN if configured on Desktop Agent
    if stored_pin and clean_pin != stored_pin:
        return JSONResponse(status_code=401, content={
            "success": False,
            "connected": True,
            "message": "सुरक्षा पिन / पासवर्ड गलत है! कृपया सही पिन दर्ज करें।"
        })

    # Evict expired documents (> 48 hours) to prevent memory leak
    now = time.time()
    expired = [k for k, v in shared_documents.items() if now - v.get('created_at', now) > 172800]
    for k in expired:
        shared_documents.pop(k, None)

    # Store document for clean DOCX stream download
    doc_id = str(uuid.uuid4())[:8]
    shared_documents[doc_id] = {
        "text": req.text,
        "stamp_paper": req.stamp_paper,
        "created_at": now
    }

    ws = conn_info["ws"]
    try:
        await ws.send_json({
            "event": "open_in_word",
            "doc_id": doc_id,
            "stamp_paper": req.stamp_paper
        })
        return {
            "success": True,
            "connected": True,
            "doc_id": doc_id,
            "message": "दस्तावेज़ सफलतापूर्वक कंप्यूटर पर भेजा गया! MS Word में नई फ़ाइल खुल रही है..."
        }
    except Exception as ws_err:
        return JSONResponse(status_code=500, content={
            "success": False,
            "connected": False,
            "message": f"डेटा भेजने में त्रुटि: {str(ws_err)}"
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

@app.post("/api/process-image")
async def process_image(
    files: list[UploadFile] = File(None),
    file: UploadFile = File(None),
    user_id: str = Form(None)
):
    """
    Receives single or multiple document page images and runs Gemini Vision OCR.
    """
    target_files = []
    if files:
        target_files.extend(files)
    if file and file not in target_files:
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
        result = extract_text_from_images(bytes_list)
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

@app.get("/v/{doc_id}", response_class=HTMLResponse)
async def view_shared_doc(doc_id: str):
    """Mobile & Desktop A4 Document Viewer with direct Word download and Print to PDF options."""
    if doc_id not in shared_documents:
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

    doc_data = shared_documents[doc_id]
    raw_text = doc_data['text']
    stamp_paper = doc_data['stamp_paper']

    # Convert markdown to clean HTML
    import html as html_lib
    from src.doc_builder import unwrap_paragraphs

    unwrapped = unwrap_paragraphs(raw_text)
    lines = unwrapped.split('\n')

    content_parts = []
    if stamp_paper:
        content_parts.append('<div class="stamp-spacer" style="height: 2.7in; width: 100%;"></div>')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if re.match(r'^-{3,}$', line):
            content_parts.append('<div class="print-page-break" style="page-break-after: always; break-after: page;"></div>')
            i += 1
            continue

        # Markdown Table
        if line.startswith('|') and line.endswith('|'):
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                tbl_lines.append(lines[i].strip())
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
                    'party', 'landlord', 'tenant', 'deponent', 'applicant'
                ]
                is_sig = any(any(kw in cell.lower() for kw in sig_kws) for r in rows for cell in r)
                cols = max(len(r) for r in rows)
                if cols == 2 and not is_sig and len(rows) <= 4:
                    is_sig = True
                border_style = 'border: none;' if is_sig else 'border: 1.5px solid #06281e;'
                t_html = [f'<table style="width: 100%; border-collapse: collapse; margin: 16px 0; {border_style} page-break-inside: avoid; break-inside: avoid;">']
                for r_idx, r in enumerate(rows):
                    is_h = (r_idx == 0 and not is_sig)
                    bg = 'background-color: #f0fdf4; font-weight: bold;' if is_h else ''
                    t_html.append(f'<tr style="{bg}">')
                    for c_idx in range(cols):
                        c_val = r[c_idx] if c_idx < len(r) else ''
                        c_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(c_val))
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
                        t_html.append(f'<td style="padding: 6px 8px; vertical-align: top; font-size: 14.5px; {cell_border} {align} {w_style}">{c_esc}</td>')
                    t_html.append('</tr>')
                t_html.append('</table>')
                content_parts.append(''.join(t_html))
            continue

        # Title (# Title)
        if line.startswith('# '):
            t_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line[2:].strip()))
            content_parts.append(f'<h1 style="text-align: center; font-size: 24px; font-weight: bold; color: #06281e; margin: 0 0 18px 0; page-break-after: avoid; break-after: avoid;">{t_esc}</h1>')
            i += 1
            continue

        # Heading (## Heading)
        if line.startswith('## '):
            h_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line[3:].strip()))
            content_parts.append(f'<h2 style="font-size: 16px; font-weight: bold; color: #0a1914; margin: 14px 0 6px 0; page-break-after: avoid; break-after: avoid;">{h_esc}</h2>')
            i += 1
            continue

        # Numbered Clause
        num_match = re.match(r'^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+(.*)$', line)
        if num_match:
            num = num_match.group(1) or num_match.group(2)
            c_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(num_match.group(3)))
            content_parts.append(f'<div style="text-align: justify; margin-bottom: 8px; font-size: 15px; line-height: 1.6; page-break-inside: avoid; break-inside: avoid;"><strong>{num}.</strong> {c_text}</div>')
            i += 1
            continue

        # Paragraph
        p_esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_lib.escape(line))
        content_parts.append(f'<p style="text-align: justify; margin-bottom: 8px; font-size: 15px; line-height: 1.6; page-break-inside: avoid; break-inside: avoid;">{p_esc}</p>')
        i += 1

    body_html = '\n'.join(content_parts)

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
        .a4-viewer-paper {{
            background: #ffffff;
            width: 100%;
            max-width: 760px;
            min-height: 1050px;
            margin: 20px auto;
            padding: 48px 52px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 15px; /* 12pt equivalent */
            line-height: 1.65;
        }}
        @media (max-width: 640px) {{
            .a4-viewer-paper {{
                margin: 10px auto;
                padding: 24px 20px;
                font-size: 13.5px;
            }}
        }}
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
            .a4-viewer-paper {{
                box-shadow: none !important;
                border: none !important;
                margin: 0 !important;
                padding: 25.4mm 25.4mm 25.4mm 25.4mm !important; /* Authentic 1.0-inch Normal margins */
                max-width: 100% !important;
                width: 100% !important;
                font-size: 12pt !important;
                line-height: 1.6 !important;
                box-sizing: border-box !important;
            }}
            @page {{
                size: A4 portrait;
                margin: 0 !important; /* Removes browser default headers (date/time/title) and footer (URL) */
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

    <!-- A4 Paper Document -->
    <main class="w-full px-2 sm:px-4 flex justify-center pb-12">
        <article class="a4-viewer-paper">
            {body_html}
        </article>
    </main>
</body>
</html>
"""
    return HTMLResponse(page_html)

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
