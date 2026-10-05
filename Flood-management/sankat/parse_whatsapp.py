import re
from typing import List, Dict


# Common WhatsApp export formats:
# 1. [05/10/26, 10:15:23 AM] Name: Message
# 2. 05/10/26, 10:15 - Name: Message
# 3. 10/05/2026, 14:30 - Name: Message
WHATSAPP_PATTERNS = [
    r"^\[?(\d{1,2}[\/\.]\d{1,2}[\/\.]\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\]?\s*(?:-\s*)?([^:]+?):\s*(.+)$",
    r"^(\d{1,2}\/\d{1,2}\/\d{2,4},\s*\d{1,2}:\d{2}\s*-\s*)([^:]+?):\s*(.+)$"
]


def parse_whatsapp_text(raw_content: str) -> List[Dict[str, str]]:
    """
    Parses a raw WhatsApp chat export into individual message dictionaries.
    Handles multi-line messages and various timestamp conventions.
    """
    lines = raw_content.splitlines()
    messages: List[Dict[str, str]] = []
    current_msg: Dict[str, str] = None

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        matched = False
        for pattern in WHATSAPP_PATTERNS:
            match = re.match(pattern, line_clean)
            if match:
                if current_msg:
                    messages.append(current_msg)
                current_msg = {
                    "timestamp": match.group(1).strip(),
                    "sender": match.group(2).strip(),
                    "text": match.group(3).strip()
                }
                matched = True
                break

        if not matched:
            # Multi-line message continuation or simple line-by-line format
            if current_msg:
                current_msg["text"] += " " + line_clean
            else:
                # Standalone emergency forward without standard WhatsApp header
                messages.append({
                    "timestamp": "Live Forward",
                    "sender": "Volunteer",
                    "text": line_clean
                })

    if current_msg:
        messages.append(current_msg)

    return messages
