#!/usr/bin/env python3
"""
Shiva Info Parser
Extracts shiva details (address, visiting hours, conclusion) from obituary text.

Handles patterns commonly found in Toronto-area funeral home obituaries,
especially Steeles Memorial Chapel.
"""

import re


def extract_shiva_info(obituary_text):
    """
    Extract shiva details from obituary text.

    Returns a dict with:
        - shiva_address: string or None
        - shiva_hours: string or None (raw visiting hours text)
        - shiva_concludes: string or None
        - shiva_raw: the original matched substring
        - shiva_private: boolean
    """
    if not obituary_text:
        return None

    text = obituary_text

    # Check for private shiva first
    private_patterns = [
        r"(?:shiva|shiv['\u2019]ah?)\s+(?:will\s+be\s+)?(?:observed|held)\s+privately",
        r"private\s+(?:shiva|shiv['\u2019]ah?)",
        r"(?:shiva|shiv['\u2019]ah?)\s+is\s+private",
        r"no\s+(?:shiva|shiv['\u2019]ah?)",
    ]
    for pattern in private_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                'shiva_address': None,
                'shiva_hours': None,
                'shiva_concludes': None,
                'shiva_raw': match.group(0).strip(),
                'shiva_private': True,
            }

    # Find the shiva-relevant portion of text
    # Look for "Shiva visits", "Shiva will be observed", "Shiva at", etc.
    shiva_section = _extract_shiva_section(text)
    if not shiva_section:
        return None

    result = {
        'shiva_address': None,
        'shiva_hours': None,
        'shiva_concludes': None,
        'shiva_raw': shiva_section.strip(),
        'shiva_private': False,
    }

    # Extract address
    result['shiva_address'] = _extract_address(text, shiva_section)

    # Extract visiting hours
    result['shiva_hours'] = _extract_hours(shiva_section)

    # Extract conclusion
    result['shiva_concludes'] = _extract_concludes(text)

    return result


def _extract_shiva_section(text):
    """
    Extract the portion of text that contains shiva information.
    Uses a pragmatic approach: find the "Shiva" keyword and grab text
    around it, being careful not to split on periods in "p.m." or "a.m.".
    """
    # Find the position of "Shiva" keyword
    shiva_match = re.search(r"(?:shiva|shiv['\u2019]ah?)", text, re.IGNORECASE)
    if not shiva_match:
        return None

    shiva_pos = shiva_match.start()

    # Look backwards for address (up to 300 chars)
    preceding = text[max(0, shiva_pos - 300):shiva_pos]

    # Find the start of the address/shiva block - look for a sentence
    # boundary (period followed by space and uppercase) working backwards
    # But skip periods in abbreviations like Cres., Dr., St., p.m., a.m.
    block_start = shiva_pos
    # Try to find address with postal code before "Shiva"
    addr_match = re.search(
        r'(\d+[^.]*[A-Z]\d[A-Z]\s*\d[A-Z]\d)',
        preceding, re.IGNORECASE
    )
    if addr_match:
        # Start from the address
        block_start = max(0, shiva_pos - 300) + addr_match.start()

    # Look forward from "Shiva" to find the end of the shiva info block
    # End conditions: double newline, or a sentence that clearly isn't about shiva
    remaining = text[shiva_pos:]

    # Grab until we hit a clear break: next paragraph, or a sentence start
    # that doesn't relate to shiva (not containing time/day keywords)
    # Simple approach: grab up to 500 chars after "Shiva", then trim to
    # the last relevant sentence
    chunk = remaining[:500]

    # Find the end point - split on sentence boundaries but respect p.m./a.m.
    # Replace p.m./a.m. temporarily
    chunk_norm = re.sub(r'(?i)p\.m\.', 'P_M_', chunk)
    chunk_norm = re.sub(r'(?i)a\.m\.', 'A_M_', chunk_norm)

    # Find sentences - split on period followed by space+uppercase or end
    # Look for the last shiva-related sentence
    sentences = re.split(r'\.(?:\s+[A-Z]|\s*$)', chunk_norm)

    # Take the first sentence(s) that contain shiva-related content
    result_parts = []
    for i, sent in enumerate(sentences):
        restored = sent.replace('P_M_', 'p.m.').replace('A_M_', 'a.m.').strip()
        if not restored:
            continue
        result_parts.append(restored)
        # After the first sentence, only continue if the next sentence
        # has shiva-related keywords
        if i > 0 and not re.search(
            r'(?:shiva|conclude|p\.?m|a\.?m|monday|tuesday|wednesday|thursday|'
            r'friday|saturday|sunday|immediately|after)',
            restored, re.IGNORECASE
        ):
            break

    shiva_text = '. '.join(result_parts)
    if shiva_text and not shiva_text.endswith('.'):
        shiva_text += '.'

    # Prepend address if found
    full_section = text[block_start:shiva_pos].strip()
    if full_section:
        # Clean up - ensure there's a proper separator
        if not full_section.endswith('.'):
            full_section += '.'
        shiva_text = full_section + ' ' + shiva_text

    return shiva_text if shiva_text.strip() else None


def _extract_address(full_text, shiva_section):
    """
    Extract the shiva address. Canadian addresses typically contain
    a postal code pattern like M2M 1P6 or L4J 4R6.
    """
    # Look for Canadian postal code in or near the shiva section
    # Pattern: letter-digit-letter space digit-letter-digit
    # Search in the shiva section first, then look backwards in full text

    # First check within the shiva section itself
    postal_match = re.search(
        r'(\d+\s+[A-Za-z][A-Za-z\s.\']+(?:(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|'
        r'Boulevard|Blvd|Crescent|Cres|Court|Ct|Circle|Cir|Way|Lane|Ln|Place|Pl|'
        r'Terrace|Terr|Trail|Tr)[.]?)?'
        r'[,.\s]+[A-Za-z\s]+[,.\s]+'
        r'[A-Z]\d[A-Z]\s*\d[A-Z]\d)',
        shiva_section, re.IGNORECASE
    )
    if postal_match:
        return postal_match.group(1).strip()

    # Look in the broader text, searching backwards from "Shiva"
    shiva_pos = re.search(r"(?:shiva|shiv['\u2019]ah?)", full_text, re.IGNORECASE)
    if shiva_pos:
        # Search the 300 chars before "Shiva" for an address with postal code
        preceding = full_text[max(0, shiva_pos.start() - 300):shiva_pos.start()]
        addr_match = re.search(
            r'(\d+\s+[A-Za-z][A-Za-z\s.\']+(?:(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|'
            r'Boulevard|Blvd|Crescent|Cres|Court|Ct|Circle|Cir|Way|Lane|Ln|Place|Pl|'
            r'Terrace|Terr|Trail|Tr)[.]?)?'
            r'[,.\s]+[A-Za-z\s]+[,.\s]+'
            r'[A-Z]\d[A-Z]\s*\d[A-Z]\d)',
            preceding, re.IGNORECASE
        )
        if addr_match:
            return addr_match.group(1).strip()

    # Also try simpler pattern: just grab text with postal code
    postal_simple = re.search(
        r'([^.;]*[A-Z]\d[A-Z]\s*\d[A-Z]\d)',
        shiva_section, re.IGNORECASE
    )
    if postal_simple:
        addr = postal_simple.group(1).strip()
        # Clean up - remove leading conjunctions/prepositions
        addr = re.sub(r'^(?:and|at|to|from|,)\s+', '', addr, flags=re.IGNORECASE)
        return addr

    return None


def _extract_hours(shiva_section):
    """
    Extract visiting hours from the shiva section text.
    Returns the raw hours string - don't over-parse.
    """
    # Normalize whitespace for matching (newlines -> spaces)
    section = re.sub(r'\s+', ' ', shiva_section).strip()

    # Pattern: "Shiva visits [hours details]"
    patterns = [
        r"(?:shiva|shiv['\u2019]ah?)\s+visits?\s+(.+)",
        r"(?:shiva|shiv['\u2019]ah?)\s+(?:will\s+be\s+)?(?:observed|held)\s+(.+)",
        r"(?:shiva|shiv['\u2019]ah?)\s+(?:hours?|schedule)\s*:?\s*(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, section, re.IGNORECASE)
        if match:
            hours = match.group(1).strip()
            # Remove "Shiva concludes..." from end if present
            hours = re.sub(
                r"\.\s*(?:shiva|shiv['\u2019]ah?)\s+(?:will\s+)?conclude.*$",
                '', hours, flags=re.IGNORECASE
            ).strip()
            # Remove unrelated trailing text (after clear shiva content ends)
            # Cut at sentences that don't contain time/day keywords
            hours = re.sub(
                r'\.\s+(?!.*(?:p\.?m|a\.?m|\d{1,2}\s*(?:to|[-\u2013])|\bmonday\b|\btuesday\b|'
                r'\bwednesday\b|\bthursday\b|\bfriday\b|\bsaturday\b|\bsunday\b|immediately)).*$',
                '', hours, flags=re.IGNORECASE
            ).strip()
            # Remove trailing period, but not from "p.m." or "a.m."
            if hours.endswith('.') and not re.search(r'[ap]\.m\.$', hours, re.IGNORECASE):
                hours = hours[:-1].strip()
            if hours:
                return hours

    return None


def _extract_concludes(text):
    """
    Extract when shiva concludes.
    Patterns: "Shiva concludes [day]", "Shiva will conclude [day/date]"
    """
    patterns = [
        r"(?:shiva|shiv['\u2019]ah?)\s+(?:will\s+)?conclude[sd]?\s+(?:on\s+)?([^.]+)",
        r"(?:shiva|shiv['\u2019]ah?)\s+ends?\s+(?:on\s+)?([^.]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip('.')

    return None


if __name__ == '__main__':
    # Test with sample obituary texts
    test_texts = [
        "49 Tanjoe Cres., Toronto, M2M 1P6. Shiva visits Thursday immediately after the service until 7 p.m.",
        "129 Rose Green Dr., Thornhill, L4J 4R6. Shiva visits Wednesday 5 to 8 p.m., Thursday \u2013 1 to 3 p.m., and 5 to 8 p.m.; Friday \u2013 1 to 3 p.m.",
        "8 Josephine Rd., Toronto, M3H 3G4. Shiva visits Monday immediately after the service until 7:30 p.m.; Tuesday through Thursday 2 to 4 p.m., and 7 to 9 p.m. Shiva concludes Thursday evening.",
        "The family will be observing a private shiva.",
        "No shiva will be held.",
    ]

    for i, text in enumerate(test_texts, 1):
        print(f"\n--- Test {i} ---")
        print(f"Input: {text[:80]}...")
        result = extract_shiva_info(text)
        if result:
            print(f"  Address:   {result['shiva_address']}")
            print(f"  Hours:     {result['shiva_hours']}")
            print(f"  Concludes: {result['shiva_concludes']}")
            print(f"  Private:   {result['shiva_private']}")
            print(f"  Raw:       {result['shiva_raw'][:100]}")
        else:
            print("  No shiva info found")
