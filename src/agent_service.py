import os
import json
import io
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Pydantic schema for structured JSON output
class TranscriptionResult(BaseModel):
    transcribed_text: str = Field(description="The full verbatim transcription and formatted document text (with paragraphs, headings, lists, tables)")

def compress_image(image_bytes: bytes, max_size: int = 1280, quality: int = 75) -> bytes:
    """
    Resizes and compresses the uploaded image to reduce payload size
    and optimize Gemini API upload speeds.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Auto-rotate image based on EXIF orientation data (fixes sideways mobile uploads)
        img = ImageOps.exif_transpose(img)
        
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGB')
            
        width, height = img.size
        if max(width, height) > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
        out_io = io.BytesIO()
        img.save(out_io, format="JPEG", quality=quality, optimize=True)
        return out_io.getvalue()
    except Exception as e:
        print(f"Image preprocessing/compression failed: {e}")
        return image_bytes

_cached_client = None

def get_genai_client():
    global _cached_client
    if _cached_client is None:
        load_dotenv(override=True)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment. Please add it to your .env file.")
        _cached_client = genai.Client(api_key=api_key)
    return _cached_client

def extract_text_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> TranscriptionResult:
    """
    Sends document image to Gemini Vision to perform verbatim OCR with legal standardization rules.
    Optimized with google.genai and zero thinking budget for sub-8-second turnaround.
    """
    # Fast compress and resize the image to optimize network upload speeds
    processed_image_bytes = compress_image(image_bytes)
    target_mime_type = "image/jpeg"
    
    client = get_genai_client()
    
    prompt = """
    You are an expert universal OCR and legal/official document typing assistant for Indian Tehsil, Court, School, and Government offices.
    Analyze the provided document image and transcribe it with high intelligence into professional, print-ready Markdown format.

    UNIVERSAL PRINCIPLES:
    1. **100% Strict Verbatim Words (शब्द बिल्कुल नहीं बदलेंगे, न जोड़ेंगे, न घटाएंगे)**:
       - Transcribe EVERY single word written in the image faithfully and accurately.
       - DO NOT add any extra unwritten words, declarations, boilerplate, or summaries.
       - DO NOT remove or skip any written words.
       - If any word or line is crossed out (काटा हुआ है), ignore only the crossed-out text.

    2. **Intelligent Document Format Recognition (दस्तावेज़ के प्रकार अनुसार सही फ़ॉर्मैटिंग)**:
       - Understand the exact nature of the document from the image:
         * Formal Application / Letter (e.g. School leave letter, Police complaint, Municipal application):
           Format recipient ('सेवा में, ...'), Subject ('विषय: ...'), Salutation ('महोदय / महोदया, ...'), Body paragraphs, and closing ('भवदीय / प्रार्थी / आपका आज्ञाकारी') in their natural, standard Indian official letter layout.
         * Legal Agreement / Deed (विलेख / अनुबंध):
           Format the Main Title at the top as '# [Title]' followed by a blank line. Write party descriptions, preambles, and numbered clauses ('1.', '2.') as continuous full-width paragraphs.
         * Affidavit (शपथ पत्र):
           Format Title '# शपथ पत्र', Deponent details, sworn points, and bottom Verification ('तस्दीक / सत्यापन').
         * For Any Other Document / Notice / Receipt:
           Apply clean, professional typography and layout appropriate for that specific document.

    3. **Continuous Full-Width Paragraphs (आधी-अधूरी लाइन न तोड़ें, पूरा पैराग्राफ लिखें)**:
       - DO NOT break sentences into short half-lines just because a notebook line ended physically.
       - Write each paragraph or numbered clause as ONE continuous flowing block so that in MS Word and A4 paper it fills the entire width naturally.

    4. **Smart Signatures & Layout (हस्ताक्षर स्पेसिंग)**:
       - If there are TWO parties/signatures side-by-side (left and right), format them as a clean 2-column Markdown table:
         | [Left Party / Signature] | [Right Party / Signature] |
         | :--- | ---: |
         | [Details] | [Details] |
       - If there is only ONE person signing (e.g. Applicant / Deponent in an application or affidavit), DO NOT create a 2-column table. Format the single signature block cleanly as written in the document.

    Ensure your response strictly matches the required JSON schema.
    """
    
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=[
            types.Part.from_bytes(data=processed_image_bytes, mime_type=target_mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json",
            response_schema=TranscriptionResult
        )
    )
    
    data = json.loads(response.text)
    return TranscriptionResult(**data)

def transcribe_audio_dictation(audio_bytes: bytes, mime_type: str = "audio/wav") -> TranscriptionResult:
    """
    Sends speech dictation audio to Gemini to transcribe and format into a structured legal document.
    """
    client = get_genai_client()
    
    prompt = """
    You are an expert audio transcription assistant.
    Transcribe the spoken audio dictation EXACTLY as spoken.

    STRICT RULES:
    1. **Faithful Transcription (जैसा बोला गया है, हूबहू वैसा ही लिखें)**:
       - Transcribe ONLY what the speaker dictated.
       - DO NOT add or invent any unmentioned legal boilerplate, preambles, artificial declarations, or fabricated witness sections.
       - If the speaker made a slip of tongue or stuttered and corrected themselves (e.g. "नाम अमित... नहीं नहीं, सुमित लिखो"), write only the intended corrected text ("सुमित").

    2. **Clean Formatting & Spacing (स्पेसिंग का ध्यान रखें)**:
       - Organize the dictated text with clean paragraphs, clear line breaks, and proper spacing.
       - Use numbered points only if the speaker dictated numbers.
       - If the speaker dictates signatures or dates at the end, arrange them with clean spacing so they do not collide.

    Ensure your response strictly matches the required JSON schema.
    """
    
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json",
            response_schema=TranscriptionResult
        )
    )
    
    data = json.loads(response.text)
    return TranscriptionResult(**data)
