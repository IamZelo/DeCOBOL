"""Tests for the PIC -> Java type mapper and naming helpers.

Owner: P3 (the module under test). P5 owns the harness (conftest, fixtures)
and the integration suites (test_pipeline, test_api).

These double as executable documentation of MAPPING_REFERENCE.md: if a rule
changes there, a test here must change with it.
"""

import pytest

from app.tools.type_mapper import (
    java_class_name, java_method_name, java_name, map_pic, unique_java_name,
)


# --------------------------------------------------------------------------
# The four rules from README §1 — the semantic bugs we exist to catch
# --------------------------------------------------------------------------

def test_money_pic_maps_to_bigdecimal_with_scale():
    """PIC S9(7)V99 is money. double loses cents; BigDecimal does not."""
    m = map_pic("S9(7)V99")
    assert m.java_type == "BigDecimal"
    assert m.scale == 2
    assert m.digits == 9
    assert m.signed is True
    assert "RoundingMode.HALF_UP" in m.java_initializer
    assert "java.math.BigDecimal" in m.required_imports
    assert "java.math.RoundingMode" in m.required_imports


def test_alphanumeric_carries_its_declared_width():
    """PIC X(10) must keep its width, or MOVE padding cannot be checked."""
    m = map_pic("X(10)")
    assert (m.java_type, m.length, m.category) == ("String", 10, "alphanumeric")


def test_short_numeric_keeps_digit_count_for_truncation_checks():
    """PIC 9(3) holds 3 digits; MOVE 12345 must truncate to 345."""
    m = map_pic("9(3)")
    assert (m.java_type, m.digits, m.scale) == ("int", 3, 0)


def test_comp3_money_matches_contract_example():
    """The worked example in CONTRACTS.md §3.3 must hold exactly."""
    m = map_pic("S9(15)V9(2)", "COMP-3")
    assert m.java_type == "BigDecimal"
    assert (m.digits, m.scale, m.signed) == (17, 2, True)
    assert m.length == 9           # ceil((17 + 1) / 2) packed bytes
    assert m.java_initializer == (
        "BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP)"
    )


# --------------------------------------------------------------------------
# Integer width selection
# --------------------------------------------------------------------------

@pytest.mark.parametrize("pic,expected", [
    ("9",      "int"),
    ("9(9)",   "int"),
    ("9(10)",  "long"),
    ("9(18)",  "long"),
    ("9(19)",  "BigDecimal"),   # exceeds long
    ("9(31)",  "BigDecimal"),
])
def test_integer_width_selection(pic, expected):
    assert map_pic(pic).java_type == expected


def test_oversized_integer_explains_itself():
    assert any("exceeds long" in n for n in map_pic("9(19)").notes)


# --------------------------------------------------------------------------
# USAGE handling and storage size
# --------------------------------------------------------------------------

@pytest.mark.parametrize("pic,usage,length", [
    ("9(4)",  "COMP",    2),
    ("9(9)",  "COMP",    4),
    ("9(18)", "COMP",    8),
    ("9(5)",  "COMP-3",  3),    # ceil(6/2)
    ("9(4)",  "COMP-3",  3),    # ceil(5/2)
    ("9(5)",  "DISPLAY", 5),
])
def test_storage_length_by_usage(pic, usage, length):
    assert map_pic(pic, usage).length == length


@pytest.mark.parametrize("alias,normalised", [
    ("COMPUTATIONAL-3", "COMP-3"),
    ("PACKED-DECIMAL",  "COMP-3"),
    ("BINARY",          "COMP"),
    ("COMPUTATIONAL",   "COMP"),
    ("comp-3",          "COMP-3"),
    ("",                "DISPLAY"),
    (None,              "DISPLAY"),
])
def test_usage_aliases(alias, normalised):
    assert map_pic("9(5)", alias).usage == normalised


def test_unknown_usage_degrades_to_display_with_a_note():
    m = map_pic("9(5)", "COMP-9")
    assert m.usage == "DISPLAY"
    assert any("unrecognised USAGE" in n for n in m.notes)


def test_binary_float_usages_avoid_double():
    """COMP-1/COMP-2 are binary floats. Mapping them to double would
    reintroduce the drift the project exists to prevent."""
    for usage, size in (("COMP-1", 4), ("COMP-2", 8)):
        m = map_pic("9(5)V99", usage)
        assert m.java_type == "BigDecimal"
        assert m.length == size
        assert any("precision drift" in n for n in m.notes)


# --------------------------------------------------------------------------
# Edited pictures are display formats, not numbers
# --------------------------------------------------------------------------

@pytest.mark.parametrize("pic,length,scale", [
    ("ZZ,ZZ9.99",   9, 2),
    ("----9.99",    8, 2),
    ("ZZZ9",        4, 0),
    ("$$$,$$9.99", 10, 2),
])
def test_edited_pictures_map_to_string_with_true_width(pic, length, scale):
    m = map_pic(pic)
    assert m.category == "numeric_edited"
    assert m.java_type == "String"
    assert m.length == length          # storage positions, no double counting
    assert m.scale == scale            # '.' is a real decimal point here


# --------------------------------------------------------------------------
# Alphabetic, group items, condition names
# --------------------------------------------------------------------------

def test_alphabetic():
    m = map_pic("A(5)")
    assert (m.category, m.java_type, m.length) == ("alphabetic", "String", 5)


def test_single_character_initialiser_is_not_a_repeat_call():
    assert map_pic("X").java_initializer == '" "'


def test_group_item_has_no_picture():
    m = map_pic(None)
    assert m.java_type == "Object"
    assert m.java_initializer is None
    assert m.digits == 0


def test_level_88_is_a_boolean():
    m = map_pic(None, level=88)
    assert (m.java_type, m.java_initializer) == ("boolean", "false")
    assert m.category == "condition"


# --------------------------------------------------------------------------
# Totality — the mapper must never raise (CONTRACTS §2)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("pic", [
    "", "   ", "9(3).", "QQQ", "X(", "9()", "S", "V", "PPP9", "@#$%",
    "9(999999)", "X(0)",
])
def test_never_raises_on_hostile_input(pic):
    m = map_pic(pic)
    assert isinstance(m.java_type, str)
    assert m.length >= 0


def test_trailing_period_is_stripped_not_treated_as_decimal_point():
    assert map_pic("9(3).").scale == 0


def test_unrecognised_characters_are_reported():
    assert any("unrecognised" in n for n in map_pic("QQQ").notes)


# --------------------------------------------------------------------------
# Naming helpers
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cobol,java", [
    ("PLAN_PAYMENT-AMOUNT", "planPaymentAmount"),   # real Lendwise name
    ("WS-EMP-NAME",         "wsEmpName"),
    ("LS_LOAN-ID",          "lsLoanId"),
    ("AMOUNT",              "amount"),
    ("WS-DATE-YYYY",        "wsDateYyyy"),
])
def test_java_name(cobol, java):
    assert java_name(cobol) == java


def test_java_keyword_collision_is_marked_not_mangled():
    assert java_name("CLASS") == "class_"
    assert java_name("NEW") == "new_"


def test_leading_digit_is_prefixed():
    assert java_name("1ST-FIELD") == "f1stField"


def test_empty_name_does_not_produce_empty_identifier():
    assert java_name("") == "unnamed"
    assert java_name("---") == "unnamed"


def test_numbered_paragraph_becomes_a_legal_method_name():
    assert java_method_name("740-PAYMENT-NOT-FOUND") == "p740PaymentNotFound"
    assert java_method_name("800-UPDATE-PAYMENT-PLAN-STATUS") == (
        "p800UpdatePaymentPlanStatus"
    )


def test_class_name_from_program_id():
    assert java_class_name("LNDWISE4") == "Lndwise4"
    assert java_class_name("DLTPAYPL") == "Dltpaypl"
    assert java_class_name("PAY-ROLL") == "PayRoll"


def test_unique_java_name_is_stable_and_ordered():
    taken: set[str] = set()
    assert unique_java_name("amount", taken) == "amount"
    assert unique_java_name("amount", taken) == "amount2"
    assert unique_java_name("amount", taken) == "amount3"
