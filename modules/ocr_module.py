import cv2
import easyocr
import pytesseract
import re


# =========================================================
# 1. CREATE EASY OCR READER (lazy — avoids slow import at startup)
# =========================================================

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


# =========================================================
# 2. PREPROCESS DOCUMENT
# =========================================================

def preprocess_image(image_path):

    # Read the image
    image = cv2.imread(image_path)

    # Check if image was loaded
    if image is None:
        raise ValueError("Could not open the image.")

    # Convert BGR colour image to grayscale
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    # Remove noise
    denoised = cv2.fastNlMeansDenoising(
        gray
    )

    # Improve contrast
    enhanced = cv2.equalizeHist(
        denoised
    )

    return enhanced


# =========================================================
# 3. EASY OCR
# =========================================================

def easyocr_extract(image):

    results = _get_reader().readtext(image)

    detections = []

    for result in results:

        bounding_box = result[0]
        text = result[1]
        confidence = result[2]

        detections.append({
            "text": text,
            "confidence": confidence,
            "bounding_box": bounding_box
        })

    return detections


# =========================================================
# 4. PYTESSERACT OCR
# =========================================================

def tesseract_extract(image):

    text = pytesseract.image_to_string(
        image
    )

    return text


# =========================================================
# 5. NORMALIZE TEXT
# =========================================================

def normalize_text(text):

    text = text.upper()

    text = re.sub(
        r'\s+',
        ' ',
        text
    )

    return text.strip()


# =========================================================
# 6. COMPARE OCR RESULTS
# =========================================================

def compare_ocr_results(
    easy_detections,
    tesseract_text
):

    easy_text = " ".join(
        detection["text"]
        for detection in easy_detections
    )

    easy_text = normalize_text(
        easy_text
    )

    tesseract_text = normalize_text(
        tesseract_text
    )

    if not easy_text or not tesseract_text:
        return 0

    easy_words = set(
        easy_text.split()
    )

    tesseract_words = set(
        tesseract_text.split()
    )

    common_words = (
        easy_words.intersection(
            tesseract_words
        )
    )

    agreement = (
        len(common_words)
        / len(easy_words)
    ) * 100

    return agreement


# =========================================================
# 7. EXTRACT ID
# =========================================================

def extract_aadhaar(full_text):
    """Extract 12-digit Aadhaar number (with or without spaces)."""
    normalized = full_text.upper().replace("O", "0").replace("I", "1").replace("L", "1")

    spaced = re.search(r"(?<!\d)(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})(?!\d)", normalized)
    if spaced:
        return re.sub(r"[\s\-]", "", spaced.group(1))

    plain = re.search(r"(?<!\d)(\d{12})(?!\d)", normalized)
    if plain:
        return plain.group(1)

    return None


def extract_id(full_text, doc_type=None):
    # Always try Aadhaar first — users often leave "Passport" selected by mistake.
    aadhaar = extract_aadhaar(full_text)
    if aadhaar:
        return aadhaar

    id_pattern = (
        r'\b[A-Z]{1,5}\d{5,10}\b'
    )

    match = re.search(
        id_pattern,
        full_text.upper()
    )

    if match:
        return match.group()

    return None


# =========================================================
# 8. EXTRACT DATES
# =========================================================

def extract_dates(full_text):

    date_pattern = (
        r'(?<!\d)(\d{2}[/-]\d{2}[/-]\d{4})(?!\d)'
    )

    dates = re.findall(
        date_pattern,
        full_text
    )

    # Aadhaar sometimes shows only Year of Birth (4 digits after YOB label)
    yob_match = re.search(r'YOB[:\s]*(\d{4})', full_text.upper())
    if yob_match and not dates:
        dates.append(f"01/01/{yob_match.group(1)}")

    return dates


# =========================================================
# 9. EXTRACT NAME
# =========================================================

def extract_name(text_list):

    for i, text in enumerate(text_list):

        normalized = text.upper().strip().rstrip(":")

        if normalized in [
            "NAME:",
            "NAME",
            "नाम",
        ]:

            if i + 1 < len(text_list):

                return text_list[i + 1]

    return None


def extract_name_aadhaar(text_list):
    """Fallback for Aadhaar cards where the name is not prefixed with 'Name:'."""
    skip_fragments = (
        "GOVERNMENT", "INDIA", "AADHAAR", "AADHAR", "UNIQUE", "IDENTIFICATION",
        "AUTHORITY", "MALE", "FEMALE", "DOB", "YOB", "YEAR", "BIRTH", "ADDRESS",
        "VID", "HELP", "WWW", "UIDAI", "GOV", "OFINDIA", "QOVERNMENT",
    )
    candidates = []
    for text in text_list:
        clean = re.sub(r"[^A-Za-z\s.]", "", text).strip()
        if len(clean) < 4:
            continue
        upper = clean.upper()
        if any(frag in upper for frag in skip_fragments):
            continue
        if re.search(r"\d", clean):
            continue
        words = clean.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z.]+", w) for w in words):
            candidates.append(clean)
    if candidates:
        # Prefer typical person-name shape (2-3 words) over longer headers
        candidates.sort(key=lambda n: (abs(len(n.split()) - 2), -len(n)))
        return candidates[0]
    return None


# =========================================================
# 10. EXTRACT ALL DOCUMENT FIELDS
# =========================================================

def extract_fields(detections, doc_type=None):

    text_list = [
        detection["text"]
        for detection in detections
    ]

    full_text = " ".join(
        text_list
    )

    fields = {}

    # Extract ID
    document_id = extract_id(
        full_text, doc_type=doc_type
    )

    if document_id:
        fields["ID"] = document_id

    # Extract dates
    dates = extract_dates(
        full_text
    )

    if len(dates) >= 1:
        fields["Date_1"] = dates[0]

    if len(dates) >= 2:
        fields["Date_2"] = dates[1]

    # Extract name
    name = extract_name(
        text_list
    )
    if not name and doc_type in ("national_id", "aadhaar", None):
        name = extract_name_aadhaar(text_list)

    if name:
        fields["Name"] = name

    return fields


# =========================================================
# 11. CALCULATE OCR CONFIDENCE
# =========================================================

def calculate_confidence(detections):

    if not detections:
        return 0

    total = sum(
        detection["confidence"]
        for detection in detections
    )

    average = (
        total / len(detections)
    ) * 100

    return average


# =========================================================
# 12. COMPLETE OCR PIPELINE
# =========================================================

def process_document(image_path, doc_type=None):

    print("\nProcessing document...\n")

    # -----------------------------------------
    # STEP 1: PREPROCESS
    # -----------------------------------------

    processed_image = preprocess_image(
        image_path
    )

    # -----------------------------------------
    # STEP 2: EASY OCR
    # -----------------------------------------

    easy_detections = easyocr_extract(
        processed_image
    )

    # -----------------------------------------
    # STEP 3: PYTESSERACT
    # -----------------------------------------

    tesseract_text = tesseract_extract(
        processed_image
    )

    # -----------------------------------------
    # STEP 4: OCR CONFIDENCE
    # -----------------------------------------

    confidence = calculate_confidence(
        easy_detections
    )

    # -----------------------------------------
    # STEP 5: OCR AGREEMENT
    # -----------------------------------------

    agreement = compare_ocr_results(
        easy_detections,
        tesseract_text
    )

    # -----------------------------------------
    # STEP 6: EXTRACT FIELDS
    # -----------------------------------------

    fields = extract_fields(
        easy_detections, doc_type=doc_type
    )

    # -----------------------------------------
    # STEP 7: DISPLAY EASY OCR RESULTS
    # -----------------------------------------

    print("====================================")
    print("           EASY OCR RESULTS")
    print("====================================")

    for detection in easy_detections:

        print(
            f"Text: {detection['text']}"
        )

        print(
            f"Confidence: "
            f"{detection['confidence']:.2f}"
        )

        print(
            f"Bounding Box: "
            f"{detection['bounding_box']}"
        )

        print("------------------------------------")

    # -----------------------------------------
    # STEP 8: DISPLAY TESSERACT RESULTS
    # -----------------------------------------

    print("\n====================================")
    print("         PYTESSERACT RESULTS")
    print("====================================")

    print(tesseract_text)

    # -----------------------------------------
    # STEP 9: DISPLAY SCORES
    # -----------------------------------------

    print(
        f"\nEasyOCR Confidence: "
        f"{confidence:.2f}%"
    )

    print(
        f"OCR Agreement: "
        f"{agreement:.2f}%"
    )

    # -----------------------------------------
    # STEP 10: DISPLAY FIELDS
    # -----------------------------------------

    print("\n====================================")
    print("         EXTRACTED FIELDS")
    print("====================================")

    for key, value in fields.items():

        print(
            f"{key}: {value}"
        )

    # -----------------------------------------
    # STEP 11: RETURN STRUCTURED RESULT
    # -----------------------------------------

    return {

        "easyocr": easy_detections,

        "pytesseract": tesseract_text,

        "ocr_confidence": confidence,

        "ocr_agreement": agreement,

        "fields": fields
    }


# =========================================================
# 13. PROGRAM START
# =========================================================

if __name__ == "__main__":

    image_path = "document.jpg"

    result = process_document(
        image_path
    )
