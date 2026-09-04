"""
Smart Typing Desktop Background Agent
Auto-opens documents generated from mobile into MS Word (New Document Window)
Features:
- PIN / Password protected authentication
- Real-time WebSocket connection to server
- Opens deeds in brand-new separate Word document windows (never mixes with existing work)
- Auto-launches MS Word if not already open
"""

import sys
import os
import json
import time
import tempfile
import asyncio
import urllib.request
import urllib.parse

# Windows specific imports
try:
    import win32com.client
    import winsound
except ImportError:
    win32com = None
    winsound = None

CONFIG_FILE = "station_config.json"
DEFAULT_SERVER = "thesmartwork.onrender.com"
DEFAULT_WS_SCHEME = "wss"
DEFAULT_HTTP_SCHEME = "https"

def load_config():
    """Loads saved station ID and PIN."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config):
    """Saves station ID and PIN locally."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def prompt_user_credentials():
    """Prompts operator for Station ID and PIN via GUI or Console."""
    cfg = load_config()
    existing_id = cfg.get("station_id", "")
    existing_pin = cfg.get("pin", "")
    existing_host = cfg.get("server_host", DEFAULT_SERVER)

    # Try Tkinter GUI first for native Windows look
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.title("Smart Typing - PC Agent Setup")
        root.geometry("400x330")
        root.resizable(False, False)
        root.configure(bg="#f8fafc")

        # Center window
        root.eval('tk::PlaceWindow . center')

        # Header
        hdr = tk.Label(
            root, 
            text="🖥️ Smart Typing PC Agent", 
            font=("Segoe UI", 13, "bold"), 
            bg="#f8fafc", 
            fg="#064e3b"
        )
        hdr.pack(pady=(18, 4))

        sub = tk.Label(
            root, 
            text="मोबाइल से MS Word में ऑटोमैटिक ट्रांसफर के लिए लॉगिन करें", 
            font=("Segoe UI", 9), 
            bg="#f8fafc", 
            fg="#64748b"
        )
        sub.pack(pady=(0, 14))

        frame = tk.Frame(root, bg="#f8fafc")
        frame.pack(padx=28, fill="x")

        # Gmail / Station ID
        tk.Label(frame, text="Gmail / स्टेशन कोड:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b", anchor="w").pack(fill="x")
        entry_id = tk.Entry(frame, font=("Segoe UI", 10), bd=1, relief="solid")
        entry_id.pack(fill="x", pady=(2, 10), ipady=3)
        if existing_id:
            entry_id.insert(0, existing_id)

        # PIN / Password
        tk.Label(frame, text="सुरक्षा पिन / पासवर्ड (PIN):", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b", anchor="w").pack(fill="x")
        entry_pin = tk.Entry(frame, font=("Segoe UI", 10), bd=1, relief="solid", show="•")
        entry_pin.pack(fill="x", pady=(2, 16), ipady=3)
        if existing_pin:
            entry_pin.insert(0, existing_pin)

        res_data = {"submitted": False}

        def on_save():
            s_id = entry_id.get().strip().lower()
            s_pin = entry_pin.get().strip()
            if not s_id:
                messagebox.showerror("त्रुटि", "कृपया अपनी Gmail या स्टेशन कोड दर्ज करें।")
                return
            if not s_pin:
                messagebox.showerror("त्रुटि", "कृपया सुरक्षा पिन / पासवर्ड दर्ज करें।")
                return
            cfg["station_id"] = s_id
            cfg["pin"] = s_pin
            cfg["server_host"] = existing_host
            save_config(cfg)
            res_data["submitted"] = True
            root.destroy()

        btn_save = tk.Button(
            frame, 
            text="✅ कनेक्ट करें और चालू रखें", 
            font=("Segoe UI", 10, "bold"), 
            bg="#059669", 
            fg="white", 
            activebackground="#047857", 
            activeforeground="white", 
            relief="flat", 
            cursor="hand2", 
            command=on_save
        )
        btn_save.pack(fill="x", ipady=5)

        root.mainloop()

        if res_data["submitted"]:
            return load_config()

    except Exception as e:
        print(f"GUI not available ({e}), using console input...")

    # Fallback to Console
    print("=" * 50)
    print("  Smart Typing PC Agent Setup")
    print("=" * 50)
    s_id = input(f"Gmail / स्टेशन कोड [{existing_id}]: ").strip() or existing_id
    s_pin = input(f"सुरक्षा पिन / पासवर्ड [{existing_pin}]: ").strip() or existing_pin
    cfg["station_id"] = s_id
    cfg["pin"] = s_pin
    cfg["server_host"] = existing_host
    save_config(cfg)
    return cfg

def open_docx_in_word(file_path):
    """
    Opens the downloaded DOCX in MS Word as a new separate window.
    Guarantees existing open documents are untouched.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        print(f"[ERROR] फ़ाइल नहीं मिली: {abs_path}")
        return False

    try:
        if win32com:
            try:
                word = win32com.client.GetObject(Class="Word.Application")
            except Exception:
                word = win32com.client.Dispatch("Word.Application")
            
            word.Visible = True
            doc = word.Documents.Open(abs_path)
            word.Activate()
            doc.Activate()
            print(f"[SUCCESS] MS Word में नया दस्तावेज़ सफलतापूर्वक खुला: {abs_path}")
            if winsound:
                try:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception:
                    pass
            return True
        else:
            # Fallback for systems without win32com
            os.startfile(abs_path)
            print(f"[SUCCESS] OS डिफ़ॉल्ट प्रोग्राम में खुला: {abs_path}")
            return True
    except Exception as e:
        print(f"[ERROR] MS Word खोलने में विफल: {e}")
        try:
            os.startfile(abs_path)
        except Exception:
            pass
        return False

async def agent_main():
    cfg = load_config()
    if not cfg.get("station_id") or not cfg.get("pin"):
        cfg = prompt_user_credentials()

    station_id = cfg.get("station_id", "").strip().lower()
    pin = cfg.get("pin", "").strip()
    server_host = cfg.get("server_host", DEFAULT_SERVER).strip()

    if not station_id or not pin:
        print("[ERROR] स्टेशन ID या पिन उपलब्ध नहीं है। ऐप बंद हो रहा है।")
        return

    # Check for websockets library, install or fail gracefully
    try:
        import websockets
    except ImportError:
        print("[INFO] 'websockets' लाइब्रेरी इंस्टॉल की जा रही है...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        import websockets

    # WebSocket URL with PIN authentication query param
    encoded_id = urllib.parse.quote(station_id)
    encoded_pin = urllib.parse.quote(pin)

    # Determine protocols
    ws_scheme = "ws" if "localhost" in server_host or "127.0.0.1" in server_host else "wss"
    http_scheme = "http" if "localhost" in server_host or "127.0.0.1" in server_host else "https"

    ws_url = f"{ws_scheme}://{server_host}/ws/desktop/{encoded_id}?pin={encoded_pin}"

    print("=" * 60)
    print(f"  Smart Typing Desktop Agent सक्रिय है")
    print(f"  स्टेशन ID : {station_id}")
    print(f"  सर्वर     : {server_host}")
    print(f"  स्थिति    : मोबाइल से कमांड का इंतज़ार कर रहा है...")
    print("=" * 60)

    retry_delay = 3
    while True:
        try:
            print(f"[CONNECTING] सर्वर से जुड़ रहा है: {ws_url} ...")
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                print(f"[CONNECTED] 🟢 सर्वर से सफलतापूर्वक जुड़ा! (ID: {station_id})")
                print("  -> मोबाइल पर 'MS Word में भेजें' दबाते ही यहाँ Word फ़ाइल खुल जाएगी।")
                retry_delay = 3

                while True:
                    raw_msg = await ws.recv()
                    if raw_msg == "pong":
                        continue

                    try:
                        data = json.loads(raw_msg)
                        event = data.get("event")

                        if event == "connection_status":
                            print(f"[INFO] सर्वर स्थिति: {data.get('status')} ({data.get('user_id')})")

                        elif event == "open_in_word":
                            doc_id = data.get("doc_id")
                            print(f"\n[EVENT] 📄 नया दस्तावेज़ प्राप्त हुआ! Doc ID: {doc_id}")

                            # Download the pristine DOCX file from server
                            download_url = f"{http_scheme}://{server_host}/d/{doc_id}"
                            temp_dir = tempfile.gettempdir()
                            temp_file_path = os.path.join(temp_dir, f"Smart_Typing_{doc_id}.docx")

                            print(f"[DOWNLOAD] डाउनलोड हो रहा है: {download_url} ...")
                            req = urllib.request.Request(
                                download_url, 
                                headers={"User-Agent": "SmartTyping-DesktopAgent/1.0"}
                            )
                            with urllib.request.urlopen(req) as resp, open(temp_file_path, "wb") as out_fp:
                                out_fp.write(resp.read())

                            print(f"[SAVED] फ़ाइल सुरक्षित: {temp_file_path}")

                            # Open directly in MS Word
                            open_docx_in_word(temp_file_path)

                    except Exception as parse_err:
                        print(f"[WARN] संदेश पार्स करने में त्रुटि: {parse_err}")

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as conn_err:
            print(f"[DISCONNECTED] कनेक्शन टूटा ({conn_err}). {retry_delay}s में पुनः प्रयास...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 30)
        except Exception as e:
            print(f"[ERROR] अप्रत्याशित त्रुटि: {e}. 5s में पुनः प्रयास...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(agent_main())
    except KeyboardInterrupt:
        print("\n[INFO] एजेंट बंद किया गया।")
