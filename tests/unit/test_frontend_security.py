"""XSS regression tests for frontend security functions.

Python reimplementations of the JS sanitisation helpers so we can
regress-test the logic without a browser.
"""
import math
import os

import pytest

# ---------------------------------------------------------------------------
# Python equivalents of the JS helpers
# ---------------------------------------------------------------------------

_HTML_ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
    "`": "&#x60;",
}


def escape_html(text: str) -> str:
    """Mirror of the frontend escapeHtml()."""
    out: list[str] = []
    for ch in text:
        out.append(_HTML_ESCAPE_MAP.get(ch, ch))
    return "".join(out)


def escape_attr(text: str) -> str:
    """Mirror of the frontend escapeAttr()."""
    return escape_html(text)


def csv_cell(text: str) -> str:
    """Mirror of the frontend csvCell() – prefix dangerous chars with tab."""
    dangerous_prefixes = ("=", "+", "-", "@", "\t")
    if text and text[0] in dangerous_prefixes:
        return "\t" + text
    return text


def sanitize_css_percent(value) -> float:
    """Mirror of the frontend sanitizeCssPercent()."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(n):
        return 0.0
    return max(0.0, min(100.0, n))


# ---------------------------------------------------------------------------
# Project root for reading index.html
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
_INDEX_HTML = os.path.join(_PROJECT_ROOT, "frontend", "index.html")


def _read_index() -> str:
    with open(_INDEX_HTML, encoding="utf-8") as fh:
        return fh.read()


# ===== 1. escapeHtml ======================================================

class TestEscapeHtml:
    def test_script_tag(self):
        result = escape_html("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_onclick_attribute(self):
        result = escape_html("onclick=")
        assert "onclick=" == result  # not dangerous on its own

    def test_ampersand(self):
        result = escape_html("&")
        assert result == "&amp;"

    def test_double_quote(self):
        result = escape_html('"')
        assert result == "&quot;"

    def test_single_quote(self):
        result = escape_html("'")
        assert result == "&#x27;"

    def test_backtick(self):
        result = escape_html("`")
        assert result == "&#x60;"

    def test_mixed_payload(self):
        payload = '<img src=x onerror="alert(1)">'
        result = escape_html(payload)
        assert "<img" not in result
        assert "&lt;img" in result


# ===== 2. escapeAttr =======================================================

class TestEscapeAttr:
    def test_double_quote_injection(self):
        payload = '" onmouseover="alert(1)'
        result = escape_attr(payload)
        assert "&quot;" in result
        assert "onmouseover" not in result.split("&quot;")[0]

    def test_single_quote_injection(self):
        payload = "' onclick='alert(1)"
        result = escape_attr(payload)
        assert "&#x27;" in result

    def test_roundtrip_safety(self):
        """Escaped output should not re-open injection when placed in attr."""
        payload = '"><script>alert(1)</script>'
        result = escape_attr(payload)
        assert "<script>" not in result


# ===== 3. csvCell ==========================================================

class TestCsvCell:
    @pytest.mark.parametrize("payload", [
        "=SUM(A1)",
        "+cmd",
        "-2+3",
        "@SUM",
    ])
    def test_formula_prefix_prefixed(self, payload):
        result = csv_cell(payload)
        assert result.startswith("\t")

    def test_tab_prefix(self):
        result = csv_cell("\tdanger")
        assert result.startswith("\t")
        # double-tab means the tab itself was also prefixed
        assert result == "\t\tdanger"

    def test_safe_string_unchanged(self):
        result = csv_cell("hello world")
        assert result == "hello world"

    def test_empty_string_unchanged(self):
        result = csv_cell("")
        assert result == ""


# ===== 4. sanitizeCssPercent ===============================================

class TestSanitizeCssPercent:
    @pytest.mark.parametrize("value, expected", [
        (150, 100.0),
        (-5, 0.0),
        ("50px", 0.0),
        (float("nan"), 0.0),
        (50, 50.0),
        (0, 0.0),
        (100, 100.0),
    ])
    def test_clamp(self, value, expected):
        assert sanitize_css_percent(value) == expected


# ===== 5. CSP meta tag =====================================================

class TestCSP:
    def test_csp_meta_tag_present(self):
        content = _read_index()
        assert "Content-Security-Policy" in content

    def test_csp_disallows_unsafe_eval(self):
        content = _read_index()
        # The CSP should not contain 'unsafe-eval'
        # (extract just the meta tag content)
        idx = content.index("Content-Security-Policy")
        snippet = content[idx : idx + 300]
        assert "unsafe-eval" not in snippet


# ===== 6. SRI on echarts CDN ===============================================

class TestSRI:
    def test_echarts_script_has_integrity(self):
        content = _read_index()
        # Find the echarts script tag
        assert "echarts" in content
        idx = content.index("echarts")
        snippet = content[max(0, idx - 100) : idx + 200]
        assert "integrity=" in snippet

    def test_echarts_script_has_crossorigin(self):
        content = _read_index()
        idx = content.index("echarts")
        snippet = content[max(0, idx - 100) : idx + 200]
        assert "crossorigin=" in snippet
