"""Unit tests for the DTC (Diagnostic Trouble Code) database.

Tests lookup functions, data integrity, severity filtering, and
case-insensitivity of the built-in DTC code reference.
"""

from __future__ import annotations

import pytest

from kuksa_mcp.dtc_database import (
    DTC_DATABASE,
    DTCInfo,
    Severity,
    get_all_dtc_codes,
    get_dtc_by_severity,
    get_dtc_description,
    get_full_database,
)


# ===================================================================
# DTCInfo Pydantic model
# ===================================================================
class TestDTCInfo:
    """Tests for the ``DTCInfo`` Pydantic model."""

    def test_creation(self) -> None:
        """All fields populate correctly."""
        info = DTCInfo(
            code="P0301",
            description="Cylinder 1 misfire detected",
            severity="high",
            system="Engine",
            recommended_action="Inspect spark plug",
        )
        assert info.code == "P0301"
        assert info.severity == "high"

    def test_severity_literal_validation(self) -> None:
        """Only valid severity literals are accepted."""
        for valid in ("low", "medium", "high", "critical"):
            info = DTCInfo(
                code="T001",
                description="test",
                severity=valid,
                system="Test",
                recommended_action="test",
            )
            assert info.severity == valid

    def test_invalid_severity_rejected(self) -> None:
        """Invalid severity literal raises a validation error."""
        with pytest.raises(Exception):
            DTCInfo(
                code="T001",
                description="test",
                severity="extreme",  # type: ignore[arg-type]
                system="Test",
                recommended_action="test",
            )

    def test_model_dump(self) -> None:
        """model_dump returns a serialisable dict with all fields."""
        info = DTCInfo(
            code="P0301",
            description="misfire",
            severity="high",
            system="Engine",
            recommended_action="fix",
        )
        dumped = info.model_dump()
        assert isinstance(dumped, dict)
        assert set(dumped.keys()) == {
            "code",
            "description",
            "severity",
            "system",
            "recommended_action",
        }


# ===================================================================
# get_dtc_description
# ===================================================================
class TestGetDtcDescription:
    """Tests for ``get_dtc_description``."""

    def test_known_code_returns_info(self) -> None:
        """Known DTC code returns a DTCInfo instance."""
        result = get_dtc_description("P0301")
        assert result is not None
        assert isinstance(result, DTCInfo)
        assert result.code == "P0301"

    def test_unknown_code_returns_none(self) -> None:
        """Unknown DTC code returns None."""
        result = get_dtc_description("Z9999")
        assert result is None

    def test_case_insensitive_lowercase(self) -> None:
        """Lowercase input is normalised to uppercase lookup."""
        result = get_dtc_description("p0301")
        assert result is not None
        assert result.code == "P0301"

    def test_case_insensitive_mixed(self) -> None:
        """Mixed-case input is normalised."""
        result = get_dtc_description("p0420")
        assert result is not None
        assert result.code == "P0420"

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        result = get_dtc_description("")
        assert result is None

    def test_returns_correct_description(self) -> None:
        """Returned DTCInfo has a meaningful description."""
        result = get_dtc_description("P0301")
        assert result is not None
        assert "misfire" in result.description.lower()

    def test_body_code_lookup(self) -> None:
        """Body (B-prefix) code is found."""
        result = get_dtc_description("B0001")
        assert result is not None
        assert result.system == "Restraint"

    def test_chassis_code_lookup(self) -> None:
        """Chassis (C-prefix) code is found."""
        result = get_dtc_description("C0035")
        assert result is not None
        assert "Chassis" in result.system

    def test_network_code_lookup(self) -> None:
        """Network (U-prefix) code is found."""
        result = get_dtc_description("U0001")
        assert result is not None
        assert result.system == "Network"


# ===================================================================
# get_all_dtc_codes
# ===================================================================
class TestGetAllDtcCodes:
    """Tests for ``get_all_dtc_codes``."""

    def test_returns_sorted_list(self) -> None:
        """Returned list is sorted alphabetically."""
        codes = get_all_dtc_codes()
        assert codes == sorted(codes)

    def test_returns_list_of_strings(self) -> None:
        """Every element is a string."""
        codes = get_all_dtc_codes()
        assert all(isinstance(c, str) for c in codes)

    def test_contains_known_codes(self) -> None:
        """Known codes are present in the result."""
        codes = get_all_dtc_codes()
        assert "P0301" in codes
        assert "P0420" in codes
        assert "B0001" in codes
        assert "U0001" in codes

    def test_count_matches_database(self) -> None:
        """Number of codes matches the database size."""
        codes = get_all_dtc_codes()
        assert len(codes) == len(DTC_DATABASE)


# ===================================================================
# get_dtc_by_severity
# ===================================================================
class TestGetDtcBySeverity:
    """Tests for ``get_dtc_by_severity``."""

    def test_filter_high(self) -> None:
        """Filtering by 'high' returns only high-severity entries."""
        results = get_dtc_by_severity("high")
        assert len(results) > 0
        assert all(r.severity == "high" for r in results)

    def test_filter_critical(self) -> None:
        """Filtering by 'critical' returns only critical entries."""
        results = get_dtc_by_severity("critical")
        assert len(results) > 0
        assert all(r.severity == "critical" for r in results)

    def test_filter_low(self) -> None:
        """Filtering by 'low' returns only low-severity entries."""
        results = get_dtc_by_severity("low")
        assert len(results) > 0
        assert all(r.severity == "low" for r in results)

    def test_filter_medium(self) -> None:
        """Filtering by 'medium' returns only medium-severity entries."""
        results = get_dtc_by_severity("medium")
        assert len(results) > 0
        assert all(r.severity == "medium" for r in results)

    def test_returns_dtc_info_instances(self) -> None:
        """All returned items are DTCInfo instances."""
        results = get_dtc_by_severity("high")
        assert all(isinstance(r, DTCInfo) for r in results)

    def test_all_severities_cover_database(self) -> None:
        """Combining all severity filters covers the entire database."""
        total = 0
        for severity in ("low", "medium", "high", "critical"):
            total += len(get_dtc_by_severity(severity))
        assert total == len(DTC_DATABASE)


# ===================================================================
# get_full_database
# ===================================================================
class TestGetFullDatabase:
    """Tests for ``get_full_database``."""

    def test_returns_dict(self) -> None:
        """Returns a dict mapping code strings to DTCInfo."""
        db = get_full_database()
        assert isinstance(db, dict)

    def test_values_are_dtc_info(self) -> None:
        """Every value is a DTCInfo instance."""
        db = get_full_database()
        assert all(isinstance(v, DTCInfo) for v in db.values())

    def test_keys_match_codes(self) -> None:
        """Dict keys match the code field of their values."""
        db = get_full_database()
        for code, info in db.items():
            assert code == info.code

    def test_returns_same_reference_as_global(self) -> None:
        """Returns the module-level DTC_DATABASE reference."""
        db = get_full_database()
        assert db is DTC_DATABASE


# ===================================================================
# DTC_DATABASE data integrity
# ===================================================================
class TestDtcDatabaseIntegrity:
    """Data quality checks for the built-in DTC database."""

    def test_minimum_entry_count(self) -> None:
        """Database contains at least 30 entries."""
        assert len(DTC_DATABASE) >= 30

    def test_all_families_represented(self) -> None:
        """All four DTC families (P, B, C, U) have at least one entry."""
        prefixes = {code[0] for code in DTC_DATABASE}
        assert {"P", "B", "C", "U"}.issubset(prefixes)

    def test_all_severities_used(self) -> None:
        """All four severity levels are represented in the database."""
        severities = {info.severity for info in DTC_DATABASE.values()}
        assert severities == {"low", "medium", "high", "critical"}

    def test_no_empty_descriptions(self) -> None:
        """Every entry has a non-empty description."""
        for code, info in DTC_DATABASE.items():
            assert info.description.strip(), f"{code} has empty description"

    def test_no_empty_systems(self) -> None:
        """Every entry has a non-empty system field."""
        for code, info in DTC_DATABASE.items():
            assert info.system.strip(), f"{code} has empty system"

    def test_no_empty_recommended_actions(self) -> None:
        """Every entry has a non-empty recommended action."""
        for code, info in DTC_DATABASE.items():
            assert info.recommended_action.strip(), (
                f"{code} has empty recommended_action"
            )

    def test_codes_are_valid_format(self) -> None:
        """Every code follows the OBD-II format: one letter + four digits."""
        import re

        pattern = re.compile(r"^[PBCU]\d{4}$")
        for code in DTC_DATABASE:
            assert pattern.match(code), f"Invalid DTC code format: {code}"

    def test_keys_match_info_codes(self) -> None:
        """Dict keys match the code field inside each DTCInfo."""
        for key, info in DTC_DATABASE.items():
            assert key == info.code, (
                f"Key '{key}' does not match info.code '{info.code}'"
            )
