import logging
import re
from datetime import datetime, timezone, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from auth import get_creds

# ---------------- LOGGING SETUP ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ---------------- HELPERS ---------------- #

def _utf16_len(text):
    """Return length in UTF-16 code units (Google Docs API indexing)."""
    return len(text.encode('utf-16-le')) // 2


def _prepare_content(raw_content):
    """
    Strip markdown artifacts and identify section titles.

    Returns:
        lines:         list of cleaned text lines
        title_indices: set of line indices that are section / document titles
    """
    src_lines = raw_content.split('\n')
    out = []
    known_titles = set()

    for line in src_lines:
        stripped = line.strip()

        # Drop horizontal rules (---, ━━━, ───, ===)
        if re.match(r'^[-━─=]{3,}\s*$', stripped):
            continue

        # Convert markdown headings → plain text and remember as title
        hm = re.match(r'^#{1,3}\s+(.+)$', stripped)
        if hm:
            title = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', hm.group(1))
            known_titles.add(title.strip())
            out.append(title)
            continue

        # Strip bold / italic markers
        cleaned = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', line)

        # Convert dash bullets to Unicode bullets
        cleaned = re.sub(r'^- ', '  •  ', cleaned)

        out.append(cleaned)

    # Collapse consecutive blank lines into a single blank
    final = []
    prev_blank = False
    for ln in out:
        if not ln.strip():
            if not prev_blank:
                final.append('')
            prev_blank = True
        else:
            final.append(ln)
            prev_blank = False

    # Trim leading / trailing blanks
    while final and not final[0].strip():
        final.pop(0)
    while final and not final[-1].strip():
        final.pop()

    # Identify title line indices
    titles = set()
    for i, ln in enumerate(final):
        s = ln.strip()
        if not s:
            continue

        # Known markdown heading
        if s in known_titles:
            titles.add(i)
            continue

        # Heuristic: short non-bullet line followed by bullets or quotes
        if s.startswith('•') or s.startswith('"') or len(s) > 55:
            continue
        for j in range(i + 1, min(i + 4, len(final))):
            ns = final[j].strip()
            if ns:
                if ns.startswith('•') or ns.startswith('"'):
                    titles.add(i)
                break

    return final, titles


# ---------------- MAIN FUNCTION ---------------- #

def append_to_doc(doc_id: str, content: str):
    """
    Appends formatted, timestamped content to a Google Doc with
    native Docs styling for a polished, executive-ready look.

    Args:
        doc_id (str): Google Doc ID
        content (str): Text to append

    Returns:
        dict: status + message
    """

    try:
        logger.info(f"Starting append_to_doc for doc_id={doc_id}")

        # -------- INPUT VALIDATION -------- #
        if not doc_id or not content:
            logger.error("Missing doc_id or content")
            return {
                "status": "error",
                "message": "doc_id and content are required"
            }

        # -------- AUTH -------- #
        creds = get_creds()
        logger.info("Credentials loaded")

        # -------- INIT SERVICE -------- #
        service = build("docs", "v1", credentials=creds)
        logger.info("Google Docs service initialized")

        # -------- CURRENT DOC LENGTH -------- #
        doc = service.documents().get(documentId=doc_id).execute()
        body = doc.get('body', {}).get('content', [])
        doc_end = body[-1]['endIndex'] - 1 if body else 1

        # -------- CLEAN CONTENT -------- #
        lines, title_indices = _prepare_content(content)
        ist_tz = timezone(timedelta(hours=5, minutes=30), "IST")
        timestamp = datetime.now(ist_tz).strftime("%B %d, %Y at %I:%M %p IST")

        # -------- ASSEMBLE INSERT TEXT -------- #
        header = f"Weekly Update  \u00b7  {timestamp}"
        body_text = '\n'.join(lines)

        # Three newlines for visual separation, then header, blank line, content
        insert_text = f"\n\n\n{header}\n\n{body_text}\n"

        # -------- CALCULATE CHARACTER RANGES (UTF-16) -------- #
        pos = doc_end

        prefix_len = _utf16_len("\n\n\n")
        header_start = pos + prefix_len
        header_len = _utf16_len(header)
        header_end = header_start + header_len          # excludes trailing \n

        content_start = header_end + _utf16_len("\n\n")  # after header\n\n

        # Line-level positions within the body text
        line_ranges = []
        p = content_start
        for ln in lines:
            ln_len = _utf16_len(ln)
            line_ranges.append((p, p + ln_len))
            p += ln_len + 1                              # +1 for \n

        # -------- BUILD API REQUESTS -------- #
        requests = []

        # 1. Insert the full text block
        requests.append({
            "insertText": {
                "endOfSegmentLocation": {},
                "text": insert_text
            }
        })

        # 2. Style the header text — bold, 13 pt, dark navy
        requests.append({
            "updateTextStyle": {
                "range": {
                    "startIndex": header_start,
                    "endIndex": header_end
                },
                "textStyle": {
                    "bold": True,
                    "fontSize": {"magnitude": 13, "unit": "PT"},
                    "foregroundColor": {
                        "color": {
                            "rgbColor": {
                                "red": 0.16,
                                "green": 0.21,
                                "blue": 0.58
                            }
                        }
                    }
                },
                "fields": "bold,fontSize,foregroundColor"
            }
        })

        # 3. Header paragraph — subtle bottom border + spacing
        requests.append({
            "updateParagraphStyle": {
                "range": {
                    "startIndex": header_start,
                    "endIndex": header_end + 1
                },
                "paragraphStyle": {
                    "borderBottom": {
                        "color": {
                            "color": {
                                "rgbColor": {
                                    "red": 0.78,
                                    "green": 0.78,
                                    "blue": 0.78
                                }
                            }
                        },
                        "width": {"magnitude": 0.5, "unit": "PT"},
                        "dashStyle": "SOLID",
                        "padding": {"magnitude": 8, "unit": "PT"}
                    },
                    "spaceAbove": {"magnitude": 24, "unit": "PT"},
                    "spaceBelow": {"magnitude": 14, "unit": "PT"}
                },
                "fields": "borderBottom,spaceAbove,spaceBelow"
            }
        })

        # 4. Style section / document titles
        first_title = True
        for idx in sorted(title_indices):
            if idx >= len(line_ranges):
                continue
            start, end = line_ranges[idx]
            if start >= end:
                continue

            # First title (document title) gets a larger font
            font_size = 14 if first_title else 11

            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": {
                        "bold": True,
                        "fontSize": {"magnitude": font_size, "unit": "PT"},
                        "foregroundColor": {
                            "color": {
                                "rgbColor": {
                                    "red": 0.20,
                                    "green": 0.20,
                                    "blue": 0.20
                                }
                            }
                        }
                    },
                    "fields": "bold,fontSize,foregroundColor"
                }
            })

            # Add breathing room above each section title
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end + 1},
                    "paragraphStyle": {
                        "spaceAbove": {
                            "magnitude": 8 if first_title else 16,
                            "unit": "PT"
                        },
                        "spaceBelow": {"magnitude": 4, "unit": "PT"}
                    },
                    "fields": "spaceAbove,spaceBelow"
                }
            })

            first_title = False

        # -------- EXECUTE API CALL -------- #
        try:
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()

            logger.info("Content appended and formatted successfully")

            return {
                "status": "success",
                "message": "Content appended to document",
                "document_id": doc_id
            }

        except HttpError as e:
            logger.error(f"Google Docs API error: {e}")

            return {
                "status": "error",
                "message": "Google Docs API error",
                "details": str(e)
            }

        except Exception as e:
            logger.error(f"Execution error: {e}")

            return {
                "status": "error",
                "message": "Failed during API execution",
                "details": str(e)
            }

    # -------- FALLBACK ERROR -------- #
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

        return {
            "status": "error",
            "message": "Unexpected error occurred",
            "details": str(e)
        }