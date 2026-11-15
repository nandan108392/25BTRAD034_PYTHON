"""
CityOS Smart Complaint Intelligence Classifier
----------------------------------------------
Offline, rule- and keyword-based complaint classification engine.
Analyzes citizen complaint titles and descriptions to automatically extract:
- Category (Road, Water, Waste, Electricity, Traffic, Public Safety, Other)
- Issue Type (e.g. Pothole, Damaged Road, Water Leakage, Broken Streetlight, etc.)
- Priority (HIGH, MEDIUM, LOW)
- Detected Keywords
"""

import re

# Supported top-level categories
CATEGORIES = [
    "Road",
    "Water",
    "Waste",
    "Electricity",
    "Traffic",
    "Public Safety",
    "Other",
]

# Category keyword dictionaries with scoring weights (multi-word phrases weighted higher)
CATEGORY_KEYWORDS = {
    "Road": [
        ("road damage", 3),
        ("broken road", 3),
        ("broken pavement", 3),
        ("pothole", 2),
        ("crater", 2),
        ("pavement", 1),
        ("road", 1),
        ("asphalt", 1),
        ("curb", 1),
        ("sidewalk", 1),
    ],
    "Water": [
        ("water supply", 3),
        ("water leak", 3),
        ("water leakage", 3),
        ("pipe leak", 3),
        ("major leak", 3),
        ("burst pipe", 3),
        ("water", 1),
        ("leakage", 2),
        ("pipe", 1),
        ("flooding", 2),
        ("flood", 2),
        ("drainage", 2),
        ("drain", 1),
        ("sewage", 2),
        ("sewer", 2),
    ],
    "Waste": [
        ("garbage collection", 3),
        ("garbage dumping", 3),
        ("illegal dumping", 3),
        ("uncollected waste", 3),
        ("trash dumping", 3),
        ("garbage", 2),
        ("waste", 1),
        ("trash", 2),
        ("dumping", 2),
        ("dump", 1),
        ("litter", 2),
        ("rubbish", 2),
        ("debris", 1),
        ("overflowing bin", 3),
    ],
    "Electricity": [
        ("broken streetlight", 3),
        ("street light", 3),
        ("streetlight", 3),
        ("live wire", 3),
        ("power cut", 3),
        ("power outage", 3),
        ("blackout", 2),
        ("electrical hazard", 3),
        ("light", 1),
        ("lamp", 1),
        ("electricity", 2),
        ("electrical", 2),
        ("power", 1),
        ("pole", 1),
        ("wire", 1),
        ("spark", 2),
        ("sparking", 2),
    ],
    "Traffic": [
        ("traffic light", 3),
        ("traffic signal", 3),
        ("traffic jam", 3),
        ("signal problem", 3),
        ("signal", 2),
        ("congestion", 2),
        ("traffic", 1),
        ("junction", 2),
        ("gridlock", 2),
        ("intersection", 1),
    ],
    "Public Safety": [
        ("life threatening", 4),
        ("school danger", 3),
        ("fire hazard", 3),
        ("accident", 3),
        ("emergency", 3),
        ("danger", 2),
        ("unsafe", 2),
        ("hazard", 2),
        ("fire", 3),
        ("crash", 3),
        ("collision", 3),
        ("collapse", 3),
        ("falling", 2),
    ],
}

# Issue type detection rules per category
ISSUE_TYPE_RULES = {
    "Road": [
        (["pothole", "crater"], "Pothole"),
        (["broken road", "road damage", "pavement", "broken pavement", "asphalt", "curb"], "Damaged Road"),
    ],
    "Water": [
        (["leakage", "leak", "pipe", "burst pipe", "water leak", "water leakage"], "Water Leakage"),
        (["drainage", "drain", "sewage", "sewer", "flooding", "flood"], "Drainage"),
        (["water supply", "supply", "no water", "contamination"], "Water Supply"),
    ],
    "Waste": [
        (["dumping", "dump", "illegal dumping", "trash dumping"], "Garbage Dumping"),
        (["garbage collection", "uncollected", "uncollected waste", "trash", "litter", "garbage", "rubbish", "overflowing bin"], "Uncollected Waste"),
    ],
    "Electricity": [
        (["live wire", "electrical hazard", "wire", "spark", "sparking", "electrical"], "Electrical Hazard"),
        (["streetlight", "street light", "light", "lamp", "pole"], "Broken Streetlight"),
        (["power", "electricity", "blackout", "power outage", "power cut", "outage"], "Power Issue"),
    ],
    "Traffic": [
        (["traffic light", "traffic signal", "signal", "signal problem"], "Signal Problem"),
        (["congestion", "traffic jam", "gridlock", "traffic", "junction"], "Traffic Congestion"),
    ],
    "Public Safety": [
        (["emergency", "fire", "fire hazard", "life threatening", "collapse"], "Emergency"),
        (["accident", "crash", "collision"], "Accident"),
        (["hazard", "danger", "unsafe", "school danger", "falling"], "Hazard"),
    ],
}

# Fallback issue types if specific keyword rules don't pinpoint a sub-issue
DEFAULT_ISSUE_TYPES = {
    "Road": "Other Road Issue",
    "Water": "Other Water Issue",
    "Waste": "Other Waste Issue",
    "Electricity": "Other Electricity Issue",
    "Traffic": "Other Traffic Issue",
    "Public Safety": "Hazard",
    "Other": "General Issue",
}

# Priority keywords
HIGH_PRIORITY_KEYWORDS = [
    "accident",
    "fire",
    "fire hazard",
    "emergency",
    "danger",
    "school danger",
    "hazard",
    "electrical hazard",
    "flooding",
    "flood",
    "major leak",
    "burst pipe",
    "severe",
    "life threatening",
    "falling",
    "collapse",
    "live wire",
    "sparking",
    "critical",
    "deep crater",
]

LOW_PRIORITY_KEYWORDS = [
    "cosmetic",
    "minor",
    "suggestion",
    "general complaint",
    "aesthetic",
    "request",
    "feedback",
    "slight",
    "painting",
    "cleaning",
]

MEDIUM_PRIORITY_KEYWORDS = [
    "broken",
    "damaged",
    "leakage",
    "leak",
    "pothole",
    "crater",
    "streetlight",
    "street light",
    "garbage",
    "waste",
    "trash",
    "dumping",
    "litter",
    "drainage",
    "drain",
    "sewage",
    "traffic signal",
    "signal",
    "power",
    "electricity",
    "pole",
    "congestion",
    "traffic",
    "pipe",
    "road",
]


def classify_complaint(description, title=None):
    """
    Classifies a municipal complaint based on its description and optional title.

    Parameters:
        description (str): The detailed text of the complaint.
        title (str, optional): The title/subject line of the complaint.

    Returns:
        dict: {
            "category": str ("Road", "Water", "Waste", "Electricity", "Traffic", "Public Safety", "Other"),
            "issue_type": str (e.g. "Pothole", "Water Leakage", "Broken Streetlight", "General Issue"),
            "priority": str ("HIGH", "MEDIUM", "LOW"),
            "keywords": list[str] (list of unique matched keywords)
        }
    """
    # Combine title and description for comprehensive analysis
    full_text = f"{title or ''} {description or ''}".strip().lower()
    if not full_text:
        return {
            "category": "Other",
            "issue_type": "General Issue",
            "priority": "MEDIUM",
            "keywords": [],
        }

    detected_keywords = []
    category_scores = {cat: 0 for cat in CATEGORY_KEYWORDS}

    # 1. Calculate category scores based on keyword matching
    for cat, kw_list in CATEGORY_KEYWORDS.items():
        for kw, weight in kw_list:
            # Word boundary or phrase search
            pattern = r"\b" + re.escape(kw) + r"\b"
            matches = re.findall(pattern, full_text)
            if matches:
                category_scores[cat] += weight * len(matches)
                if kw not in detected_keywords:
                    detected_keywords.append(kw)

    # 2. Determine best category
    best_category = "Other"
    max_score = 0
    for cat, score in category_scores.items():
        if score > max_score:
            max_score = score
            best_category = cat

    # 3. Determine Issue Type within the determined category
    if best_category == "Other" or max_score == 0:
        best_category = "Other"
        issue_type = "General Issue"
    else:
        issue_type = DEFAULT_ISSUE_TYPES.get(best_category, "General Issue")
        # Check specific issue type matching rules
        rules = ISSUE_TYPE_RULES.get(best_category, [])
        matched = False
        for kw_group, itype in rules:
            for kw in kw_group:
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, full_text):
                    issue_type = itype
                    if kw not in detected_keywords:
                        detected_keywords.append(kw)
                    matched = True
                    break
            if matched:
                break

    # 4. Determine Priority (HIGH, MEDIUM, LOW)
    priority = "MEDIUM"  # Default priority

    has_high = False
    for kw in HIGH_PRIORITY_KEYWORDS:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, full_text):
            has_high = True
            if kw not in detected_keywords:
                detected_keywords.append(kw)
            break

    if has_high:
        priority = "HIGH"
    else:
        has_low = False
        for kw in LOW_PRIORITY_KEYWORDS:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, full_text):
                has_low = True
                if kw not in detected_keywords:
                    detected_keywords.append(kw)
                break

        has_medium = False
        for kw in MEDIUM_PRIORITY_KEYWORDS:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, full_text):
                has_medium = True
                if kw not in detected_keywords:
                    detected_keywords.append(kw)
                break

        if has_low and not has_medium:
            priority = "LOW"
        else:
            priority = "MEDIUM"

    return {
        "category": best_category,
        "issue_type": issue_type,
        "priority": priority,
        "keywords": detected_keywords,
    }
