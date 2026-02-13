"""Knowledge-base retrieval for ingredient facts.

Goals:
- Match detected ingredient strings to a KB entry via:
  1) exact normalized match
  2) synonym match
  3) conservative token match (whole-word)
  4) optional fuzzy match (difflib / rapidfuzz if installed)
- Produce stable citation IDs so caching and chat citations are deterministic.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..schemas import EvidenceSnippet

# Expected KB schema:
# [
#   {
#     "canonicalName": "citric acid",
#     "synonyms": ["e330"],
#     "tags": ["acid","additive"],
#     "description": "...",
#     "considerations": [...],
#     "citations": [{"title": "...", "url": "..."}]
#   },
#   ...
# ]

_KB_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "kb" / "ingredients_kb.json"

_kb_cache: Optional[List[Dict]] = None
_name_index: Optional[Dict[str, Dict]] = None   # normalized name/synonym -> entry
_all_index_keys: Optional[List[str]] = None     # for fuzzy matching


_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]+")
_MULTI_SPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase, remove punctuation, normalize separators, collapse spaces."""
    t = text.lower().strip().replace("-", " ").replace("_", " ")
    t = _NORMALIZE_RE.sub(" ", t)
    t = _MULTI_SPACE_RE.sub(" ", t).strip()
    return t


def _slug(text: str) -> str:
    """Stable slug for citation IDs."""
    t = _normalize(text)
    t = t.replace(" ", "-")
    return t[:80] if len(t) > 80 else t


def _load_kb() -> List[Dict]:
    global _kb_cache, _name_index, _all_index_keys
    if _kb_cache is None:
        with open(_KB_PATH, "r", encoding="utf-8") as f:
            _kb_cache = json.load(f)

        # Build index for canonical + synonyms
        idx: Dict[str, Dict] = {}
        for entry in _kb_cache:
            canon = entry.get("canonicalName", "")
            if not canon:
                continue
            idx[_normalize(canon)] = entry
            for syn in entry.get("synonyms", []) or []:
                if syn:
                    idx[_normalize(syn)] = entry

        _name_index = idx
        _all_index_keys = sorted(idx.keys())

    assert _kb_cache is not None
    assert _name_index is not None
    assert _all_index_keys is not None
    return _kb_cache


def _entry_to_snippets(entry: Dict) -> List[EvidenceSnippet]:
    """Create EvidenceSnippet objects with stable IDs for each citation in an entry."""
    snippets: List[EvidenceSnippet] = []
    citations = entry.get("citations", []) or []
    canon = entry.get("canonicalName", "unknown")
    slug = _slug(canon)

    # Keep snippet short and useful (description + at most 1 consideration)
    desc = (entry.get("description") or "").strip()
    cons = entry.get("considerations") or []
    if cons:
        desc2 = desc + (" " if desc else "") + f"Note: {cons[0]}"
    else:
        desc2 = desc

    for i, cit in enumerate(citations):
        title = cit.get("title", "Source")
        url = cit.get("url", "")
        cid = f"kb:{slug}:cit-{i+1:02d}"
        snippets.append(
            EvidenceSnippet(
                citation_id=cid,
                title=title,
                snippet=desc2,
                source_url=url,
            )
        )
    return snippets


def _token_match(query_norm: str, candidate_norm: str) -> bool:
    """Conservative token match:
    - Requires whole token overlap (no substrings)
    - Only used when either side has >=2 tokens (to avoid matching 'oil' everywhere)
    """
    q_tokens = query_norm.split()
    c_tokens = candidate_norm.split()
    if len(q_tokens) < 2 and len(c_tokens) < 2:
        return False
    return set(c_tokens).issubset(set(q_tokens)) or set(q_tokens).issubset(set(c_tokens))


def _fuzzy_lookup(query_norm: str) -> Optional[Dict]:
    """Optional fuzzy match for OCR noise. Uses rapidfuzz if available, else difflib."""
    # Guard: fuzzy matching can create false positives for very short strings
    if len(query_norm) < 5:
        return None

    kb = _load_kb()
    assert _name_index is not None
    assert _all_index_keys is not None

    # Try rapidfuzz first
    try:
        from rapidfuzz import process  # type: ignore
        match = process.extractOne(query_norm, _all_index_keys, score_cutoff=92)
        if match:
            key, score, _ = match
            return _name_index.get(key)
    except Exception:
        pass

    # Fallback to difflib (standard library)
    import difflib

    close = difflib.get_close_matches(query_norm, _all_index_keys, n=1, cutoff=0.92)
    if close:
        return _name_index.get(close[0])
    return None


def lookup_ingredients(canonical_names: List[str]) -> Tuple[List[EvidenceSnippet], Dict[str, Dict]]:
    """Return (evidence snippets, matched_entries) where:
    - matched_entries maps *original query name* -> KB entry dict
    - snippets contains citation-backed evidence for all matched entries
    """
    _load_kb()
    assert _name_index is not None

    snippets: List[EvidenceSnippet] = []
    matched_entries: Dict[str, Dict] = {}

    for orig in canonical_names:
        if not orig:
            continue
        q_norm = _normalize(orig)

        entry = _name_index.get(q_norm)
        if entry is None:
            # token match against index keys (conservative)
            for key in _name_index.keys():
                if _token_match(q_norm, key):
                    entry = _name_index[key]
                    break

        if entry is None:
            entry = _fuzzy_lookup(q_norm)

        if entry is not None:
            matched_entries[orig] = entry
            snippets.extend(_entry_to_snippets(entry))

    # De-duplicate snippets by citation_id
    uniq: Dict[str, EvidenceSnippet] = {s.citation_id: s for s in snippets}
    return list(uniq.values()), matched_entries


def get_kb_tags(ingredient_name: str) -> List[str]:
    """Return tags for a given ingredient from the KB, if matched."""
    _load_kb()
    assert _name_index is not None

    q_norm = _normalize(ingredient_name)
    entry = _name_index.get(q_norm) or _fuzzy_lookup(q_norm)
    if entry is None:
        return []
    return entry.get("tags", []) or []
