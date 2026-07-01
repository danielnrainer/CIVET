"""Behavior-focused tests for syntax-highlighting token classification workflows."""

import pytest
from PyQt6.QtWidgets import QApplication

from gui.editor.syntax_highlighter import CIFSyntaxHighlighter


class _FakeMatch:
    def __init__(self, matched: bool, captured: str):
        self._matched = matched
        self._captured = captured

    def hasMatch(self):
        return self._matched

    def captured(self, index: int):
        if index != 1:
            return ""
        return self._captured

    def capturedStart(self, index: int):
        if index != 1:
            return -1
        return 0

    def capturedLength(self, index: int):
        if index != 1:
            return 0
        return len(self._captured)


class _FakePattern:
    def __init__(self, captured: str):
        self._captured = captured

    def match(self, text: str):
        _ = text
        return _FakeMatch(bool(self._captured), self._captured)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_field_pattern_captures_malformed_trailing_quote(app):
    _ = app
    highlighter = CIFSyntaxHighlighter()

    match = highlighter._field_pattern.match('_audit_contact.author_name"')

    assert match.hasMatch()
    assert match.captured(1) == '_audit_contact.author_name"'


def test_validated_field_highlighting_uses_full_token_for_classification(app, monkeypatch):
    _ = app
    highlighter = CIFSyntaxHighlighter()

    # Simulate token extraction returning the full malformed token.
    highlighter._field_pattern = _FakePattern('_audit_contact.author_name"')
    highlighter.in_loop_data = False

    captured_fields = []

    def validator(field_name: str) -> str:
        captured_fields.append(field_name)
        return highlighter.UNKNOWN

    highlighter.set_field_validator(validator)

    # Avoid QTextDocument dependencies in this focused workflow test.
    monkeypatch.setattr(highlighter, 'setFormat', lambda *args, **kwargs: None)

    highlighter._apply_validated_field_highlighting('_audit_contact.author_name"', '_audit_contact.author_name"')

    assert captured_fields == ['_audit_contact.author_name"']
