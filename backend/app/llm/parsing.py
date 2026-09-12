"""
Robust LLM output parsing utilities for DeCOBOL.
Conforms to docs/CONTRACTS.md v1.0.0 §12.
Owner: P2.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def clean_markdown_fences(text: str) -> str:
    """Strips outer markdown code fences (e.g. ```json ... ``` or ```java ... ```)."""
    text = text.strip()
    # Match ```optional_lang\n ... \n```
    match = re.match(r"^```[a-zA-Z0-9_\-\+]*\s*\n?(.*?)\n?```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def extract_json(text: str) -> Dict[str, Any]:
    """
    Extracts a JSON dictionary from model output.
    Handles markdown code fences, embedded JSON objects, trailing commas,
    and leading/trailing conversational text.
    Raises ValueError if no valid JSON object can be extracted.
    """
    if not text or not text.strip():
        raise ValueError("Cannot extract JSON from empty text")

    stripped = text.strip()

    # 1. Try stripping markdown fence first
    unfenced = clean_markdown_fences(stripped)
    try:
        data = json.loads(unfenced)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Look for explicit ```json ... ``` code fence inside text
    json_block = re.search(r"```(?:json)?\s*\n(.*?)\n```", stripped, re.DOTALL | re.IGNORECASE)
    if json_block:
        block_content = json_block.group(1).strip()
        try:
            data = json.loads(block_content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 3. Locate outermost balanced { ... }
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace : last_brace + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            # 4. Attempt cleaning common syntax issues: trailing commas
            cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Failed to parse valid JSON from text: {text[:200]}...")


def extract_java_code(text: str, class_name: Optional[str] = None) -> str:
    """
    Extracts raw Java code from text.
    - If text contains a JSON payload with a 'java_code' field, extracts that.
    - If text contains a ```java ... ``` block, extracts that.
    - Otherwise locates 'public class ...' or returns text stripped of fences.
    """
    if not text or not text.strip():
        return ""

    stripped = text.strip()

    # 1. Check if the output is a JSON envelope
    try:
        parsed = extract_json(stripped)
        if "java_code" in parsed and isinstance(parsed["java_code"], str):
            code = parsed["java_code"].strip()
            if code:
                return code
    except Exception:
        pass

    # 2. Look for ```java ... ``` code block
    java_block = re.search(r"```(?:java)?\s*\n(.*?)\n```", stripped, re.DOTALL | re.IGNORECASE)
    if java_block:
        return java_block.group(1).strip()

    # 3. Check for public class start
    pub_class = re.search(r"(?:package\s+[a-zA-Z0-9_\.]+;\s*)?(?:import\s+[a-zA-Z0-9_\.\*]+;\s*)*public\s+class\s+", stripped)
    if pub_class:
        return stripped[pub_class.start():].strip()

    # 4. Fallback to clean markdown fences
    return clean_markdown_fences(stripped)
