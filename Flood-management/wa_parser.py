import re
from datetime import datetime

def parse_export(text: str) -> list[dict]:
    text = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', text)
    text = re.sub(r'[\u202f\u00a0]', ' ', text)
    lines = text.splitlines()
    
    header_pattern = re.compile(
        r'^\[?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*,\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\s*\]?\s*(?:-\s*)?(.*)$'
    )
    
    has_header = any(header_pattern.match(line) for line in lines)
    if not has_header:
        messages = []
        idx = 1
        for line in lines:
            body = line.strip()
            if body:
                messages.append({"report_id": f"r{idx}", "sender": None, "ts": None, "text": body})
                idx += 1
        return messages

    raw_messages = []
    current_msg = None
    
    for line in lines:
        match = header_pattern.match(line)
        if match:
            date_str, time_str, rest = match.groups()
            
            if ": " not in rest:
                current_msg = None
                continue
                
            sender, body = rest.split(": ", 1)
            
            ts = None
            time_clean = time_str.strip().upper()
            time_clean = re.sub(r'([AP]M)$', r' \1', time_clean).replace('  ', ' ')
            
            for fmt in ("%d/%m/%y, %I:%M %p", "%d/%m/%Y, %I:%M %p", 
                        "%d/%m/%y, %I:%M:%S %p", "%d/%m/%Y, %I:%M:%S %p",
                        "%d/%m/%y, %H:%M", "%d/%m/%Y, %H:%M",
                        "%d/%m/%y, %H:%M:%S", "%d/%m/%Y, %H:%M:%S"):
                try:
                    dt = datetime.strptime(f"{date_str}, {time_clean}", fmt)
                    if dt.year < 100:
                        dt = dt.replace(year=dt.year + 2000)
                    ts = dt.strftime("%Y-%m-%dT%H:%M")
                    break
                except ValueError:
                    continue
                    
            current_msg = {"sender": sender.strip(), "ts": ts, "text": body.strip()}
            raw_messages.append(current_msg)
        else:
            if current_msg is not None:
                body = line.strip()
                if body:
                    if current_msg["text"]:
                        current_msg["text"] += " " + body
                    else:
                        current_msg["text"] = body

    skip_exact = {
        "<media omitted>", "image omitted", "video omitted", 
        "sticker omitted", "this message was deleted", "you deleted this message"
    }
    
    final_messages = []
    idx = 1
    for msg in raw_messages:
        body_lower = msg["text"].lower()
        if not msg["text"].strip():
            continue
        if body_lower in skip_exact:
            continue
        if "(file attached)" in body_lower:
            continue
            
        final_messages.append({
            "report_id": f"r{idx}",
            "sender": msg["sender"],
            "ts": msg["ts"],
            "text": msg["text"]
        })
        idx += 1
        
    return final_messages

def find_phones(text: str) -> list[str]:
    core = r'[6-9](?:\d{9}|[\s-]\d{9}|\d[\s-]\d{8}|\d{2}[\s-]\d{7}|\d{3}[\s-]\d{6}|\d{4}[\s-]\d{5}|\d{5}[\s-]\d{4}|\d{6}[\s-]\d{3}|\d{7}[\s-]\d{2}|\d{8}[\s-]\d)'
    prefix = r'(?:\+91[\s-]?|91[\s-]?|0[\s-]?)?'
    pattern = rf'(?<!\d){prefix}{core}(?!\d)'
    
    matches = re.finditer(pattern, text)
    phones = []
    seen = set()
    for m in matches:
        raw = m.group(0)
        digits = re.sub(r'\D', '', raw)
        
        if len(digits) == 10:
            norm = "+91" + digits
        elif len(digits) == 11 and digits.startswith('0'):
            norm = "+91" + digits[1:]
        elif len(digits) == 12 and digits.startswith('91'):
            norm = "+" + digits
        else:
            if raw.startswith('+91'):
                norm = "+91" + digits[-10:]
            else:
                continue
                
        if norm not in seen:
            seen.add(norm)
            phones.append(norm)
            
    return phones

def mask_phones(text: str) -> str:
    core = r'[6-9](?:\d{9}|[\s-]\d{9}|\d[\s-]\d{8}|\d{2}[\s-]\d{7}|\d{3}[\s-]\d{6}|\d{4}[\s-]\d{5}|\d{5}[\s-]\d{4}|\d{6}[\s-]\d{3}|\d{7}[\s-]\d{2}|\d{8}[\s-]\d)'
    prefix = r'(?:\+91[\s-]?|91[\s-]?|0[\s-]?)?'
    pattern = rf'(?<!\d){prefix}{core}(?!\d)'
    return re.sub(pattern, "[PHONE]", text)
