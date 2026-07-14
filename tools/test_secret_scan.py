import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.secret_scan import (
    PASSWORD_ASSIGNMENT_RE,
    is_safe_placeholder,
    looks_like_embedded_value,
    scan_text_file,
)
from tools.secret_scan_test_data import (
    SAMPLE_EMBEDDED_CHECK,
    SAMPLE_PASSWORD_FORWARD,
    SAMPLE_PASSWORD_TYPE,
    SAMPLE_PASSWORD_VALUE,
    SAMPLE_PATTERN,
    SAMPLE_REGEX_CHECK,
    SAMPLE_SLACK_ID,
    SAMPLE_PLACEHOLDER,
)


def _write_temp_sample(tmp_path, content: str) -> pathlib.Path:
    path = tmp_path / 'sample.py'
    path.write_text(content, encoding='utf-8')
    return path


def test_hard_coded_password_string_is_detected(tmp_path):
    path = _write_temp_sample(tmp_path, SAMPLE_PASSWORD_VALUE)
    findings = scan_text_file(path)
    assert any(item[1] == 'password-assignment' for item in findings)


def test_password_type_annotation_is_ignored(tmp_path):
    path = _write_temp_sample(tmp_path, SAMPLE_PASSWORD_TYPE)
    findings = scan_text_file(path)
    assert not findings


def test_password_variable_forwarding_is_ignored(tmp_path):
    path = _write_temp_sample(tmp_path, SAMPLE_PASSWORD_FORWARD)
    findings = scan_text_file(path)
    assert not findings


def test_scanner_pattern_definitions_are_ignored(tmp_path):
    path = _write_temp_sample(tmp_path, SAMPLE_PATTERN)
    findings = scan_text_file(path)
    assert not findings


def test_real_slack_like_ids_are_detected(tmp_path):
    path = _write_temp_sample(tmp_path, SAMPLE_SLACK_ID)
    findings = scan_text_file(path)
    assert any(item[1] == 'slack-user-id' for item in findings)


def test_explicit_synthetic_placeholders_are_ignored(tmp_path):
    path = _write_temp_sample(tmp_path, SAMPLE_PLACEHOLDER)
    findings = scan_text_file(path)
    assert not findings


def test_password_assignment_regex_matches_string_literals():
    match = PASSWORD_ASSIGNMENT_RE.search(SAMPLE_REGEX_CHECK)
    assert match is not None
    assert match.group('value') == '"synthetic-secret"'


def test_embedded_value_detection_requires_literal_or_structure():
    assert looks_like_embedded_value('"secret"') is True
    assert looks_like_embedded_value('password') is False
    assert looks_like_embedded_value(SAMPLE_EMBEDDED_CHECK) is False
    assert is_safe_placeholder('<@synthetic-user>') is True
