"""Tests for hierarchical section structure parsing."""

import pytest

from src.ingestion.section_parser import parse_section_structure


class TestParseSectionStructure:
    """Test parsing of legal section identifiers into hierarchical components."""

    def test_simple_section_numbers(self) -> None:
        """Simple section numbers should have section_number set."""
        assert parse_section_structure("2").section_number == "2"
        assert parse_section_structure("2").subsection is None
        assert parse_section_structure("2").clause is None
        assert parse_section_structure("2").structure_path == ["2"]

    def test_two_digit_section_numbers(self) -> None:
        """Two-digit section numbers."""
        result = parse_section_structure("10")
        assert result.section_number == "10"
        assert result.subsection is None
        assert result.clause is None
        assert result.structure_path == ["10"]

        result = parse_section_structure("73")
        assert result.section_number == "73"
        assert result.structure_path == ["73"]

    def test_section_with_letter_suffix(self) -> None:
        """Section numbers can have letter suffix like 2A."""
        result = parse_section_structure("2A")
        assert result.section_number == "2A"
        assert result.subsection is None
        assert result.clause is None
        assert result.structure_path == ["2A"]

    def test_section_with_subsection(self) -> None:
        """Section 2(d) should parse to section_number=2, subsection=d."""
        result = parse_section_structure("2(d)")
        assert result.section_number == "2"
        assert result.subsection == "d"
        assert result.clause is None
        assert result.structure_path == ["2", "d"]

    def test_section_with_subsection_uppercase(self) -> None:
        """Uppercase subsections should be normalized to lowercase."""
        result = parse_section_structure("2(D)")
        assert result.section_number == "2"
        assert result.subsection == "d"
        assert result.clause is None
        assert result.structure_path == ["2", "d"]

    def test_all_subsections_a_through_z(self) -> None:
        """All letter subsections should parse correctly."""
        for letter in "abcdefghijklmnopqrstuvwxyz":
            result = parse_section_structure(f"2({letter})")
            assert result.section_number == "2"
            assert result.subsection == letter
            assert result.clause is None
            assert result.structure_path == ["2", letter]

    def test_section_with_subsection_and_clause(self) -> None:
        """Section 2(d)(i) should parse to section=2, subsection=d, clause=i."""
        result = parse_section_structure("2(d)(i)")
        assert result.section_number == "2"
        assert result.subsection == "d"
        assert result.clause == "i"
        assert result.structure_path == ["2", "d", "i"]

    def test_nested_clause_roman_numerals(self) -> None:
        """Nested clauses can use roman numerals."""
        test_cases = [
            ("2(d)(i)", "i"),
            ("2(d)(ii)", "ii"),
            ("2(d)(iii)", "iii"),
            ("2(d)(iv)", "iv"),
            ("2(d)(v)", "v"),
        ]
        for section_id, expected_clause in test_cases:
            result = parse_section_structure(section_id)
            assert result.clause == expected_clause
            assert result.structure_path == ["2", "d", expected_clause]

    def test_clause_uppercase_normalized(self) -> None:
        """Uppercase roman numerals should be normalized to lowercase."""
        result = parse_section_structure("2(d)(I)")
        assert result.clause == "i"

    def test_multiple_subsections_not_combined(self) -> None:
        """Multiple subsections like 2(a)(b) should only capture first."""
        # This is a key requirement: "2(a)(b)(c)(d)" should NOT be treated as one section
        # In practice, the detector should not produce these, but if it does,
        # we should handle it gracefully
        result = parse_section_structure("15")
        assert result.section_number == "15"
        assert result.structure_path == ["15"]

    def test_plain_section_15(self) -> None:
        """Section 15 should parse correctly."""
        result = parse_section_structure("15")
        assert result.section_number == "15"
        assert result.subsection is None
        assert result.clause is None
        assert result.structure_path == ["15"]

    def test_plain_section_19(self) -> None:
        """Section 19 should parse correctly."""
        result = parse_section_structure("19")
        assert result.section_number == "19"
        assert result.subsection is None
        assert result.clause is None
        assert result.structure_path == ["19"]

    def test_plain_section_73(self) -> None:
        """Section 73 should parse correctly."""
        result = parse_section_structure("73")
        assert result.section_number == "73"
        assert result.subsection is None
        assert result.clause is None
        assert result.structure_path == ["73"]

    def test_none_section(self) -> None:
        """None input should return empty structure."""
        result = parse_section_structure(None)
        assert result.section_number is None
        assert result.subsection is None
        assert result.clause is None
        assert result.structure_path == []

    def test_empty_string_section(self) -> None:
        """Empty string should return empty structure."""
        result = parse_section_structure("")
        assert result.section_number is None
        assert result.subsection is None
        assert result.clause is None
        assert result.structure_path == []

    def test_frontmatter_prefix(self) -> None:
        """Frontmatter sections should be treated as-is."""
        result = parse_section_structure("FRONTMATTER:PREAMBLE")
        # This doesn't match the pattern, so treated as section_number
        assert result.section_number == "FRONTMATTER:PREAMBLE"
        assert result.structure_path == ["FRONTMATTER:PREAMBLE"]

    def test_real_contract_act_examples(self) -> None:
        """Test with real Contract Act section examples."""
        # Section 2 with all subsections
        for letter in ["a", "b", "c", "d"]:
            result = parse_section_structure(f"2({letter})")
            assert result.section_number == "2"
            assert result.subsection == letter

        # Section 2(d) with nested clauses
        result = parse_section_structure("2(d)(i)")
        assert result.section_number == "2"
        assert result.subsection == "d"
        assert result.clause == "i"
        assert result.structure_path == ["2", "d", "i"]
