import re
from fastapi import Request, HTTPException

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|commands?)",
    r"(?i)forget\s+(all\s+)?(previous|prior|above)",
    r"(?i)you\s+are\s+now\s+(a\s+)?(god|master|admin)",
    r"(?i)system\s*prompt\s*:",
    r"(?i)you\s+must\s+(obey|comply)",
]


def sanitize_input(text: str) -> str:
    if len(text) > 10000:
        text = text[:10000]
    return text.strip()


def detect_injection(text: str) -> bool:
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


async def sanitizer_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT") and request.url.path.startswith("/api/"):
        try:
            body = await request.json()
            for key, value in body.items():
                if isinstance(value, str) and detect_injection(value):
                    raise HTTPException(status_code=422, detail="Invalid input detected")
                if isinstance(value, str):
                    body[key] = sanitize_input(value)
        except HTTPException:
            raise
        except Exception:
            pass
    response = await call_next(request)
    return response
