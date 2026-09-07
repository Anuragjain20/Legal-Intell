"""Parse hierarchical legal section structures."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedSection:
    """Hierarchical representation of a legal section."""

    section_number: str | None
    subsection: str | None
    clause: str | None
    structure_path: list[str]


def parse_section_structure(section_id: str | None) -> ParsedSection:
    """
    Parse a section identifier into hierarchical components.

    Examples:
        "2" → section_number="2", subsection=None, clause=None, path=["2"]
        "2(d)" → section_number="2", subsection="d", clause=None, path=["2", "d"]
        "2(d)(i)" → section_number="2", subsection="d", clause="i", path=["2", "d", "i"]
        "10" → section_number="10", subsection=None, clause=None, path=["10"]
        None → all None, path=[]
    """

    if not section_id:
        return ParsedSection(section_number=None, subsection=None, clause=None, structure_path=[])

    # Pattern: captures section_number, optional first level parens, optional second level parens
    # Examples: "2", "2(d)", "2(d)(i)", "10", "73"
    pattern = r"^(\d+[A-Za-z]?)(?:\(([a-z])\))?(?:\(([ivxlcdm]+)\))?$"
    match = re.match(pattern, section_id, re.IGNORECASE)

    if not match:
        # If it doesn't match our pattern, treat the whole thing as section_number
        return ParsedSection(
            section_number=section_id,
            subsection=None,
            clause=None,
            structure_path=[section_id],
        )

    section_num, subsec, clause = match.groups()
    path = [section_num]

    if subsec:
        subsec = subsec.lower()
        path.append(subsec)

    if clause:
        clause = clause.lower()
        path.append(clause)

    return ParsedSection(
        section_number=section_num,
        subsection=subsec,
        clause=clause,
        structure_path=path,
    )
