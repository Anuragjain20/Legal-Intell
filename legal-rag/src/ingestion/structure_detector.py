"""Lightweight structure detection for legal documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.ingestion.models import DocumentPage
from src.ingestion.structure_patterns import (
    DetectedStructure,
    accept_numbered_section,
    collect_signals,
    is_allcaps_heading,
    is_heading_like,
    is_noise_line,
    match_line,
)

_SECTION_PARENT_RE = re.compile(r"^\d+[A-Za-z]?(?:\.\d+)*(?:\([a-z]+\))*$")

_HEADING_TYPES = {
    "chapter",
    "part",
    "article",
    "rule",
    "regulation",
    "schedule",
    "annexure",
    "heading",
    "judgment_heading",
    "clause",
}


@dataclass(frozen=True)
class DetectedParagraph:
    text: str
    page_number: int
    end_page_number: int
    section: str | None
    heading: str | None
    structure: DetectedStructure | None = None


def _compose_identifier(parent: str | None, child: str) -> str:
    """Compose a hierarchical section identifier.

    Composes section identifiers hierarchically:
    - "2" + "(d)" → "2(d)"
    - "2(d)" + "(i)" → "2(d)(i)"

    But does NOT combine siblings:
    - "2(a)" + "(d)" → "2(d)" (not "2(a)(d)")
    - "2(a)(i)" + "(ii)" → "2(a)(ii)" (not "2(a)(i)(ii)")
    """
    if not parent or parent.startswith("FRONTMATTER:"):
        return child

    if not child.startswith("("):
        # Child is not a subsection/clause marker, don't compose
        return child

    # Extract the base section number from parent, even if parent has subsections
    # e.g., from "2(a)" extract "2", from "2(d)(i)" extract "2"
    match = re.match(r"^(\d+[A-Za-z]?)", parent)
    if match:
        base_section = match.group(1)
        # Compose: "2" + "(d)" → "2(d)"
        return f"{base_section}{child}"

    return child


def _is_definition_or_child(detected: DetectedStructure) -> bool:
    if detected.type in {"subsection", "nested_clause"}:
        return True
    return detected.type == "section" and bool(detected.identifier) and "(" in detected.identifier


class StructureDetector:
    def detect(self, pages: list[DocumentPage]) -> list[DetectedParagraph]:
        all_lines = [raw.strip() for page in pages for raw in page.text.splitlines()]
        signals = collect_signals(all_lines)

        results: list[DetectedParagraph] = []
        current_heading: str | None = None
        current_section: str | None = None
        current_frontmatter_type: str | None = None
        current_structure: DetectedStructure | None = None
        current_heading_is_clause: bool = False
        last_line_was_heading = False

        buffer_lines: list[str] = []
        buffer_start_page: int | None = None
        buffer_end_page: int | None = None

        def flush() -> None:
            nonlocal buffer_lines, buffer_start_page, buffer_end_page
            text = "\n".join(buffer_lines).strip()
            if text and buffer_start_page is not None:
                section_tag = current_section
                if current_frontmatter_type:
                    section_tag = f"FRONTMATTER:{current_frontmatter_type}"

                results.append(
                    DetectedParagraph(
                        text=text,
                        page_number=buffer_start_page,
                        end_page_number=buffer_end_page or buffer_start_page,
                        section=section_tag,
                        heading=current_heading,
                        structure=current_structure,
                    )
                )
            buffer_lines = []
            buffer_start_page = None
            buffer_end_page = None

        def start_heading(
            text: str,
            section: str | None,
            frontmatter_type: str | None = None,
            structure: DetectedStructure | None = None,
            is_clause: bool = False,
        ) -> None:
            nonlocal current_heading, current_section, current_frontmatter_type, last_line_was_heading
            nonlocal current_structure, current_heading_is_clause
            if last_line_was_heading and current_section is not None and section is None:
                current_heading = f"{current_heading} {text}".strip()
            else:
                current_heading = text
                current_section = section
                current_frontmatter_type = frontmatter_type
                current_structure = structure
                current_heading_is_clause = is_clause
            last_line_was_heading = True

        def begin_paragraph(page_number: int, line: str) -> None:
            nonlocal buffer_start_page, buffer_end_page, last_line_was_heading
            buffer_start_page = page_number
            buffer_end_page = page_number
            buffer_lines.append(line)
            last_line_was_heading = False

        def append_body(page_number: int, line: str) -> None:
            nonlocal buffer_start_page, buffer_end_page, last_line_was_heading
            last_line_was_heading = False
            if current_frontmatter_type and not buffer_lines:
                buffer_start_page = page_number
            if buffer_start_page is None:
                buffer_start_page = page_number
            buffer_end_page = page_number
            buffer_lines.append(line)

        for page in pages:
            for raw_line in page.text.splitlines():
                line = raw_line.strip()

                if not line:
                    flush()
                    last_line_was_heading = False
                    continue

                if is_noise_line(line) and not is_allcaps_heading(line):
                    append_body(page.page_number, line)
                    continue

                detected = match_line(line)
                if detected is None:
                    append_body(page.page_number, line)
                    continue

                if _is_definition_or_child(detected):
                    flush()
                    child_id = detected.identifier or ""
                    if detected.type in {"subsection", "nested_clause"}:
                        section_id = _compose_identifier(current_section, child_id)
                        structure = DetectedStructure(
                            type="section" if detected.type == "subsection" else detected.type,
                            identifier=section_id,
                            title=detected.title,
                            level=2 if detected.type == "subsection" else detected.level,
                            confidence=detected.confidence,
                        )
                    else:
                        section_id = child_id
                        structure = detected
                    start_heading(
                        f"{section_id}. {detected.title}",
                        section_id,
                        structure=structure,
                        is_clause=True,
                    )
                    begin_paragraph(page.page_number, line)
                    continue

                if detected.type == "frontmatter":
                    flush()
                    fm_type = detected.identifier or "PREAMBLE"
                    start_heading(line, None, frontmatter_type=fm_type, structure=detected)
                    begin_paragraph(page.page_number, line)
                    continue

                if detected.type in _HEADING_TYPES:
                    flush()
                    heading_text = line if detected.title == line else detected.title
                    if detected.type in {"heading", "judgment_heading"}:
                        heading_text = detected.title
                    start_heading(heading_text, detected.identifier, structure=detected)
                    continue

                if detected.type == "section":
                    if not accept_numbered_section(detected, signals):
                        append_body(page.page_number, line)
                        continue

                    remainder = detected.title
                    is_dotted = "." in (detected.identifier or "")
                    inline_body = detected.confidence == 0.95 and not is_dotted
                    if remainder and is_heading_like(remainder):
                        flush()
                        start_heading(remainder, detected.identifier, structure=detected)
                        continue
                    if remainder and inline_body:
                        flush()
                        start_heading(remainder, detected.identifier, structure=detected)
                        begin_paragraph(page.page_number, line)
                        continue

                    flush()
                    is_top_level = bool(
                        detected.identifier
                        and "." not in detected.identifier
                        and "(" not in detected.identifier
                    )
                    if is_top_level and current_heading_is_clause:
                        current_heading = None
                        current_heading_is_clause = False
                    current_section = detected.identifier
                    current_frontmatter_type = None
                    current_structure = detected
                    begin_paragraph(page.page_number, line)
                    continue

                append_body(page.page_number, line)

        flush()
        return results
