import re
import json
from typing import Tuple, Optional, Dict, Any

def strip_chinese(text: str) -> str:
    """Removes any trailing hallucination starting from a Chinese character."""
    match = re.search(r'[\u4e00-\u9fff]', text)
    if match:
        return text[:match.start()].strip()
    return text

def parse_thought(text: str) -> Tuple[str, str]:
    """
    Parses the raw LLM output, extracting the <thought> tag contents.
    Returns (raw_thoughts, final_output).
    If no tag is found, returns ('', text).
    """
    text = strip_chinese(text)
    pattern = re.compile(r"<thought>(.*?)</thought>", re.DOTALL)
    
    match = pattern.search(text)
    if match:
        raw_thoughts = match.group(1).strip()
        final_output = pattern.sub("", text).strip()
        
        # Fallback: if the model wrote its entire response inside the thought tag and didn't write a public response
        if not final_output:
            final_output = raw_thoughts
            
        return raw_thoughts, final_output.lower()
    
    pattern_unclosed = re.compile(r"<thought>(.*)", re.DOTALL)
    match_unclosed = pattern_unclosed.search(text)
    if match_unclosed:
        raw_thoughts = match_unclosed.group(1).strip()
        # Fallback: if the model forgot to close the tag, assume the entire output is meant for the user.
        return raw_thoughts, raw_thoughts.lower()

    return "", text.strip().lower()

def parse_init_done(text: str) -> Optional[Dict[str, Any]]:
    """
    Looks for the <init_done>{...}</init_done> tag in the text.
    If found, attempts to parse the inner JSON and returns it.
    Returns None if not found or invalid JSON.
    """
    pattern = re.compile(r"<init_done>(.*?)</init_done>", re.DOTALL)
    match = pattern.search(text)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            return data
        except json.JSONDecodeError:
            return None
    return None
