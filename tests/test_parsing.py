"""Tests for the JSON-parsing helpers in orchestrator and fix_orchestrator.

Covers: dict input, clean JSON, markdown-fenced JSON, and unparseable text.
"""

import json

import pytest

from app.services.orchestrator import (
    _extract_output,
    _parse_finding_counts,
    _parse_findings,
    _parse_json,
    _strip_fences,
)
from app.services.fix_orchestrator import _parse_fix_result


# ---------------------------------------------------------------------------
# _extract_output
# ---------------------------------------------------------------------------

class TestExtractOutput:
    def test_structured_output_dict(self):
        """structured_output as dict is returned directly."""
        result = {"structured_output": {"findings": []}, "messages": []}
        assert _extract_output(result) == {"findings": []}

    def test_structured_output_string(self):
        """structured_output as string is returned directly."""
        result = {"structured_output": '{"findings": []}', "messages": []}
        assert _extract_output(result) == '{"findings": []}'

    def test_v1_api_message_field(self):
        """v1 API uses 'message' not 'content' in message objects."""
        result = {
            "structured_output": None,
            "messages": [
                {"type": "initial_user_message", "message": "prompt text"},
                {"type": "devin_message", "message": '{"findings": [{"severity": "high"}]}'},
            ],
        }
        output = _extract_output(result)
        assert output == '{"findings": [{"severity": "high"}]}'

    def test_content_field_fallback(self):
        """Falls back to 'content' if 'message' is not present."""
        result = {
            "structured_output": None,
            "messages": [{"content": '{"findings": []}'}],
        }
        assert _extract_output(result) == '{"findings": []}'

    def test_no_messages(self):
        result = {"structured_output": None, "messages": []}
        assert _extract_output(result) == ""

    def test_empty_result(self):
        assert _extract_output({}) == ""


# ---------------------------------------------------------------------------
# _strip_fences
# ---------------------------------------------------------------------------

class TestStripFences:
    def test_no_fences(self):
        assert _strip_fences('{"a": 1}') == '{"a": 1}'

    def test_json_fence(self):
        text = '```json\n{"findings": []}\n```'
        assert _strip_fences(text) == '{"findings": []}'

    def test_plain_fence(self):
        text = '```\n{"findings": []}\n```'
        assert _strip_fences(text) == '{"findings": []}'

    def test_fence_with_surrounding_text(self):
        text = 'Here is the result:\n```json\n{"a": 1}\n```\nDone.'
        assert _strip_fences(text) == '{"a": 1}'

    def test_empty_string(self):
        assert _strip_fences("") == ""


# ---------------------------------------------------------------------------
# _parse_json
# ---------------------------------------------------------------------------

class TestParseJson:
    def test_dict_passthrough(self):
        d = {"findings": [{"severity": "high"}]}
        assert _parse_json(d) is d

    def test_clean_json_string(self):
        s = '{"findings": [{"severity": "high"}]}'
        assert _parse_json(s) == {"findings": [{"severity": "high"}]}

    def test_fenced_json_string(self):
        s = '```json\n{"findings": [{"severity": "critical"}]}\n```'
        assert _parse_json(s) == {"findings": [{"severity": "critical"}]}

    def test_fenced_json_with_surrounding_text(self):
        s = 'Here are the findings:\n```json\n{"findings": []}\n```\nEnd.'
        assert _parse_json(s) == {"findings": []}

    def test_plain_fence(self):
        s = '```\n{"findings": [{"severity": "low"}]}\n```'
        assert _parse_json(s) == {"findings": [{"severity": "low"}]}

    def test_returns_none_for_garbage(self):
        assert _parse_json("not json at all") is None

    def test_returns_none_for_none(self):
        assert _parse_json(None) is None

    def test_returns_none_for_int(self):
        assert _parse_json(42) is None

    def test_returns_none_for_empty_string(self):
        assert _parse_json("") is None


# ---------------------------------------------------------------------------
# _parse_finding_counts
# ---------------------------------------------------------------------------

SAMPLE_FINDINGS = {
    "findings": [
        {"severity": "critical", "title": "SQL injection"},
        {"severity": "high", "title": "XSS"},
        {"severity": "medium", "title": "Open redirect"},
        {"category": "bug", "title": "Off-by-one"},
    ]
}


class TestParseFindingCounts:
    def test_dict_input(self):
        counts = _parse_finding_counts(SAMPLE_FINDINGS)
        assert counts["total"] == 4
        assert counts["critical"] == 1
        assert counts["high"] == 1
        assert counts["medium"] == 1
        assert counts["low"] == 0

    def test_clean_json_input(self):
        counts = _parse_finding_counts(json.dumps(SAMPLE_FINDINGS))
        assert counts["total"] == 4
        assert counts["critical"] == 1

    def test_fenced_json_input(self):
        fenced = f"```json\n{json.dumps(SAMPLE_FINDINGS)}\n```"
        counts = _parse_finding_counts(fenced)
        assert counts["total"] == 4
        assert counts["critical"] == 1
        assert counts["high"] == 1

    def test_garbage_returns_zeros(self):
        counts = _parse_finding_counts("this is not json")
        assert counts["total"] == 0

    def test_empty_findings(self):
        counts = _parse_finding_counts({"findings": []})
        assert counts["total"] == 0


# ---------------------------------------------------------------------------
# _parse_findings
# ---------------------------------------------------------------------------

class TestParseFindings:
    def test_dict_input(self):
        findings = _parse_findings(SAMPLE_FINDINGS)
        assert len(findings) == 4
        assert findings[0]["title"] == "SQL injection"

    def test_clean_json_input(self):
        findings = _parse_findings(json.dumps(SAMPLE_FINDINGS))
        assert len(findings) == 4

    def test_fenced_json_input(self):
        fenced = f"```json\n{json.dumps(SAMPLE_FINDINGS)}\n```"
        findings = _parse_findings(fenced)
        assert len(findings) == 4
        assert findings[0]["title"] == "SQL injection"

    def test_fenced_with_surrounding_text(self):
        text = f"Results:\n```json\n{json.dumps(SAMPLE_FINDINGS)}\n```\nDone."
        findings = _parse_findings(text)
        assert len(findings) == 4

    def test_garbage_returns_empty(self):
        findings = _parse_findings("this is not json")
        assert findings == []


# ---------------------------------------------------------------------------
# _parse_fix_result
# ---------------------------------------------------------------------------

class TestParseFixResult:
    def test_dict_input(self):
        data = {"status": "fixed", "commit_sha": "abc123", "summary": "Fixed it"}
        result = _parse_fix_result(data)
        assert result["status"] == "fixed"
        assert result["commit_sha"] == "abc123"

    def test_clean_json_input(self):
        data = {"status": "fixed", "commit_sha": "abc123", "summary": "Fixed it"}
        result = _parse_fix_result(json.dumps(data))
        assert result["status"] == "fixed"

    def test_fenced_json_input(self):
        data = {"status": "skipped", "commit_sha": None, "summary": "Not fixable"}
        fenced = f"```json\n{json.dumps(data)}\n```"
        result = _parse_fix_result(fenced)
        assert result["status"] == "skipped"
        assert result["summary"] == "Not fixable"

    def test_garbage_stores_raw(self):
        result = _parse_fix_result("something went wrong")
        assert result["status"] is None
        assert "something went wrong" in result["summary"]
