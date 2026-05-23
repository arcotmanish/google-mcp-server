import logging
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from auth import get_creds

# ---------------- LOGGING SETUP ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ---------------- MAIN FUNCTION ---------------- #
def append_to_doc(doc_id: str, content: str):
    """
    Appends timestamped content to a Google Doc.

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

        # -------- FORMAT CONTENT -------- #
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        formatted_content = (
            f"\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 MCP Server Update  •  {timestamp}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{content}\n"
        )

        # -------- PREPARE REQUEST -------- #
        requests = [
            {
                "insertText": {
                    "endOfSegmentLocation": {},
                    "text": formatted_content
                }
            }
        ]

        # -------- EXECUTE API CALL -------- #
        try:
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()

            logger.info("Content appended successfully")

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