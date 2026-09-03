import os
import json
import io
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

from PIL import Image, ImageOps, ImageEnhance

# Load environment variables
load_dotenv(override=True)

# Pydantic schema for structured JSON output
class TranscriptionResult(BaseModel):
    transcribed_text: str = Field(description="The full verbatim transcription and formatted document text (with paragraphs, headings, lists, tables)")
    stamp_paper_detected: bool = Field(default=False, description="Set to true if the document was photographed on an Indian government Stamp Paper")

def compress_image(image_bytes: bytes, max_size: int = 1400, quality: int = 80) -> bytes:
    """
    Resizes, contrast-enhances, and sharpens the uploaded image to maximize
    OCR legibility for faint ballpoint pen, low-light shadows, and handwritten strokes.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Auto-rotate image based on EXIF orientation data (fixes sideways mobile uploads)
        img = ImageOps.exif_transpose(img)
        
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGB')

        # Intelligent contrast & sharpness boost for faint handwriting and low-contrast lighting
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.15)
        sharpener = ImageEnhance.Sharpness(img)
        img = sharpener.enhance(1.25)
            
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
    # Fast compress, contrast-enhance, and resize the image to optimize OCR and upload speed
    processed_image_bytes = compress_image(image_bytes)
    target_mime_type = "image/jpeg"
    
    client = get_genai_client()
    
    prompt = """
    You are an expert universal OCR and legal/official document typing assistant for Indian Tehsil, Court, School, and Government offices.
    Analyze the provided document image and transcribe it with high intelligence into professional, print-ready Markdown format.

    1. **100% Strict Verbatim Words & Proper Noun Preservation (नाम व वाक्य की मूल भावना अक्षुण्ण रखें)**:
       - **Personal Names, Father's Names, Castes, Villages, Towns, IDs (नामों की स्पेलिंग कभी न बदलें)**:
         * NEVER auto-correct or alter the spelling of ANY person's name, surname, father's name, or village name!
         * Even if a name looks dialectical or unconventional (e.g. 'रामेशवर परसाद', 'कलूराम', 'बचनू लाल', 'सुनील', 'झिनझिनिया'), transcribe the EXACT spelling as written. Changing a person's name invalidates their legal registration with Government IDs.
       - **Preserve Sentence Meaning Exactly (वाक्य का अर्थ चाहे अजीब हो, वैसा ही लिखें)**:
         * NEVER rephrase, rewrite, paraphrase, summarize, or alter strange, illogical, or informal sentences.
         * Whatever conditions or statements are written, transcribe them EXACTLY as written without trying to "make more sense" of them.
       - **Common Words (सामान्य शब्दावली)**:
         * Standard generic words (e.g. 'किरायानामा', 'इकरारनामा', 'प्रतिदिन', 'हस्ताक्षर', 'सहमति') should be formatted cleanly with standard devanagari orthography if there was a minor handwriting slip.
       - **Strikethrough (काटा हुआ)**:
         * If any word is crossed out with a pen line, ignore the crossed-out text and transcribe the intended correction.

    2. **Pre-Printed Government Stamp Paper Rule (स्टाम्प पेपर के सरकारी हेडर को कभी न लिखें)**:
       - If the document is written on an official Indian Stamp Paper (₹10, ₹50, ₹100, ₹500 Non-Judicial paper with State/Government emblem):
         * Set `stamp_paper_detected = True`.
         * DO NOT transcribe the pre-printed government stamp header (e.g. "भारत सरकार", "GOVERNMENT OF INDIA", National Emblem / Lion Capital, "NON JUDICIAL / गैर न्यायिक", "₹100", Serial No., Vendor Name/Seal/Barcode, or "Notary Stamp below").
         * Physical stamp papers already contain these factory-printed. Typists insert the physical stamp paper into the printer, and typing MUST start strictly from the actual legal content (e.g. '# शपथ पत्र (Affidavit)', or Court/Authority heading 'समक्ष: श्रीमान...').
       - If it is on normal notebook, register, or plain blank paper, set `stamp_paper_detected = False`.

    3. **Intelligent Document Format Recognition (दस्तावेज़ के प्रकार अनुसार सही फ़ॉर्मैटिंग)**:
       - Understand the exact nature of the document from the image:
         * Formal Application / Letter (e.g. School leave letter, Police complaint, Municipal application):
           Format recipient ('सेवा में, ...'), Subject ('विषय: ...'), Salutation ('महोदय / महोदया, ...'), Body paragraphs, and closing ('भवदीय / प्रार्थी / आपका आज्ञाकारी') in their natural, standard Indian official letter layout.
         * Legal Agreement / Deed (विलेख / अनुबंध):
           Format the Main Title at the top as '# [Title]' followed by a blank line. Write party descriptions, preambles, and numbered clauses ('1.', '2.') as continuous full-width paragraphs.
         * Affidavit (शपथ पत्र):
           Format Title '# शपथ पत्र', Deponent details, sworn points, and bottom Verification ('# सत्यापन' or 'तस्दीक').
         * Advocate Court Petitions & Applications (जमानत अर्जी, वकालतनामा, हाजिरी माफी, 156(3) अर्जी):
            - Preserve Court Heading at top: 'न्यायालय श्रीमान [पद / कोर्ट] महोदय, [स्थान]'.
            - Preserve Crime/Case citations: 'मुकदमा अपराध क्रमांक / वाद सं०: ...', 'थाना: ...', 'धारा: ...'.
            - Preserve Cause Title: '[प्रार्थी / अभियुक्त] बनाम [शासन / अनावेदक]'.
            - Main Petition Title: '# [प्रार्थना पत्र अंतर्गत धारा ... वास्ते जमानत / हाजिरी माफी / वकालतनामा]'.
            - Numbered legal grounds ('1.', '2.', '3.') and Prayer ('# प्रार्थना' or 'प्रार्थना:-').
            - Advocate signature & Bar Council details at bottom right:
              | | द्वारा अधिवक्ता: |
              | :--- | ---: |
              | | [हस्ताक्षर / नाम / एडवोकेट / नामांकन क्रमांक / चेंबर नं.] |
         * Advocate Legal Notices (विधिक नोटिस - e.g. धारा 138 चेक बाउंस, संपत्ति बेदखली):
            - Preserve Advocate/Firm Letterhead at top with Chamber, Court, and Contact details.
            - Format Date and Mode of Dispatch ('रजिस्टर्ड डाक / स्पीड पोस्ट A.D.').
            - Format Title '# विधिक नोटिस (LEGAL NOTICE)'.
            - Transcribe exact cheque numbers, dates, amounts, bank branches, and statutory demand periods ('15 दिवस').
            - Format Advocate closing block cleanly at bottom.
         * For Any Other Document / Notice / Receipt:
           Apply clean, professional typography and layout appropriate for that specific document.

    4. **Continuous Full-Width Paragraphs (आधी-अधूरी लाइन न तोड़ें, पूरा पैराग्राफ लिखें)**:
       - DO NOT break sentences into short half-lines just because a notebook line ended physically.
       - Write each paragraph or numbered clause as ONE continuous flowing block so that in MS Word and A4 paper it fills the entire width naturally.

    5. **Smart Signatures & Layout (हस्ताक्षर स्पेसिंग)**:
       - If there are TWO parties/signatures side-by-side (left and right), format them as a clean 2-column Markdown table:
         | [Left Party / Signature] | [Right Party / Signature] |
         | :--- | ---: |
         | [Details] | [Details] |
        - If there is only ONE person signing (e.g. Applicant / Deponent in an application, Student in school letter, Employee in corporate letter):
          * For Hindi applications, affidavits, and school letters: Keep the sign-off and credentials neatly aligned to the right:
            | | [भवदीय / आज्ञाकारी शिष्य / शपथकर्ता] |
            | :--- | ---: |
            | | [नाम / पद / कक्षा / अनुक्रमांक] |
          * For standard English corporate letters: Keep the entire sign-off block ('Sincerely,', Name, Title, Contact) uniformly left-aligned (standard corporate full-block format).

    Ensure your response strictly matches the required JSON schema.
    """
    
    models = ["gemini-3.7-flash", "gemini-flash-lite-latest", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]
    last_err = None
    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=processed_image_bytes, mime_type=target_mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TranscriptionResult
                )
            )
            data = json.loads(response.text)
            return TranscriptionResult(**data)
        except Exception as e:
            last_err = e
            print(f"Model {model_name} failed: {e}. Trying fallback...")
            continue
    raise last_err

def transcribe_audio_dictation(audio_bytes: bytes, mime_type: str = "audio/wav") -> TranscriptionResult:
    """
    Sends speech dictation audio to Gemini to transcribe and format into a structured legal document.
    """
    client = get_genai_client()
    
    prompt = """
    You are an expert audio transcription assistant for legal, official, and administrative document dictation.
    Transcribe the spoken audio dictation into a clean, professional, print-ready Markdown document.

    STRICT RULES FOR REAL HUMAN SPEECH:
    1. **Conversational Chitchat & Noise Filtering (बातचीत व फ़ालतू बातों को हटाएं)**:
       - Speakers often converse with the typist, ask for water/tea, check on the printer, or greet (e.g. "Hello brother", "चाय पी लूँ...", "प्रिंटर चल रहा है क्या", "Wait, hold on, let me take a sip of tea... where were we?").
       - COMPLETELY OMIT all conversational chit-chat, side remarks, and casual talk. Do NOT put them in the final document!

    2. **Convert Spoken Formatting Commands into Markdown (निर्देशों को फ़ॉर्मैटिंग में बदलें)**:
       - If the speaker says: "Title at top: [Title]" or "ऊपर हेडिंग डालो [शीर्षक]" -> '# [Title]'
       - If the speaker says: "Point number one / पहला पॉइंट" -> '1. [Text]'
       - If the speaker dictates side-by-side signatures (e.g. "At the bottom, make two signature columns: on the left Landlord..., on the right Tenant..."):
         Format as a clean 2-column Markdown table:
         | [Left Party / Title] | [Right Party / Title] |
         | :--- | ---: |
         | [Left Name] | [Right Name] |
       - If the speaker dictates a single signature at the end, align it to the right:
         | | [हस्ताक्षर / नाम / पद] |
         | :--- | ---: |

    3. **Stutter, Slip of Tongue & Self-Corrections (हकलाना व सुधार)**:
       - When the speaker corrects themselves (e.g. "9000... no wait, make that 9500", or "नाम अमित... नहीं नहीं, सुमित लिखो"), transcribe ONLY the final intended correction ("9500" / "सुमित").

    4. **Accurate Legal Text & Numbers**:
       - Transcribe the actual agreement terms, party names, dates, and amounts faithfully.
       - DO NOT invent or add any unmentioned clauses or legal boilerplate.

    Ensure your response strictly matches the required JSON schema.
    """
    
    models = ["gemini-3.7-flash", "gemini-flash-lite-latest", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]
    last_err = None
    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TranscriptionResult
                )
            )
            data = json.loads(response.text)
            return TranscriptionResult(**data)
        except Exception as e:
            last_err = e
            print(f"Model {model_name} failed: {e}. Trying fallback...")
            continue
    raise last_err
