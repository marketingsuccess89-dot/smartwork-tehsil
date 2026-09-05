import os
import re
import json
import io
import time
from PIL import Image, ImageOps, ImageEnhance
# Allow processing very large DSLR and high-megapixel camera photos without DecompressionBombError
Image.MAX_IMAGE_PIXELS = None

from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

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

        # Resize first to target resolution to minimize memory and accelerate processing
        width, height = img.size
        if max(width, height) > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Intelligent contrast & sharpness boost on target resolution for crisp OCR legibility
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.15)
        sharpener = ImageEnhance.Sharpness(img)
        img = sharpener.enhance(1.25)
            
        out_io = io.BytesIO()
        img.save(out_io, format="JPEG", quality=quality, optimize=True)
        return out_io.getvalue()
    except Exception as e:
        print(f"Image preprocessing/compression failed: {e}")
        return image_bytes

_cached_client = None

PRIMARY_MODEL = "gemini-3.6-flash"
SECONDARY_MODEL = "gemini-3.5-flash"
EMERGENCY_MODELS = ["gemini-3.7-flash", "gemini-2.5-flash", "gemini-flash-latest"]

RATE_LIMIT_COOLDOWN = 60.0  # 60 seconds cooldown window matching Google API quota window

# Model cooldown state: {model_name: timestamp_when_cooldown_ends}
_model_cooldowns: dict[str, float] = {
    PRIMARY_MODEL: 0.0,
    SECONDARY_MODEL: 0.0
}

def is_rate_limit_error(e: Exception) -> bool:
    """Checks whether an exception corresponds to a 429 / Quota / Rate Limit error."""
    err_str = str(e).lower()
    err_type = type(e).__name__.lower()
    return any(marker in err_str or marker in err_type for marker in [
        "429", "resource_exhausted", "resourceexhausted", "quota", "rate limit", "rate_limit", "too many requests"
    ])

def record_model_rate_limit(model_name: str):
    """Activates cooldown for a model that exceeded its rate limit."""
    _model_cooldowns[model_name] = time.time() + RATE_LIMIT_COOLDOWN
    print(f"[ModelManager] [WARNING] Rate limit exceeded on '{model_name}'. Switching to backup model for {RATE_LIMIT_COOLDOWN}s.")

def get_prioritized_models() -> list[str]:
    """
    Returns dynamically ordered models:
    - Models not in cooldown are prioritized in preferred order (PRIMARY -> SECONDARY -> EMERGENCY).
    - Models in cooldown are placed at the end, ordered by which cooldown expires first.
    """
    now = time.time()
    base_order = [PRIMARY_MODEL, SECONDARY_MODEL] + [m for m in EMERGENCY_MODELS if m not in (PRIMARY_MODEL, SECONDARY_MODEL)]
    
    ready_models = [m for m in base_order if now >= _model_cooldowns.get(m, 0.0)]
    cooling_models = [m for m in base_order if now < _model_cooldowns.get(m, 0.0)]
    cooling_models.sort(key=lambda m: _model_cooldowns.get(m, 0.0))
    
    if cooling_models and not ready_models:
        print(f"[ModelManager] All models in cooldown! Attempting nearest cooldown model '{cooling_models[0]}'.")
    elif cooling_models and PRIMARY_MODEL in cooling_models:
        remaining = int(_model_cooldowns[PRIMARY_MODEL] - now)
        next_model = ready_models[0] if ready_models else cooling_models[0]
        print(f"[ModelManager] Primary '{PRIMARY_MODEL}' is cooling down ({remaining}s remaining). Routing to '{next_model}'.")

    return ready_models + cooling_models

def get_model_status() -> dict:
    """Returns real-time status of model priorities and cooldown timers."""
    now = time.time()
    primary_remaining = max(0, int(_model_cooldowns.get(PRIMARY_MODEL, 0.0) - now))
    secondary_remaining = max(0, int(_model_cooldowns.get(SECONDARY_MODEL, 0.0) - now))
    active_models = get_prioritized_models()
    active_default = active_models[0] if active_models else PRIMARY_MODEL
    return {
        "active_primary": active_default,
        "default_primary": PRIMARY_MODEL,
        "secondary_backup": SECONDARY_MODEL,
        "primary_cooldown_remaining_sec": primary_remaining,
        "secondary_cooldown_remaining_sec": secondary_remaining,
        "is_fallback_active": primary_remaining > 0
    }

def get_genai_client():
    global _cached_client
    if _cached_client is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file = os.path.join(project_root, ".env")
        if os.path.exists(env_file):
            try:
                from dotenv import dotenv_values
                env_vals = dotenv_values(env_file)
                if env_vals.get("GEMINI_API_KEY"):
                    os.environ["GEMINI_API_KEY"] = env_vals["GEMINI_API_KEY"]
            except Exception:
                pass
        load_dotenv(override=True)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment. Please add it to your .env file.")
        _cached_client = genai.Client(api_key=api_key)
    return _cached_client

def extract_text_from_images(image_bytes_list: list[bytes]) -> TranscriptionResult:
    """
    Sends 1 or multiple document page images to Gemini Vision to perform verbatim OCR 
    with legal standardization rules, transcribing multi-page deeds seamlessly in order.
    """
    if not image_bytes_list:
        raise ValueError("कम से कम एक पेज की फ़ोटो आवश्यक है।")

    # Fast compress, contrast-enhance, and resize each page image
    parts = []
    for idx, img_b in enumerate(image_bytes_list):
        compressed_b = compress_image(img_b)
        parts.append(types.Part.from_bytes(data=compressed_b, mime_type="image/jpeg"))

    client = get_genai_client()
    
    num_pages = len(image_bytes_list)
    page_context = ""
    if num_pages > 1:
        page_context = f"""
    IMPORTANT: MULTI-IMAGE INTELLIGENT DOCUMENT & BOUNDARY RECOGNITION (बहु-फ़ोटो एवं दस्तावेज़ पहचान नियम):
    You have been provided {num_pages} uploaded document photos in sequence.
    Carefully inspect each photo's visual layout, formal headers, and textual flow to detect whether they belong to the SAME continuous document or are MULTIPLE DIFFERENT letters/applications:

    CASE 1: CONTINUATION OF THE SAME DOCUMENT (एक ही दस्तावेज़ / डीड के क्रमिक पेज):
    - Indicators: A legal agreement or deed (e.g. बैनामा, किरायानामा, इकरारनामा, शपथ पत्र) where Page 2 continues clauses from Page 1, mid-sentence flow across pages, continuous clause numbering (e.g. 1..5 on Page 1, 6..10 on Page 2), or page numbers ('पेज 1', 'पेज 2', 'Page 2 of 3'), with final signatures only on the last page.
    - Formatting: Flow the terms, conditions, and numbered clauses continuously in chronological order into ONE unified document. DO NOT repeat or duplicate the main title/header on subsequent pages. Format signatures only at the end of the final page.

    CASE 2: MULTIPLE SEPARATE INDEPENDENT DOCUMENTS / LETTERS (अलग-अलग स्वतंत्र पत्र / प्रार्थना पत्र):
    - Indicators: A user uploads 2, 3, or 4 different letters or applications at the same time (e.g. School leave letter + Police complaint + Electricity application, or independent affidavits for different persons). Each has its own distinct formal opening ('सेवा में, ...', 'न्यायालय श्रीमान...', '# शपथ पत्र', '# प्रार्थना पत्र', new subject 'विषय: ...', new date, new recipient, or complete individual closing signatures).
    - Formatting:
      * NEVER merge or glue separate letters together! Each letter MUST be kept completely distinct.
      * Whenever a NEW separate letter/document begins, you MUST insert a Markdown page-break line:
        ---
        (Three hyphens on their own line with a blank line before and after).
      * After '---', format the next letter completely starting with its own Title, 'सेवा में, ...', Subject, Body paragraphs, and closing signatures.

    CASE 3: MIXED (e.g. Document 1 has 2 pages, followed by a separate 1-page letter):
      * Flow the 2 pages of Document 1 continuously.
      * When Document 1 finishes with its signatures, insert '---'.
      * Then start Document 2 on a fresh new page.
    """

    prompt = f"""
    You are an expert universal OCR and legal/official document typing assistant for Indian Tehsil, Court, School, and Government offices.
    Analyze the provided document image(s) and transcribe them with high intelligence into professional, print-ready Markdown format.
    {page_context}

    1. **100% Strict Verbatim Words & Proper Noun Preservation (नाम व वाक्य की मूल भावना अक्षुण्ण रखें)**:
       - **Personal Names, Father's Names, Castes, Villages, Towns, IDs (नामों की स्पेलिंग कभी न बदलें)**:
         * NEVER auto-correct or alter the spelling of ANY person's name, surname, father's name, or village name!
         * Even if a name looks dialectical or unconventional (e.g. 'रामेशवर परसाद', 'कलूराम', 'बचनू लाल', 'सुनील', 'झिनझिनिया'), transcribe the EXACT spelling as written. Changing a person's name invalidates their legal registration with Government IDs.
       - **Preserve Sentence Meaning Exactly (वाक्य का अर्थ चाहे अजीब हो, वैसा ही लिखें)**:
         * NEVER rephrase, rewrite, paraphrase, summarize, or alter strange, illogical, or informal sentences.
         * Whatever conditions or statements are written, transcribe them EXACTLY as written without trying to "make more sense" of them.
       - **Standard Hindi Legal & General Orthography (कानूनी व सामान्य शब्दों की शुद्ध मानक वर्तनी)**:
         * Standard generic and legal words (e.g. 'किरायानामा', 'इकरारनामा', 'बैनामा', 'शपथ पत्र', 'प्रथम पक्ष', 'द्वितीय पक्ष', 'हस्ताक्षर', 'साक्षी', 'गवाह', 'यह कि', 'प्रभावी', 'प्रतिमाह', 'अवधि', 'धरोहर', 'सूचना', 'निवासी', 'उभय पक्ष', 'स्वीकृत', 'प्रार्थना पत्र') MUST be transcribed with 100% correct standard Devanagari Hindi spelling and matras!
         * NEVER output broken phonetic slips like 'करियानामा', 'दवतीय', 'परथम', 'हसताक्षर', 'साक्क्षी', or 'यह का'. Always write them cleanly and correctly as 'किरायानामा', 'द्वितीय पक्ष', 'प्रथम पक्ष', 'हस्ताक्षर', 'साक्षी', 'यह कि'.
         * (Remember: ONLY personal names of individuals, their father's names, castes, and villages must preserve their specific spelling as written).
       - **Strikethrough (काटा हुआ)**:
         * If any word is crossed out with a pen line, ignore the crossed-out text and transcribe the intended correction.

    2. **Pre-Printed Government Stamp Paper Rule (स्टाम्प पेपर के सरकारी हेडर को कभी न लिखें)**:
       - If the document (specifically Page 1) is written on an official Indian Stamp Paper (₹10, ₹50, ₹100, ₹500 Non-Judicial paper with State/Government emblem):
         * Set `stamp_paper_detected = True`.
         * DO NOT transcribe the pre-printed government stamp header (e.g. "भारत सरकार", "GOVERNMENT OF INDIA", National Emblem / Lion Capital, "NON JUDICIAL / गैर न्यायिक", "₹100", Serial No., Vendor Name/Seal/Barcode, or "Notary Stamp below").
         * Physical stamp papers already contain these factory-printed. Typists insert the physical stamp paper into the printer, and typing MUST start strictly from the actual legal content (e.g. '# शपथ पत्र (Affidavit)', or Court/Authority heading 'समक्ष: श्रीमान...').
       - If it is on normal notebook, register, or plain blank paper, set `stamp_paper_detected = False`.

    3. **Intelligent Document Format Recognition (दस्तावेज़ के प्रकार अनुसार सही फ़ॉर्मैटिंग)**:
       - Understand the exact nature of the document from the image(s):
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
            - Advocate signature & Bar Council details at bottom right (clean text lines, NOT a table):
              द्वारा अधिवक्ता:
              [हस्ताक्षर / नाम / एडवोकेट]
              [नामांकन क्रमांक / चेंबर नं. / मोबाइल]
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

    5. **Signatures & Sign-off Layout (हस्ताक्षर व परिचय नियम)**:
       - **TWO PARTIES SIDE-BY-SIDE (दो पक्षों के हस्ताक्षर - Left और Right अलग-अलग रहें, कभी मिक्स न हों)**:
         * If there are two parties signing side-by-side (e.g. In deeds/agreements: Landlord & Tenant, Buyer & Seller, First Party & Second Party, or Witness 1 & Witness 2):
           Format them strictly as a clean 2-column Markdown table so that Left and Right parties remain completely separated with clear space between them and NEVER mix or overlap:
           | [Left Party / प्रथम पक्ष] | [Right Party / द्वितीय पक्ष] |
           | :--- | ---: |
           | हस्ताक्षर: ____________ | हस्ताक्षर: ____________ |
           | नाम: [नाम] | नाम: [नाम] |
           | [अन्य विवरण] | [अन्य विवरण] |
       - **SINGLE SIGNATORY / APPLICANT INTRODUCTION (एकल हस्ताक्षर / प्रार्थी / भवदीय / शपथकर्ता परिचय)**:
         * When there is only ONE applicant, deponent, student, or person introducing themselves / signing at the bottom (e.g. In Applications, School Letters, Affidavits, Petitions):
           DO NOT CREATE ANY TABLE FOR A SINGLE PERSON! (एकल हस्ताक्षर या परिचय के लिए टेबल कभी न बनाएं)।
           Write the sign-off and personal introduction directly as clean, normal text lines (without any pipe '|' symbols):
           भवदीय / प्रार्थी / शपथकर्ता,
           [नाम]
           [पिता का नाम / पद]
           [पता / मोबाइल नंबर]
       - **Standard English Corporate Letters**:
         Write the sign-off block ('Sincerely,', Name, Title, Contact) as clean text lines without tables.

    Ensure your response strictly matches the required JSON schema.
    """
    
    parts.append(prompt)

    models = get_prioritized_models()
    last_err = None
    for model_name in models:
        try:
            print(f"[Gemini Vision] Requesting model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TranscriptionResult
                )
            )
            clean_text = (response.text or "").strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                clean_text = re.sub(r"\s*```$", "", clean_text).strip()
            data = json.loads(clean_text)
            return TranscriptionResult(**data)
        except Exception as e:
            last_err = e
            if is_rate_limit_error(e):
                record_model_rate_limit(model_name)
            print(f"Model {model_name} failed: {e}. Trying fallback...")
            continue
    raise last_err

def extract_text_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> TranscriptionResult:
    """Backward-compatible wrapper for single image OCR."""
    return extract_text_from_images([image_bytes])

def transcribe_audio_dictation(audio_bytes: bytes, mime_type: str = "audio/wav") -> TranscriptionResult:
    """
    Sends speech dictation audio to Gemini to transcribe and format into a structured legal document.
    """
    client = get_genai_client()
    
    prompt = """
    You are an expert audio transcription assistant specialized in Indian Legal, Court, Tehsil, and Administrative document dictation (तहसील व न्यायालय विलेख एवं प्रार्थना पत्र).
    Transcribe the spoken audio dictation into a clean, professional, print-ready Markdown document.

    STRICT RULES FOR DESI & REAL HUMAN SPEECH (देसी बोलचाल व मौखिक निर्देशों के नियम):
    1. **Conversational Chitchat & Side Remarks Filtering (आपसी बातचीत व फ़ालतू बातों को 100% हटाएं)**:
       - Elderly advocates, deed writers (कातिब/मुंशी), and rural citizens speak casually to the typist while dictating:
         * e.g. "अरे मुंशी जी सुनो...", "टाइपिंग वाले बाबू ध्यान से लिखना...", "अरे चाय ठंडी हो रही है ज़रा एक घूँट पी लूँ...", "कहाँ थे हम... हाँ...", "अरे भैया समझ रहे हो ना...", "प्रिंटर ठीक चल रहा है?", "ज़रा पानी देना...".
       - NEVER include any of these casual remarks, instructions to the typist, or personal chitchat in the transcribed document!

    2. **Spoken Formatting & Layout Directives (मौखिक फ़ॉर्मैटिंग व लाइन निर्देशों को Markdown में बदलें)**:
       - Recipient Block ("सेवा में" का सही प्रारूप):
         * ALWAYS place "**सेवा में,**" on its own separate line.
         * The recipient's official title/designation and office/district MUST start on the subsequent line(s) below it:
           ```markdown
           **सेवा में,**  
           श्रीमान उपजिलाधिकारी महोदय,  
           तहसील सोहना, जनपद गुरुग्राम।
           ```
         * NEVER merge "सेवा में," and the recipient's name into a single combined line!
       - Line Breaks & Paragraphs:
         * "अब नीचे की लाइन से..." / "अगली लाइन में लिखो..." / "नीचे लिखो..." -> Insert a clean line break (`\n`).
         * "पैरा बदलो..." / "नया पैराग्राफ बनाओ..." / "एक लाइन छोड़ कर लिखो..." -> Insert a new paragraph break (`\n\n`).
       - Headers & Topics:
         * "ऊपर हेडिंग डालो..." / "मोटे अक्षरों में शीर्षक लिखो..." -> '# [Title]' or '## [Title]'.
         * "विषय में लिखो..." / "सब्जेक्ट डालो..." -> '**विषय:** [Text]'.
       - Numbered Points:
         * "पॉइंट नंबर 1 / पहला पॉइंट...", "दूसरा पॉइंट...", "शर्त नंबर 1..." -> '1. [Text]', '2. [Text]'.
       - Parentheses:
         * "ब्रैकेट में लिखो..." / "कोष्ठक में डालो..." -> '([Text])'.
       - Signatures & Closings:
         * If speaker dictates side-by-side signatures for TWO parties (e.g. "प्रथम पक्ष बाएँ, द्वितीय पक्ष दाएँ"):
           Format as a clean 2-column Markdown table:
           | **प्रथम पक्ष** | **द्वितीय पक्ष** |
           | :--- | ---: |
           | हस्ताक्षर: ____________ | हस्ताक्षर: ____________ |
           | नाम: **[नाम]** | नाम: **[नाम]** |
         * If speaker dictates single applicant details (e.g. "प्रार्थी / शपथकर्ता / भवदीय"):
           Write as clean plain text block at the end (DO NOT create a table):
           **प्रार्थी / शपथकर्ता / भवदीय**,  
           **[नाम]**  
           [पिता का नाम / उम्र / पता]

    4. **Modern Professional Hindi Formatting (आधुनिक, सरल व मानक पेशेवर भाषा - कठिन/क्लिष्ट संस्कृत शब्दों से बचें)**:
       - DO NOT use overly archaic, hyper-Sanskritized, or artificially complex words that are not commonly used in today's offices/letters (जैसे 'अत्यधिक त्रुटिपूर्ण', 'निर्गत कर दिया', 'विद्युत विच्छेदन', 'अवलोकनार्थ', 'महती कृपा' जैसे भारी-भरकम शब्द न लिखें)।
       - Convert casual, conversational speech into **clean, respectful, modern standard professional Hindi** (आजकल के सरकारी/प्रशासनिक प्रार्थना पत्रों की सरल व स्पष्ट भाषा):
         * "बिजली का गलत बिल आने और मीटर सही कराने के बारे में" ➔ `**विषय:** गलत बिजली बिल सुधारने एवं खराब मीटर की जांच कराने हेतु प्रार्थना पत्र।`
         * "अचानक 48,500 का भारी-भरकम बिल भेज दिया" ➔ `विभाग द्वारा अचानक ₹48,500 का गलत बिल भेज दिया गया है।`
         * "मीटर बहुत तेज भाग रहा था और स्क्रीन लाइट बंद है... मीटर अंदर से खराब हो गया है" ➔ `मीटर अत्यधिक तेज चल रहा है तथा उसकी डिस्प्ले स्क्रीन लाइट बंद है, जिससे प्रतीत होता है कि मीटर खराब है।`
         * "कनेक्शन काट देंगे की धमकी दी" ➔ `बिल जमा न करने पर बिजली कनेक्शन काटने की चेतावनी दी गई।`
         * "पुराने बिलों की रसीदें साथ में लगा दी हैं उन्हें देख लेना" ➔ `पिछले 6 माह के सही बिलों की प्रतियां इस प्रार्थना पत्र के साथ संलग्न हैं।`
         * "हम गरीब आदमी हैं और बिल भरने में असमर्थ हैं" ➔ `प्रार्थी एक साधारण परिवार से है और इतना भारी बिल भरने में पूर्णतः असमर्थ है।`
         * "हाथ जोड़कर विनती है कि कर्मचारी भेजकर मीटर चेक करवाएं और बिल ठीक करें" ➔ `अतः श्रीमान जी से निवेदन है कि मौके पर कर्मचारी भेजकर मीटर की जांच कराने तथा गलत बिल को सुधारकर सही बिल जारी करने की कृपा करें।`
         * "असल में बात ये है कि / मामला ऐसा है कि" ➔ `विवरण निम्न प्रकार है:`
         * "मेरी जमीन पर कब्जा कर लिया" ➔ `प्रार्थी की जमीन पर अवैध रूप से कब्जा कर लिया गया है।`
         * "आम रास्ता रोक दिया" ➔ `आम रास्ते को गलत तरीके से बंद कर दिया गया है।`
       - Keep the language natural, fluent, modern, and easy to read while maintaining complete administrative respect and structure.

    5. **Filter Spoken Clause Starters & Conversational Preamble ('यह कि', 'प्रार्थी का नाम लिखो', 'लिखो कि' को हटाएं)**:
       - Advocates/speakers often use colloquial filler starters when dictating numbered points:
         * e.g. "पहला पॉइंट डालो... यह कि प्रार्थी का नाम लिखो... प्रार्थी रामपाल सिंह यादव..." -> Do NOT write "यह कि" or "प्रार्थी का नाम लिखो". Write directly: `1. प्रार्थी **रामपाल सिंह यादव** पुत्र...`
         * e.g. "दूसरा पॉइंट... यह कि प्रार्थी मौजा भोंडसी स्थित..." -> Write directly: `2. प्रार्थी मौजा भोंडसी स्थित...`
         * e.g. "चौथा पॉइंट लिखो... यह कि विपक्षी सुखबीर सिंह..." -> Write directly: `4. विपक्षी **सुखबीर सिंह** ने...`
       - Repetitive conversational prefixes like "यह कि", "इसमें लिखो कि", "लिखो कि", "अगला यह कि" are spoken artifacts used while explaining to the typist. Strip them so that each numbered point starts cleanly and directly with the subject matter.

    6. **Stutter, Slip of Tongue & Desi Self-Corrections (हकलाना, गलती सुधारना व 'अरे नहीं नहीं')**:
       - When the speaker hesitates, slips tongue, or corrects themselves:
         * e.g. "नाम रामकिशन... अरे नहीं नहीं, रामकिशन शर्मा लिखो" -> Transcribe ONLY "**रामकिशन शर्मा**".
         * e.g. "रकबा 5 बीघा... अरे रुको 5 नहीं, 4 बीघा 12 बिस्वा लिखो" -> Transcribe ONLY "**4 बीघा 12 बिस्वा**".
         * e.g. "उम्र 45... नहीं 48 वर्ष" -> Transcribe ONLY "**48 वर्ष**".
         * e.g. "दिनांक 10 मार्च... काट के 15 मार्च 2026 करो" -> Transcribe ONLY "**15 मार्च 2026**".
       - NEVER include the mistaken words or the correction phrases ("अरे नहीं नहीं", "काट के", "गलत हो गया").

    7. **Intelligent Markdown Bolding (बोल्ड करने के सटीक नियम)**:
       - **Main Names (मुख्य व्यक्तियों व पक्षों के नाम बोल्ड करें)**:
         * Person names, father's names, caste, age, village: e.g. **रामकिशन शर्मा**, **स्वर्गीय मुंशी लाल**, **62 वर्ष**, **ग्राम देवली**.
       - **Land Details, Numbers & Measurements (भूमि रकबा, गाटा संख्या व नाप-जोख)**:
         * Specific land numbers and areas: e.g. **गाटा संख्या 342**, **रकबा 0.450 हेक्टेयर**, **4 बीघा 12 बिस्वा**.
       - **Financial Amounts (धनराशि व लेन-देन)**:
         * e.g. **₹4,50,000 (चार लाख पचास हजार रुपये)**, **50,000 रुपये नकद**.
       - **Chauhaddi / Boundaries (चौहद्दी व दिशाएं)**:
         * e.g. **पूरब:** ..., **पश्चिम:** ..., **उत्तर:** ..., **दक्षिण:** ...
       - **Document Labels & Roles (शीर्षक व पद)**:
         * e.g. **विषय:**, **शपथ पत्र**, **बनाम**, **प्रार्थी:**, **अनावेदक:**, **गवाहान:**, **सत्यापन:**.
       - **DO NOT Bold Regular Narrative Sentences (सामान्य कथनों को बोल्ड न करें)**:
         * 'निवेदन है कि...', 'अतः श्रीमान से प्रार्थना है कि...' should remain normal unbolded text.

    8. **Accurate Legal Terminology**:
       - Preserve authentic Indian legal words when specifically mentioned (e.g. खतौनी, इंतकाल, काश्तकार, बैनामा, इकरारनामा, वसीयतनामा, चौहद्दी, तकसीम, दाखिल खारिज).

    Ensure your response strictly matches the required JSON schema.
    """
    
    models = get_prioritized_models()
    last_err = None
    for model_name in models:
        try:
            print(f"[Gemini Audio] Requesting model: {model_name}...")
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
            clean_text = (response.text or "").strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                clean_text = re.sub(r"\s*```$", "", clean_text).strip()
            data = json.loads(clean_text)
            return TranscriptionResult(**data)
        except Exception as e:
            last_err = e
            if is_rate_limit_error(e):
                record_model_rate_limit(model_name)
            print(f"Model {model_name} failed: {e}. Trying fallback...")
            continue
    raise last_err
