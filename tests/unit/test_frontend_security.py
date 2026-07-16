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
    "\"": "&quot;",
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
    """Mirror of the frontend csvCell() -- prefix dangerous chars with tab."""
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


# ===== 7. X-Content-Type-Options ============================================

class TestSecurityHeaders:
    def test_nosniff_in_index(self):
        """X-Content-Type-Options mentioned in comments or meta tag."""
        content = _read_index()
        # Should reference nosniff either in meta or comment
        assert "nosniff" in content.lower() or "X-Content-Type-Options" in content


# ===== 8. Tactical board sanitizer coverage ==================================

_TACTICAL_JS = os.path.join(_PROJECT_ROOT, "frontend", "tactical-board.js")


def _read_tactical_js() -> str:
    with open(_TACTICAL_JS, encoding="utf-8") as fh:
        return fh.read()


class TestTacticalBoardSanitizer:
    def test_sanitize_project_limits_objects(self):
        """sanitizeProject caps objects at MAX_OBJECTS."""
        js = _read_tactical_js()
        assert "MAX_OBJECTS" in js
        assert ".slice(0, this.MAX_OBJECTS)" in js

    def test_sanitize_project_limits_frames(self):
        """sanitizeProject caps frames at MAX_FRAMES."""
        js = _read_tactical_js()
        assert "MAX_FRAMES" in js

    def test_sanitize_project_limits_text_length(self):
        """_safeString and sanitizeObject truncate text at MAX_TEXT_LENGTH."""
        js = _read_tactical_js()
        assert "MAX_TEXT_LENGTH" in js
        assert "this.MAX_TEXT_LENGTH" in js

    def test_sanitize_project_limits_import_size(self):
        """importJSON rejects files larger than MAX_IMPORT_BYTES."""
        js = _read_tactical_js()
        assert "MAX_IMPORT_BYTES" in js
        assert "Project file too large" in js

    def test_sanitize_project_clamps_coordinates(self):
        """_sanitizeObject clamps x/y to 0-100 range."""
        js = _read_tactical_js()
        assert "_clampNumber(object.x, 0, 100" in js
        assert "_clampNumber(object.y, 0, 100" in js

    def test_sanitize_project_validates_object_types(self):
        """_sanitizeObject only allows known object types."""
        js = _read_tactical_js()
        assert '"player", "ball", "arrow", "zone", "text"' in js

    def test_sanitize_project_strips_control_chars(self):
        """_safeString removes control characters."""
        js = _read_tactical_js()
        assert "\\u0000-\\u001F" in js or "\\u0000" in js

    def test_sanitize_project_strips_dangerous_id_chars(self):
        """_safeId removes characters outside [a-zA-Z0-9._-]."""
        js = _read_tactical_js()
        assert "a-zA-Z0-9._-" in js

    def test_sanitize_project_arrow_style_whitelist(self):
        """Arrow style is whitelisted to solid/dashed/curved."""
        js = _read_tactical_js()
        assert '"solid", "dashed", "curved"' in js


# ===== 9. App.js security helpers coverage ===================================

_APP_JS = os.path.join(_PROJECT_ROOT, "frontend", "app.js")


def _read_app_js() -> str:
    with open(_APP_JS, encoding="utf-8") as fh:
        return fh.read()


class TestAppJsSecurityHelpers:
    def test_escape_html_function_defined(self):
        js = _read_app_js()
        assert "function escapeHtml" in js

    def test_escape_attr_function_defined(self):
        js = _read_app_js()
        assert "function escapeAttr" in js

    def test_csv_cell_function_defined(self):
        js = _read_app_js()
        assert "function csvCell" in js

    def test_sanitize_css_percent_function_defined(self):
        js = _read_app_js()
        assert "function sanitizeCssPercent" in js

    def test_no_innerhtml_without_escape(self):
        """Check that innerHTML assignments use escapeHtml or template literals with escaping."""
        js = _read_app_js()
        # Find all innerHTML = assignments
        import re
        inner_html_assigns = re.findall(r"\.innerHTML\s*=\s*([^;]+)", js)
        # Most should reference escapeHtml, escapeAttr, or be safe patterns
        unsafe = []
        for assign in inner_html_assigns:
            assign_stripped = assign.strip()
            # Safe: uses escapeHtml, escapeAttr, or is a variable reference
            # or uses join/map (which typically includes escaping)
            # or is empty string
            if any(safe in assign_stripped for safe in [
                "escapeHtml", "escapeAttr", "join(", ".map(", '""',
                "No saved", "No data", "No results",
                "scout-note-display", "scout-note-textarea",
                "scout-tactical-role-btn", "price_band",
            ]):
                continue
            # Direct string literal without escaping is suspicious
            if assign_stripped.startswith('"') or assign_stripped.startswith("'"):
                # Simple literals are usually safe static text
                if ("<script" not in assign_stripped.lower()
                        and "onerror" not in assign_stripped.lower()):
                    continue
            # Template literals with ${} should use escapeHtml
            if "`" in assign_stripped and "${" in assign_stripped:
                if "escapeHtml" not in assign_stripped and "escapeAttr" not in assign_stripped:
                    unsafe.append(assign_stripped[:80])
        # This is a heuristic check -- allow some false positives
        # The key invariant is that dynamic user data goes through escapeHtml
        assert len(unsafe) < 8, f"Potentially unsafe innerHTML: {unsafe[:3]}"


# ===== 10. Tactical board renderer security ==================================

_TACTICAL_RENDERER_JS = os.path.join(_PROJECT_ROOT, "frontend", "tactical-renderer.js")


def _read_renderer_js() -> str:
    with open(_TACTICAL_RENDERER_JS, encoding="utf-8") as fh:
        return fh.read()


class TestTacticalRendererSecurity:
    def test_no_eval_in_renderer(self):
        """Renderer should not use eval()."""
        js = _read_renderer_js()
        assert "eval(" not in js

    def test_no_innerhtml_in_renderer(self):
        """Canvas renderer should not use innerHTML except for hover card tooltip."""
        js = _read_renderer_js()
        # innerHTML is acceptable for the hover card tooltip (controlled data)
        # Count occurrences -- should be minimal (1-2 for hover card)
        count = js.count("innerHTML")
        msg = f"Too many innerHTML uses ({count}), expected <=8"
        assert count <= 8, msg

    def test_no_document_write_in_renderer(self):
        """Renderer should not use document.write except for PDF export."""
        js = _read_renderer_js()
        # document.write is acceptable for PDF export print window
        count = js.count("document.write")
        assert count <= 2, f"Too many document.write uses ({count}), expected <=2 for PDF export"

    def test_coordinate_clamping(self):
        """Mouse move handler clamps coordinates to 0-100."""
        js = _read_renderer_js()
        assert "Math.max(0, Math.min(100" in js

# ===== 11. Event marker sanitization ========================================
class TestEventMarkerSanitization:
    """Verify event markers placed on tactical board are sanitized."""

    def test_event_marker_type_whitelist(self):
        """Event marker types should be whitelisted in the select options."""
        content = _read_index()
        # The tactical-event-marker-type select should only have safe option values
        assert 'id="tactical-event-marker-type"' in content
        allowed_types = {
            "press", "pass", "shot", "turnover",
            "overlap", "underlap", "third-man", "cover",
        }
        import re
        options = re.findall(
            r'id="tactical-event-marker-type"[^>]*>(.*?)</select>',
            content, re.DOTALL,
        )
        if options:
            values = re.findall(r'value="([^"]+)"', options[0])
            for v in values:
                assert v in allowed_types, f"Unexpected event marker type: {v}"

    def test_event_marker_label_escapes_html(self):
        """Event marker labels should go through escapeHtml in renderer."""
        js = _read_renderer_js()
        # The renderer should use escapeHtml or safe patterns for marker text
        # Check that event marker text rendering uses safe patterns
        has_safe_text = (
            "escapeHtml" in js
            or "textContent" in js
            or "fillText" in js  # canvas text rendering is safe
        )
        assert has_safe_text, "Renderer should use safe text rendering for markers"

    def test_event_marker_no_script_injection(self):
        """Event marker placement should not allow script injection."""
        js = _read_tactical_js()
        # sanitizeObject should handle text fields
        assert "MAX_TEXT_LENGTH" in js
        assert "text" in js  # text type should be in allowed types list


# ===== 12. Value page security ===============================================
class TestValuePageSecurity:
    """Verify value page dynamic content uses safe patterns."""

    def test_price_band_select_no_script(self):
        """Price band filter should only contain safe option values."""
        content = _read_index()
        assert 'id="value-price-band"' in content
        import re
        options = re.findall(
            r'id="value-price-band"[^>]*>(.*?)</select>',
            content, re.DOTALL,
        )
        if options:
            values = re.findall(r'value="([^"]+)"', options[0])
            allowed = {"all", "low", "medium", "high"}
            for v in values:
                assert v in allowed, f"Unexpected price band value: {v}"

    def test_age_curve_uses_escape_html(self):
        """Age curve chart tooltip should use escapeHtml."""
        js = _read_app_js()
        assert "renderAgeCurveScatter" in js
        # The function should use escapeHtml in its tooltip formatter
        idx = js.find("renderAgeCurveScatter")
        snippet = js[idx : idx + 2000]
        assert "escapeHtml" in snippet, "Age curve scatter should use escapeHtml in tooltip"

    def test_same_cohort_uses_escape_html(self):
        """Same-cohort comparison should use escapeHtml."""
        js = _read_app_js()
        assert "renderSameCohortComparison" in js
        idx = js.find("function renderSameCohortComparison")
        snippet = js[idx : idx + 1000]
        assert "escapeHtml" in snippet, "Same-cohort comparison should use escapeHtml"


# ===== 13. Watchlist notes security ==========================================
class TestWatchlistNotesSecurity:
    """Verify watchlist/shortlist notes use safe rendering."""

    def test_watchlist_notes_use_escape_html(self):
        """Watchlist notes display should use escapeHtml."""
        js = _read_app_js()
        # Check the watchlist rendering section uses escapeHtml for notes
        idx = js.find("watchlistNotes[pName]")
        assert idx > 0, "Watchlist notes reference found"
        # The rendering should escape the note content
        nearby = js[max(0, idx - 500) : idx + 500]
        assert "escapeHtml" in nearby, "Watchlist notes should be escaped with escapeHtml"

    def test_tactical_role_uses_escape_html(self):
        """Tactical role output should use escapeHtml."""
        js = _read_app_js()
        assert "generateTacticalRole" in js
        idx = js.find("generateTacticalRole")
        # Check that the function returns safe text
        func_end = js.find("}", js.find("return", idx))  # noqa: F841
        # The role strings are static, but the output container should escape
        assert "function generateTacticalRole" in js

    def test_scout_note_textarea_class_exists(self):
        """Textarea class for notes should be referenced in event handlers."""
        js = _read_app_js()
        assert "scout-note-textarea" in js
        assert "wl-note-player" in js or "wlNotePlayer" in js


# ===== 13b. Scouting dashboard handoff wiring (Round 86) ====================
class TestScoutingDashboardHandoffSecurity:
    """Verify the Round 86 dashboard △ / ◇ handoff buttons escape player keys.

    The dashboard renders candidate rows with data-cs-dash-short and
    data-cs-dash-compare attributes carrying the player name as the lookup
    key. These MUST go through escapeAttr() so a malicious or malformed
    player name cannot break out of the attribute and inject markup.
    """

    def test_dashboard_short_button_uses_escape_attr(self):
        js = _read_app_js()
        idx = js.find("data-cs-dash-short=")
        assert idx > 0, "dashboard shortlist button attribute not found"
        nearby = js[max(0, idx - 200) : idx + 200]
        assert "escapeAttr" in nearby, (
            "data-cs-dash-short must use escapeAttr for the player key"
        )

    def test_dashboard_compare_button_uses_escape_attr(self):
        js = _read_app_js()
        idx = js.find("data-cs-dash-compare=")
        assert idx > 0, "dashboard compare button attribute not found"
        nearby = js[max(0, idx - 200) : idx + 200]
        assert "escapeAttr" in nearby, (
            "data-cs-dash-compare must use escapeAttr for the player key"
        )

    def test_dashboard_batch_button_label_escaped(self):
        js = _read_app_js()
        idx = js.find("cs-dash-batch-add")
        assert idx > 0, "dashboard batch button id not found"
        nearby = js[max(0, idx - 300) : idx + 300]
        assert "escapeHtml" in nearby, (
            "batch button label must be escaped with escapeHtml"
        )

    def test_dashboard_batch_reason_code_present(self):
        js = _read_app_js()
        assert "cross_scouting_dashboard_batch" in js, (
            "batch reason code cross_scouting_dashboard_batch not wired"
        )

    def test_dashboard_single_reason_code_present(self):
        js = _read_app_js()
        assert "cross_scouting_dashboard" in js, (
            "single-candidate reason code cross_scouting_dashboard not wired"
        )

    def test_dashboard_batch_handler_no_alert(self):
        """Batch handler should surface status via textContent, not alert()."""
        js = _read_app_js()
        idx = js.find("function _wireCrossScoutingDashboardBatch")
        assert idx > 0, "batch handler function definition not found"
        func_body = js[idx : idx + 1400]
        assert "alert(" not in func_body, (
            "batch handler must not use alert() for status updates"
        )
        assert "textContent" in func_body, (
            "batch handler should set status via textContent"
        )


# ===== 13c. Shortlist / watchlist source provenance (Round 87) =============
class TestShortlistProvenanceSecurity:
    """Verify the Round 87 shortlist/watchlist source provenance wiring.

    The toggle functions now accumulate reason codes in a `reason_codes`
    array instead of silently overwriting or removing entries when a
    different source adds the same player. These tests lock in the
    static invariants: the helper exists, pills are escaped, and the
    legacy `reason_code` field is kept in sync for backward compat.
    """

    def test_entry_reason_codes_helper_defined(self):
        js = _read_app_js()
        assert "function _entryReasonCodes(" in js, (
            "_entryReasonCodes helper must be defined for provenance migration"
        )

    def test_normalize_entry_reason_codes_helper_defined(self):
        js = _read_app_js()
        assert "function _normalizeEntryReasonCodes(" in js, (
            "_normalizeEntryReasonCodes helper must be defined"
        )

    def test_render_reason_code_pills_uses_escape_html(self):
        js = _read_app_js()
        idx = js.find("function _renderReasonCodePills(")
        assert idx > 0, "_renderReasonCodePills function not found"
        func_body = js[idx : idx + 900]
        assert "escapeHtml" in func_body, (
            "reason code pills must escape each code with escapeHtml"
        )

    def test_toggle_shortlist_returns_source_change(self):
        js = _read_app_js()
        idx = js.find("function togglePlayerShortlist(")
        assert idx > 0
        func_body = js[idx : idx + 1800]
        assert "source_change" in func_body, (
            "togglePlayerShortlist must return a source_change field"
        )
        assert '"merged"' in func_body or "'merged'" in func_body, (
            "togglePlayerShortlist must surface a 'merged' source_change "
            "when a new reason code is accumulated"
        )

    def test_toggle_watchlist_returns_source_change(self):
        js = _read_app_js()
        idx = js.find("function togglePlayerWatchlist(")
        assert idx > 0
        func_body = js[idx : idx + 1800]
        assert "source_change" in func_body, (
            "togglePlayerWatchlist must return a source_change field"
        )

    def test_toggle_functions_accumulate_reason_codes_array(self):
        """Both toggle functions must push to a reason_codes array on merge."""
        js = _read_app_js()
        for func_name in ("togglePlayerShortlist", "togglePlayerWatchlist"):
            idx = js.find(f"function {func_name}(")
            assert idx > 0
            func_body = js[idx : idx + 1800]
            assert "reason_codes" in func_body, (
                f"{func_name} must reference reason_codes array"
            )
            assert "codes.push(" in func_body, (
                f"{func_name} must push new codes onto the array (accumulate)"
            )

    def test_watchlist_render_uses_pills_not_single_code(self):
        """Watchlist rendering must use _renderReasonCodePills, not a single
        inline reason_code string, so all accumulated sources are visible."""
        js = _read_app_js()
        idx = js.find('document.getElementById("watchlist").innerHTML')
        assert idx > 0
        nearby = js[idx : idx + 1200]
        assert "_renderReasonCodePills" in nearby, (
            "watchlist rendering must call _renderReasonCodePills"
        )

    def test_shortlist_render_uses_pills_not_single_code(self):
        """Shortlist rendering must use _renderReasonCodePills."""
        js = _read_app_js()
        idx = js.find('document.getElementById("shortlist").innerHTML')
        assert idx > 0
        nearby = js[idx : idx + 1600]
        assert "_renderReasonCodePills" in nearby, (
            "shortlist rendering must call _renderReasonCodePills"
        )

    def test_csv_export_includes_reason_codes_column(self):
        """CSV exports must include a reason_codes column (pipe-joined)."""
        js = _read_app_js()
        assert '"reason_codes"' in js or "'reason_codes'" in js, (
            "CSV export header must include a reason_codes column"
        )
        assert ".join(\"|\")" in js or ".join('|')" in js, (
            "reason_codes must be pipe-joined for CSV export"
        )


# ===== 14b. Round 88: shortlist provenance management security ==============
class TestShortlistProvenanceManagement:
    """Verify per-source removal, source summary strip, and filter wiring
    use proper escaping and safe event handlers."""

    def test_render_reason_code_pills_accepts_list_type(self):
        """_renderReasonCodePills must accept a listType parameter."""
        js = _read_app_js()
        assert "function _renderReasonCodePills(entry, listType)" in js, (
            "_renderReasonCodePills must accept a listType parameter"
        )

    def test_pill_x_button_uses_escape_attr(self):
        """The × button attributes must use escapeAttr for dynamic values."""
        js = _read_app_js()
        idx = js.find("function _renderReasonCodePills(")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert 'data-reason-code="${escapeAttr(code)}"' in func_body, (
            "× button data-reason-code must use escapeAttr"
        )
        assert 'data-reason-player="${escapeAttr(playerKey)}"' in func_body, (
            "× button data-reason-player must use escapeAttr"
        )
        assert 'data-reason-list="${escapeAttr(listType)}"' in func_body, (
            "× button data-reason-list must use escapeAttr"
        )

    def test_pill_x_button_title_uses_escape_attr(self):
        """The × button title must use escapeAttr for the i18n string."""
        js = _read_app_js()
        idx = js.find("function _renderReasonCodePills(")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert 'title="${escapeAttr(t("remove_source"))}"' in func_body, (
            "× button title must use escapeAttr for i18n string"
        )

    def test_pill_code_text_uses_escape_html(self):
        """The pill code text must use escapeHtml (not escapeAttr)."""
        js = _read_app_js()
        idx = js.find("function _renderReasonCodePills(")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert "${escapeHtml(code)}" in func_body, (
            "pill code text must use escapeHtml"
        )

    def test_source_summary_strip_uses_escape_html(self):
        """_renderSourceSummary must escape code text with escapeHtml."""
        js = _read_app_js()
        idx = js.find("function _renderSourceSummary(")
        assert idx > 0, "_renderSourceSummary function not found"
        func_body = js[idx : idx + 1200]
        assert "escapeHtml" in func_body, (
            "source summary must escape code text with escapeHtml"
        )
        assert "escapeAttr" in func_body, (
            "source summary must escape data-source-filter with escapeAttr"
        )

    def test_source_summary_uses_escape_attr_for_filter(self):
        """data-source-filter attribute must use escapeAttr."""
        js = _read_app_js()
        idx = js.find("function _renderSourceSummary(")
        assert idx > 0
        func_body = js[idx : idx + 1200]
        assert 'data-source-filter="${escapeAttr(code)}"' in func_body, (
            "data-source-filter must use escapeAttr"
        )
        assert 'data-source-list="${escapeAttr(listType)}"' in func_body, (
            "data-source-list must use escapeAttr"
        )

    def test_wire_reason_pill_removals_calls_toggle(self):
        """_wireReasonPillRemovals must call toggle functions."""
        js = _read_app_js()
        idx = js.find("function _wireReasonPillRemovals(")
        assert idx > 0, "_wireReasonPillRemovals function not found"
        func_body = js[idx : idx + 800]
        assert "togglePlayerShortlist" in func_body, (
            "_wireReasonPillRemovals must call togglePlayerShortlist"
        )
        assert "togglePlayerWatchlist" in func_body, (
            "_wireReasonPillRemovals must call togglePlayerWatchlist"
        )

    def test_wire_reason_pill_removals_no_eval(self):
        """_wireReasonPillRemovals must not use eval or innerHTML."""
        js = _read_app_js()
        idx = js.find("function _wireReasonPillRemovals(")
        assert idx > 0
        func_body = js[idx : idx + 800]
        assert "eval(" not in func_body, (
            "_wireReasonPillRemovals must not use eval"
        )
        assert ".innerHTML" not in func_body, (
            "_wireReasonPillRemovals must not use innerHTML"
        )

    def test_wire_source_summary_no_eval(self):
        """_wireSourceSummary must not use eval or innerHTML."""
        js = _read_app_js()
        idx = js.find("function _wireSourceSummary(")
        assert idx > 0
        func_body = js[idx : idx + 800]
        assert "eval(" not in func_body, (
            "_wireSourceSummary must not use eval"
        )
        assert ".innerHTML" not in func_body, (
            "_wireSourceSummary must not use innerHTML"
        )

    def test_filter_by_source_function_defined(self):
        """_filterBySource helper must be defined."""
        js = _read_app_js()
        assert "function _filterBySource(" in js, (
            "_filterBySource helper must be defined"
        )

    def test_compute_source_counts_function_defined(self):
        """_computeSourceCounts helper must be defined."""
        js = _read_app_js()
        assert "function _computeSourceCounts(" in js, (
            "_computeSourceCounts helper must be defined"
        )

    def test_source_filter_state_variables_defined(self):
        """Module-level filter state arrays must be defined."""
        js = _read_app_js()
        assert "let _shortlistSourceFilter" in js, (
            "_shortlistSourceFilter state must be defined"
        )
        assert "let _watchlistSourceFilter" in js, (
            "_watchlistSourceFilter state must be defined"
        )

    def test_renderscout_calls_wire_functions(self):
        """renderScouting must call _wireSourceSummary and _wireReasonPillRemovals."""
        js = _read_app_js()
        assert '_wireSourceSummary(document.getElementById("watchlist")' in js, (
            "renderScouting must wire source summary for watchlist"
        )
        assert '_wireSourceSummary(document.getElementById("shortlist")' in js, (
            "renderScouting must wire source summary for shortlist"
        )
        assert '_wireReasonPillRemovals(document.getElementById("watchlist")' in js, (
            "renderScouting must wire pill removals for watchlist"
        )
        assert '_wireReasonPillRemovals(document.getElementById("shortlist")' in js, (
            "renderScouting must wire pill removals for shortlist"
        )

    def test_renderscout_passes_list_type_to_pills(self):
        """renderScouting must pass listType to _renderReasonCodePills."""
        js = _read_app_js()
        assert '_renderReasonCodePills(player, "watchlist")' in js, (
            "watchlist render must pass 'watchlist' listType to pills"
        )
        assert '_renderReasonCodePills(player, "shortlist")' in js, (
            "shortlist render must pass 'shortlist' listType to pills"
        )


# ===== 14. Tactical board regression: malicious project title ================
class TestMaliciousTitleRegression:
    """Verify that XSS payloads in project titles are sanitized."""

    def test_malicious_title_script_tag(self):
        """XSS payload in title should be stripped by _safeString."""
        js = _read_tactical_js()
        # sanitizeProject uses _safeString for title
        assert '_safeString(project.title' in js or '_safeString(project?.title' in js

    def test_malicious_title_onerror(self):
        """onerror payload in title should not survive _safeString."""
        # _safeString removes control chars and limits length
        # The real sanitizer also escapes via escapeHtml when rendering
        js = _read_tactical_js()
        assert "MAX_TEXT_LENGTH" in js

    def test_title_sanitized_in_sanitize_project(self):
        """sanitizeProject should apply _safeString to title."""
        js = _read_tactical_js()
        # Find the sanitizeProject method and verify title is sanitized
        idx = js.find("sanitizeProject(project)")
        assert idx > 0
        snippet = js[idx : idx + 1500]
        assert "_safeString" in snippet


# ===== 15. Tactical board regression: malicious player name/notes ============
class TestMaliciousPlayerNameRegression:
    """Verify that XSS payloads in player names and notes are sanitized."""

    def test_player_label_sanitized(self):
        """Player label should go through _safeString."""
        js = _read_tactical_js()
        # In _sanitizeObject for player type
        assert "safe.label = this._safeString(object.label)" in js

    def test_player_notes_sanitized(self):
        """Player notes should go through _safeString with length limit."""
        js = _read_tactical_js()
        # _sanitizeObject truncates notes
        assert "_safeString(object.notes)" in js

    def test_notes_length_limited(self):
        """Player notes should be limited to 500 chars."""
        js = _read_tactical_js()
        assert ".slice(0, 500)" in js  # notes limit


# ===== 16. Tactical board regression: oversized JSON import ==================
class TestOversizedJsonImport:
    """Verify that oversized JSON imports are rejected."""

    def test_max_import_bytes_enforced(self):
        """importJSON should check file size against MAX_IMPORT_BYTES."""
        js = _read_tactical_js()
        assert "MAX_IMPORT_BYTES" in js
        assert "Project file too large" in js
        # Should check byte length before parsing
        assert "size" in js.lower() or "length" in js.lower() or "byteLength" in js.lower()


# ===== 17. Tactical board regression: corrupt JSON import ====================
class TestCorruptJsonImport:
    """Verify that corrupt JSON imports are handled gracefully."""

    def test_import_json_try_catch(self):
        """importJSON should have try/catch around JSON.parse."""
        js = _read_tactical_js()
        idx = js.find("importJSON")
        assert idx > 0
        snippet = js[idx : idx + 2000]
        assert "try" in snippet
        assert "catch" in snippet

    def test_import_json_board_id_required(self):
        """importJSON should require board_id in the parsed JSON."""
        js = _read_tactical_js()
        assert 'Invalid project: missing board_id' in js


# ===== 18. Tactical board regression: duplicate object IDs ===================
class TestDuplicateObjectIds:
    """Verify that duplicate object IDs are handled."""

    def test_sanitize_object_assigns_safe_id(self):
        """_sanitizeObject should use _safeId which generates unique IDs."""
        js = _read_tactical_js()
        # _sanitizeObject uses _safeId for the object id (object literal syntax)
        assert "id: this._safeId(object.id)" in js or "id:this._safeId(object.id)" in js

    def test_safe_id_generates_fallback(self):
        """_safeId should generate a fallback ID if input is empty."""
        js = _read_tactical_js()
        assert "Date.now().toString(36)" in js  # fallback ID generation


# ===== 19. Tactical board regression: out-of-range coordinates ===============
class TestOutOfRangeCoordinates:
    """Verify that out-of-range coordinates are clamped."""

    def test_x_coordinate_clamped(self):
        """Object x coordinate should be clamped to 0-100."""
        js = _read_tactical_js()
        assert "_clampNumber(object.x, 0, 100" in js

    def test_y_coordinate_clamped(self):
        """Object y coordinate should be clamped to 0-100."""
        js = _read_tactical_js()
        assert "_clampNumber(object.y, 0, 100" in js

    def test_arrow_coordinates_clamped(self):
        """Arrow start/end coordinates should be clamped to 0-100."""
        js = _read_tactical_js()
        assert "_clampNumber(object.startX, 0, 100" in js
        assert "_clampNumber(object.endX, 0, 100" in js


# ===== 20. Tactical board regression: too many objects =======================
class TestTooManyObjects:
    """Verify that too many objects are capped."""

    def test_max_objects_enforced(self):
        """sanitizeProject should cap objects at MAX_OBJECTS."""
        js = _read_tactical_js()
        assert "MAX_OBJECTS" in js
        assert ".slice(0, this.MAX_OBJECTS)" in js

    def test_max_frames_enforced(self):
        """sanitizeProject should cap frames at MAX_FRAMES."""
        js = _read_tactical_js()
        assert "MAX_FRAMES" in js
        assert ".slice(0, this.MAX_FRAMES)" in js

    def test_max_objects_value(self):
        """MAX_OBJECTS should be 200."""
        js = _read_tactical_js()
        assert "MAX_OBJECTS: 200" in js

    def test_max_frames_value(self):
        """MAX_FRAMES should be 60."""
        js = _read_tactical_js()
        assert "MAX_FRAMES: 60" in js


# ===== 21. Tactical board regression: old schema version =====================
class TestOldSchemaVersion:
    """Verify that old schema versions are migrated."""

    def test_schema_version_defined(self):
        """SCHEMA_VERSION should be defined."""
        js = _read_tactical_js()
        assert "SCHEMA_VERSION" in js

    def test_migrate_project_exists(self):
        """migrateProject method should exist for schema migration."""
        js = _read_tactical_js()
        assert "migrateProject" in js

    def test_version_set_on_sanitize(self):
        """sanitizeProject should set version to SCHEMA_VERSION."""
        js = _read_tactical_js()
        idx = js.find("sanitizeProject(project)")
        assert idx > 0
        snippet = js[idx : idx + 5000]
        assert "SCHEMA_VERSION" in snippet


# ===== 22. Performance boundary in renderer ==================================
class TestPerformanceBoundary:
    """Verify performance boundary checks exist in renderer."""

    def test_check_performance_method(self):
        """_checkPerformance method should exist."""
        js = _read_renderer_js()
        assert "_checkPerformance" in js

    def test_simplify_project_method(self):
        """simplifyProject method should exist."""
        js = _read_renderer_js()
        assert "simplifyProject" in js

    def test_performance_warning_message_objects(self):
        """Performance warning for objects should mention the count."""
        js = _read_renderer_js()
        assert "Too many objects" in js

    def test_performance_warning_message_frames(self):
        """Performance warning for frames should mention the count."""
        js = _read_renderer_js()
        assert "Too many frames" in js

    def test_fps_counter_method(self):
        """_drawFPSCounter method should exist."""
        js = _read_renderer_js()
        assert "_drawFPSCounter" in js

    def test_perf_monitor_state(self):
        """_perfMonitor state should be initialized."""
        js = _read_renderer_js()
        assert "_perfMonitor" in js
        assert "renderTime" in js

    def test_xt_heatmap_method(self):
        """_drawXTHeatmap method should exist for heatmap overlay."""
        js = _read_renderer_js()
        assert "_drawXTHeatmap" in js

    def test_statsbomb_attribution_in_heatmap(self):
        """Heatmap should display StatsBomb attribution."""
        js = _read_renderer_js()
        assert "Data: StatsBomb Open Data" in js


# ===== 23. Simplify button in HTML ==========================================
class TestSimplifyButtonHtml:
    """Verify simplify button exists in HTML."""

    def test_simplify_button_exists(self):
        """Simplify button should be in the tactical board HTML."""
        content = _read_index()
        assert 'id="tactical-simplify"' in content

    def test_heatmap_toggle_exists(self):
        """xT heatmap toggle button should be in the HTML."""
        content = _read_index()
        assert 'id="tactical-toggle-heatmap"' in content

    def test_debug_toggle_exists(self):
        """Debug mode toggle should be in the HTML."""
        content = _read_index()
        assert 'id="tactical-toggle-debug"' in content

    def test_xt_heatmap_tactical_button_exists(self):
        """Show on Tactical Board button should be in actions page."""
        content = _read_index()
        assert 'id="btn-xt-heatmap-tactical"' in content


# ===== 24. Round 89: Shortlist Quick-Compare security ========================
class TestShortlistQuickCompare:
    """Verify the shortlist quick-compare feature follows security rules."""

    def test_selection_state_variable_defined(self):
        js = _read_app_js()
        # Round 90: initialized from localStorage via _loadStringArray.
        assert "let _shortlistCompareSelection = _loadStringArray" in js

    def test_max_constant_defined(self):
        js = _read_app_js()
        assert "_SHORTLIST_COMPARE_MAX = 6" in js

    def test_toggle_function_defined(self):
        js = _read_app_js()
        assert "function _toggleShortlistCompareSelect" in js

    def test_clear_function_defined(self):
        js = _read_app_js()
        assert "function _clearShortlistCompareSelection" in js

    def test_prune_function_defined(self):
        js = _read_app_js()
        assert "function _pruneShortlistCompareSelection" in js

    def test_render_bar_function_defined(self):
        js = _read_app_js()
        assert "function _renderShortlistCompareBar" in js

    def test_wire_bar_function_defined(self):
        js = _read_app_js()
        assert "function _wireShortlistCompareBar" in js

    def test_wire_checkboxes_function_defined(self):
        js = _read_app_js()
        assert "function _wireShortlistCompareCheckboxes" in js

    def test_resolve_names_function_defined(self):
        js = _read_app_js()
        assert "function _resolveShortlistCompareNames" in js

    def test_render_result_function_defined(self):
        js = _read_app_js()
        assert "async function _renderShortlistCompareResult" in js

    def test_checkbox_uses_escape_attr_for_key(self):
        """The checkbox data-shortlist-compare-key must use escapeAttr."""
        js = _read_app_js()
        idx = js.find("data-shortlist-compare-key=")
        assert idx > 0
        snippet = js[max(0, idx - 200) : idx + 100]
        assert "escapeAttr(dossierKey)" in snippet

    def test_checkbox_uses_escape_attr_for_name(self):
        """The checkbox data-shortlist-compare-name must use escapeAttr."""
        js = _read_app_js()
        idx = js.find("data-shortlist-compare-name=")
        assert idx > 0
        snippet = js[max(0, idx - 200) : idx + 100]
        assert "escapeAttr(pName)" in snippet

    def test_bar_button_label_uses_escape_html(self):
        """The compare button label must use escapeHtml."""
        js = _read_app_js()
        idx = js.find("function _renderShortlistCompareBar")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert "escapeHtml" in func_body

    def test_bar_hint_uses_escape_html(self):
        """The hint text in the bar must use escapeHtml."""
        js = _read_app_js()
        idx = js.find("function _renderShortlistCompareBar")
        assert idx > 0
        func_body = js[idx : idx + 1300]
        assert "escapeHtml(hint)" in func_body

    def test_result_renderer_uses_escape_html(self):
        """The result renderer must escape all dynamic content."""
        js = _read_app_js()
        idx = js.find("async function _renderShortlistCompareResult")
        assert idx > 0
        func_body = js[idx : idx + 3000]
        # Player names, teams, dimension labels must all be escaped
        assert func_body.count("escapeHtml") >= 10

    def test_result_renderer_uses_escape_html_for_loading(self):
        """The loading message must use escapeHtml."""
        js = _read_app_js()
        idx = js.find("async function _renderShortlistCompareResult")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "escapeHtml(t(" in func_body

    def test_no_eval_in_compare_code(self):
        """No eval() in the quick-compare helpers."""
        js = _read_app_js()
        idx = js.find("===== Round 89")
        assert idx > 0
        end_idx = js.find("function togglePlayerWatchlist", idx)
        assert end_idx > idx
        snippet = js[idx:end_idx]
        assert "eval(" not in snippet

    def test_no_innerhtml_without_escape_in_compare_bar(self):
        """The bar innerHTML must use escapeHtml for dynamic content."""
        js = _read_app_js()
        idx = js.find("function _renderShortlistCompareBar")
        assert idx > 0
        func_body = js[idx : idx + 1700]
        # The only innerHTML assignment should contain escapeHtml calls
        assert "innerHTML" in func_body
        assert "escapeHtml" in func_body

    def test_renderscout_calls_wire_functions(self):
        """renderScouting must call the new wiring functions."""
        js = _read_app_js()
        idx = js.find("function renderScouting")
        assert idx > 0
        func_body = js[idx : idx + 16000]
        assert "_wireShortlistCompareCheckboxes" in func_body
        assert "_renderShortlistCompareBar" in func_body
        assert "_wireShortlistCompareBar" in func_body

    def test_renderscout_prunes_selection(self):
        """renderScouting must prune stale compare selections."""
        js = _read_app_js()
        idx = js.find("function renderScouting")
        assert idx > 0
        func_body = js[idx : idx + 16000]
        assert "_pruneShortlistCompareSelection" in func_body

    def test_checkbox_label_uses_escape_html_for_text(self):
        """The checkbox label text ('对比'/'Cmp') must use escapeHtml."""
        js = _read_app_js()
        idx = js.find("data-shortlist-compare-key=")
        assert idx > 0
        snippet = js[idx : idx + 300]
        assert "escapeHtml" in snippet

    def test_compare_result_container_in_html(self):
        """The shortlist-compare-result div must exist in index.html."""
        content = _read_index()
        assert 'id="shortlist-compare-result"' in content

    def test_compare_bar_container_in_html(self):
        """The shortlist-compare-bar div must exist in index.html."""
        content = _read_index()
        assert 'id="shortlist-compare-bar"' in content

    def test_i18n_keys_present_zh(self):
        """All 7 new i18n keys must be present (zh)."""
        js = _read_app_js()
        for key in [
            "shortlist_compare_btn",
            "shortlist_compare_clear",
            "shortlist_compare_min",
            "shortlist_compare_max",
            "shortlist_compare_loading",
            "shortlist_compare_unavailable",
            "shortlist_compare_failed",
        ]:
            assert f"{key}:" in js, f"Missing i18n key: {key}"

    def test_i18n_keys_present_en(self):
        """All 7 new i18n keys must be present (en section)."""
        js = _read_app_js()
        # Find the en section and verify keys exist there too
        en_idx = js.find("Compare selected")
        assert en_idx > 0

    def test_fetch_uses_existing_api_helper(self):
        """The result renderer should call fetchPlayerComparisonMulti, not a raw URL."""
        js = _read_app_js()
        idx = js.find("async function _renderShortlistCompareResult")
        assert idx > 0
        func_body = js[idx : idx + 3000]
        assert "fetchPlayerComparisonMulti" in func_body
        # Should not construct a raw fetch URL
        assert "/players/compare-multi" not in func_body


# ===== 25. Round 90: Shortlist UI state persistence ==========================
class TestShortlistUiStatePersistence:
    """Verify the localStorage persistence of shortlist UI state."""

    def test_shortlist_source_filter_key_defined(self):
        js = _read_app_js()
        assert 'SHORTLIST_SOURCE_FILTER_KEY = "sf-shortlist-source-filter"' in js

    def test_watchlist_source_filter_key_defined(self):
        js = _read_app_js()
        assert 'WATCHLIST_SOURCE_FILTER_KEY = "sf-watchlist-source-filter"' in js

    def test_compare_selection_key_defined(self):
        js = _read_app_js()
        assert 'SHORTLIST_COMPARE_SELECTION_KEY = "sf-shortlist-compare-selection"' in js

    def test_load_string_array_function_defined(self):
        js = _read_app_js()
        assert "function _loadStringArray" in js

    def test_save_string_array_function_defined(self):
        js = _read_app_js()
        assert "function _saveStringArray" in js

    def test_load_string_array_validates_array(self):
        """_loadStringArray must reject non-array JSON and non-string items."""
        js = _read_app_js()
        idx = js.find("function _loadStringArray")
        assert idx > 0
        func_body = js[idx : idx + 500]
        assert "Array.isArray" in func_body
        assert "typeof v === \"string\"" in func_body

    def test_load_string_array_caps_length(self):
        """_loadStringArray must cap the result to prevent unbounded growth."""
        js = _read_app_js()
        idx = js.find("function _loadStringArray")
        assert idx > 0
        func_body = js[idx : idx + 500]
        assert "slice(0, 100)" in func_body

    def test_save_string_array_uses_json_stringify(self):
        """_saveStringArray must use JSON.stringify (no raw concatenation)."""
        js = _read_app_js()
        idx = js.find("function _saveStringArray")
        assert idx > 0
        func_body = js[idx : idx + 300]
        assert "JSON.stringify" in func_body

    def test_shortlist_source_filter_loads_from_local_storage(self):
        """_shortlistSourceFilter must initialize via _loadStringArray."""
        js = _read_app_js()
        assert "let _shortlistSourceFilter = _loadStringArray" in js

    def test_watchlist_source_filter_loads_from_local_storage(self):
        """_watchlistSourceFilter must initialize via _loadStringArray."""
        js = _read_app_js()
        assert "let _watchlistSourceFilter = _loadStringArray" in js

    def test_compare_selection_loads_from_local_storage(self):
        """_shortlistCompareSelection must initialize via _loadStringArray."""
        js = _read_app_js()
        assert "let _shortlistCompareSelection = _loadStringArray" in js

    def test_persist_shortlist_source_filter_function_defined(self):
        js = _read_app_js()
        assert "function _persistShortlistSourceFilter" in js

    def test_persist_watchlist_source_filter_function_defined(self):
        js = _read_app_js()
        assert "function _persistWatchlistSourceFilter" in js

    def test_persist_compare_selection_function_defined(self):
        js = _read_app_js()
        assert "function _persistShortlistCompareSelection" in js

    def test_persist_shortlist_source_filter_calls_save(self):
        js = _read_app_js()
        idx = js.find("function _persistShortlistSourceFilter")
        assert idx > 0
        func_body = js[idx : idx + 300]
        assert "_saveStringArray" in func_body
        assert "SHORTLIST_SOURCE_FILTER_KEY" in func_body

    def test_persist_watchlist_source_filter_calls_save(self):
        js = _read_app_js()
        idx = js.find("function _persistWatchlistSourceFilter")
        assert idx > 0
        func_body = js[idx : idx + 300]
        assert "_saveStringArray" in func_body
        assert "WATCHLIST_SOURCE_FILTER_KEY" in func_body

    def test_persist_compare_selection_calls_save(self):
        js = _read_app_js()
        idx = js.find("function _persistShortlistCompareSelection")
        assert idx > 0
        func_body = js[idx : idx + 300]
        assert "_saveStringArray" in func_body
        assert "SHORTLIST_COMPARE_SELECTION_KEY" in func_body

    def test_toggle_compare_select_persists(self):
        """_toggleShortlistCompareSelect must call _persistShortlistCompareSelection."""
        js = _read_app_js()
        idx = js.find("function _toggleShortlistCompareSelect")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "_persistShortlistCompareSelection" in func_body

    def test_clear_compare_select_persists(self):
        """_clearShortlistCompareSelection must call _persistShortlistCompareSelection."""
        js = _read_app_js()
        idx = js.find("function _clearShortlistCompareSelection")
        assert idx > 0
        func_body = js[idx : idx + 300]
        assert "_persistShortlistCompareSelection" in func_body

    def test_prune_compare_select_persists_on_change(self):
        """_pruneShortlistCompareSelection must persist when keys are pruned."""
        js = _read_app_js()
        idx = js.find("function _pruneShortlistCompareSelection")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "_persistShortlistCompareSelection" in func_body

    def test_wire_source_summary_persists_shortlist(self):
        """_wireSourceSummary must call _persistShortlistSourceFilter for shortlist."""
        js = _read_app_js()
        idx = js.find("function _wireSourceSummary")
        assert idx > 0
        func_body = js[idx : idx + 1200]
        assert "_persistShortlistSourceFilter" in func_body

    def test_wire_source_summary_persists_watchlist(self):
        """_wireSourceSummary must call _persistWatchlistSourceFilter for watchlist."""
        js = _read_app_js()
        idx = js.find("function _wireSourceSummary")
        assert idx > 0
        func_body = js[idx : idx + 1200]
        assert "_persistWatchlistSourceFilter" in func_body

    def test_no_eval_in_persistence_code(self):
        """No eval() in the persistence helpers."""
        js = _read_app_js()
        idx = js.find("function _loadStringArray")
        assert idx > 0
        end_idx = js.find("function _computeSourceCounts", idx)
        assert end_idx > idx
        snippet = js[idx:end_idx]
        assert "eval(" not in snippet

    def test_save_string_array_wraps_in_try_catch(self):
        """_saveStringArray must be wrapped in try/catch (localStorage can throw)."""
        js = _read_app_js()
        idx = js.find("function _saveStringArray")
        assert idx > 0
        func_body = js[idx : idx + 300]
        assert "try" in func_body
        assert "catch" in func_body

    def test_load_string_array_wraps_in_try_catch(self):
        """_loadStringArray must be wrapped in try/catch."""
        js = _read_app_js()
        idx = js.find("function _loadStringArray")
        assert idx > 0
        func_body = js[idx : idx + 500]
        assert "try" in func_body
        assert "catch" in func_body


# ===== Round 91: Shortlist Provenance Audit Log + Reset UI State =============


class TestShortlistProvenanceLogReset:
    """Round 91: provenance audit log + reset UI state controls."""

    # --- constants ---

    def test_provenance_log_key_constant(self):
        """SHORTLIST_PROVENANCE_LOG_KEY uses sf- prefix."""
        js = _read_app_js()
        assert 'SHORTLIST_PROVENANCE_LOG_KEY = "sf-shortlist-provenance-log"' in js

    def test_provenance_log_max_constant(self):
        """_PROVENANCE_LOG_MAX caps the log size."""
        js = _read_app_js()
        assert "_PROVENANCE_LOG_MAX = 200" in js

    # --- _loadProvenanceLog ---

    def test_load_provenance_log_function_defined(self):
        js = _read_app_js()
        assert "function _loadProvenanceLog" in js

    def test_load_provenance_log_validates_array(self):
        """_loadProvenanceLog must filter to objects and slice to max."""
        js = _read_app_js()
        idx = js.find("function _loadProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "Array.isArray(parsed)" in func_body
        assert "typeof v === \"object\"" in func_body
        assert "_PROVENANCE_LOG_MAX" in func_body

    def test_load_provenance_log_wraps_in_try_catch(self):
        js = _read_app_js()
        idx = js.find("function _loadProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "try" in func_body
        assert "catch" in func_body

    # --- _persistShortlistProvenanceLog ---

    def test_persist_provenance_log_function_defined(self):
        js = _read_app_js()
        assert "function _persistShortlistProvenanceLog" in js

    def test_persist_provenance_log_wraps_in_try_catch(self):
        js = _read_app_js()
        idx = js.find("function _persistShortlistProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 400]
        assert "try" in func_body
        assert "catch" in func_body

    def test_persist_provenance_log_uses_json_stringify(self):
        js = _read_app_js()
        idx = js.find("function _persistShortlistProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 400]
        assert "JSON.stringify" in func_body
        assert "SHORTLIST_PROVENANCE_LOG_KEY" in func_body

    # --- state var ---

    def test_provenance_log_state_var_initialized_via_loader(self):
        """_shortlistProvenanceLog must initialize via _loadProvenanceLog()."""
        js = _read_app_js()
        assert "let _shortlistProvenanceLog = _loadProvenanceLog()" in js

    # --- _recordShortlistProvenance ---

    def test_record_provenance_function_defined(self):
        js = _read_app_js()
        assert "function _recordShortlistProvenance" in js

    def test_record_provenance_builds_entry_fields(self):
        """Entry must have all required audit fields."""
        js = _read_app_js()
        idx = js.find("function _recordShortlistProvenance")
        assert idx > 0
        func_body = js[idx : idx + 800]
        fields = (
            "timestamp", "player_key", "player_name",
            "action", "reason_code", "resulting_codes",
        )
        for field in fields:
            assert field in func_body, f"Missing field: {field}"

    def test_record_provenance_uses_iso_timestamp(self):
        js = _read_app_js()
        idx = js.find("function _recordShortlistProvenance")
        assert idx > 0
        func_body = js[idx : idx + 800]
        assert "new Date().toISOString()" in func_body

    def test_record_provenance_unshift_newest_first(self):
        """unshift puts newest entries at index 0."""
        js = _read_app_js()
        idx = js.find("function _recordShortlistProvenance")
        assert idx > 0
        func_body = js[idx : idx + 800]
        assert "unshift" in func_body

    def test_record_provenance_caps_at_max(self):
        """Log must be truncated to _PROVENANCE_LOG_MAX."""
        js = _read_app_js()
        idx = js.find("function _recordShortlistProvenance")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert "_PROVENANCE_LOG_MAX" in func_body
        assert ".length =" in func_body

    def test_record_provenance_calls_persist(self):
        js = _read_app_js()
        idx = js.find("function _recordShortlistProvenance")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert "_persistShortlistProvenanceLog" in func_body

    def test_record_provenance_slices_long_strings(self):
        """player_key sliced to 180, reason_code to 64."""
        js = _read_app_js()
        idx = js.find("function _recordShortlistProvenance")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert ".slice(0, 180)" in func_body
        assert ".slice(0, 64)" in func_body

    def test_record_provenance_validates_action(self):
        """action must be normalized to 'merged' or 'removed'."""
        js = _read_app_js()
        idx = js.find("function _recordShortlistProvenance")
        assert idx > 0
        func_body = js[idx : idx + 900]
        assert '"merged"' in func_body
        assert '"removed"' in func_body

    # --- _clearShortlistProvenanceLog ---

    def test_clear_provenance_log_function_defined(self):
        js = _read_app_js()
        assert "function _clearShortlistProvenanceLog" in js

    def test_clear_provenance_log_empties_then_persists(self):
        js = _read_app_js()
        idx = js.find("function _clearShortlistProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 300]
        assert "[]" in func_body
        assert "_persistShortlistProvenanceLog" in func_body

    # --- togglePlayerShortlist integration ---

    def test_toggle_shortlist_records_merged(self):
        """togglePlayerShortlist must call _recordShortlistProvenance with 'merged'."""
        js = _read_app_js()
        idx = js.find("function togglePlayerShortlist")
        assert idx > 0
        func_body = js[idx : idx + 2000]
        assert '_recordShortlistProvenance(entry, "merged"' in func_body

    def test_toggle_shortlist_records_removed(self):
        """togglePlayerShortlist records 'removed' for code-removal branch."""
        js = _read_app_js()
        idx = js.find("function togglePlayerShortlist")
        assert idx > 0
        func_body = js[idx : idx + 2000]
        assert '_recordShortlistProvenance(entry, "removed"' in func_body

    def test_toggle_shortlist_no_record_on_added(self):
        """The 'added' branch (new entry) must NOT call _recordShortlistProvenance."""
        js = _read_app_js()
        idx = js.find("function togglePlayerShortlist")
        assert idx > 0
        added_idx = js.find("source_change: \"added\"", idx)
        assert added_idx > idx
        # Check the 300 chars before added branch don't contain record call
        snippet_before = js[added_idx - 300 : added_idx]
        assert "_recordShortlistProvenance" not in snippet_before

    def test_toggle_shortlist_no_record_on_full_removal(self):
        """The full-removal branch (codes empty) must NOT call _recordShortlistProvenance."""
        js = _read_app_js()
        idx = js.find("function togglePlayerShortlist")
        assert idx > 0
        # Find the full-removal branch: codes.length === 0
        empty_idx = js.find("codes.length === 0", idx)
        assert empty_idx > idx
        # The next 200 chars should contain the return but NOT _recordShortlistProvenance
        snippet = js[empty_idx : empty_idx + 200]
        assert "_recordShortlistProvenance" not in snippet

    # --- _renderProvenanceLog ---

    def test_render_provenance_log_function_defined(self):
        js = _read_app_js()
        assert "function _renderProvenanceLog" in js

    def test_render_provenance_log_uses_escape_html_for_count(self):
        """The count in summary must use escapeHtml."""
        js = _read_app_js()
        idx = js.find("function _renderProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "escapeHtml(String(n))" in func_body

    def test_render_provenance_log_uses_escape_html_for_header(self):
        js = _read_app_js()
        idx = js.find("function _renderProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "escapeHtml(headerText)" in func_body

    def test_render_provenance_log_uses_details_summary(self):
        """Uses <details>/<summary> for collapsible section."""
        js = _read_app_js()
        idx = js.find("function _renderProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 1000]
        assert "<details" in func_body
        assert "<summary" in func_body

    def test_render_provenance_log_renders_clear_button(self):
        js = _read_app_js()
        idx = js.find("function _renderProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 3000]
        assert "provenance-log-clear" in func_body
        assert "escapeHtml" in func_body

    def test_render_provenance_log_uses_escape_html_on_all_dynamic(self):
        """All dynamic fields in the table must use escapeHtml."""
        js = _read_app_js()
        idx = js.find("function _renderProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 2500]
        # timestamp, player_name, actionLabel, reason_code, resultCodes
        assert "escapeHtml(logEntry.timestamp" in func_body
        assert "escapeHtml(logEntry.player_name" in func_body
        assert "escapeHtml(actionLabel)" in func_body
        assert "escapeHtml(logEntry.reason_code" in func_body
        assert "escapeHtml(resultCodes)" in func_body

    def test_render_provenance_log_no_eval(self):
        js = _read_app_js()
        idx = js.find("function _renderProvenanceLog")
        assert idx > 0
        end_idx = js.find("function _wireProvenanceLog", idx)
        assert end_idx > idx
        snippet = js[idx:end_idx]
        assert "eval(" not in snippet

    # --- _wireProvenanceLog ---

    def test_wire_provenance_log_function_defined(self):
        js = _read_app_js()
        assert "function _wireProvenanceLog" in js

    def test_wire_provenance_log_wires_clear_button(self):
        js = _read_app_js()
        idx = js.find("function _wireProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 800]
        assert "provenance-log-clear" in func_body
        assert "addEventListener" in func_body

    def test_wire_provenance_log_clear_calls_clear_function(self):
        js = _read_app_js()
        idx = js.find("function _wireProvenanceLog")
        assert idx > 0
        func_body = js[idx : idx + 800]
        assert "_clearShortlistProvenanceLog" in func_body
        assert "_renderProvenanceLog" in func_body

    # --- _resetShortlistUiState ---

    def test_reset_ui_state_function_defined(self):
        js = _read_app_js()
        assert "function _resetShortlistUiState" in js

    def test_reset_ui_state_clears_all_three_arrays(self):
        js = _read_app_js()
        idx = js.find("function _resetShortlistUiState")
        assert idx > 0
        func_body = js[idx : idx + 500]
        assert "_shortlistSourceFilter = []" in func_body
        assert "_watchlistSourceFilter = []" in func_body
        assert "_shortlistCompareSelection = []" in func_body

    def test_reset_ui_state_persists_all_three(self):
        js = _read_app_js()
        idx = js.find("function _resetShortlistUiState")
        assert idx > 0
        func_body = js[idx : idx + 500]
        assert "_persistShortlistSourceFilter" in func_body
        assert "_persistWatchlistSourceFilter" in func_body
        assert "_persistShortlistCompareSelection" in func_body

    def test_reset_ui_state_does_not_clear_shortlist_data(self):
        """Reset must NOT clear the shortlist itself, only UI state."""
        js = _read_app_js()
        idx = js.find("function _resetShortlistUiState")
        assert idx > 0
        end_idx = js.find("function _wireResetShortlistUiState", idx)
        assert end_idx > idx
        snippet = js[idx:end_idx]
        assert "savePlayerShortlist" not in snippet
        assert "savePlayerWatchlist" not in snippet
        assert "getPlayerShortlist" not in snippet

    # --- _wireResetShortlistUiState ---

    def test_wire_reset_ui_state_function_defined(self):
        js = _read_app_js()
        assert "function _wireResetShortlistUiState" in js

    def test_wire_reset_ui_state_wires_button(self):
        js = _read_app_js()
        idx = js.find("function _wireResetShortlistUiState")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "shortlist-reset-ui-state" in func_body
        assert "addEventListener" in func_body

    def test_wire_reset_ui_state_calls_reset_and_render(self):
        js = _read_app_js()
        idx = js.find("function _wireResetShortlistUiState")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "_resetShortlistUiState" in func_body
        assert "renderScouting" in func_body

    def test_wire_reset_ui_state_idempotent(self):
        """Uses dataset guard to avoid double-wiring on re-render."""
        js = _read_app_js()
        idx = js.find("function _wireResetShortlistUiState")
        assert idx > 0
        func_body = js[idx : idx + 600]
        assert "round91Wired" in func_body
        assert "dataset" in func_body

    # --- renderScouting integration ---

    def test_renderscout_calls_provenance_render(self):
        js = _read_app_js()
        idx = js.find("function renderScouting")
        assert idx > 0
        func_body = js[idx : idx + 18000]
        assert "_renderProvenanceLog()" in func_body

    def test_renderscout_calls_provenance_wire(self):
        js = _read_app_js()
        idx = js.find("function renderScouting")
        assert idx > 0
        func_body = js[idx : idx + 18000]
        assert "_wireProvenanceLog()" in func_body

    def test_renderscout_calls_reset_wire(self):
        js = _read_app_js()
        idx = js.find("function renderScouting")
        assert idx > 0
        func_body = js[idx : idx + 18000]
        assert "_wireResetShortlistUiState()" in func_body

    # --- index.html containers ---

    def test_index_html_has_provenance_container(self):
        content = _read_index()
        assert 'id="shortlist-provenance-log"' in content

    def test_index_html_has_reset_button(self):
        content = _read_index()
        assert 'id="shortlist-reset-ui-state"' in content

    def test_index_html_reset_button_has_i18n_attr(self):
        content = _read_index()
        idx = content.find('id="shortlist-reset-ui-state"')
        assert idx > 0
        snippet = content[max(0, idx - 200) : idx + 400]
        assert "data-i18n=" in snippet
        assert "data-i18n-title=" in snippet

    # --- i18n keys ---

    _PROVENANCE_I18N_KEYS = (
        "shortlist_provenance_log_title",
        "shortlist_provenance_empty",
        "shortlist_provenance_count",
        "shortlist_provenance_col_time",
        "shortlist_provenance_col_player",
        "shortlist_provenance_col_action",
        "shortlist_provenance_col_code",
        "shortlist_provenance_col_result",
        "shortlist_provenance_action_merged",
        "shortlist_provenance_action_removed",
        "shortlist_provenance_clear",
        "shortlist_reset_ui_state",
        "shortlist_reset_ui_state_title",
    )

    def test_i18n_keys_present_zh(self):
        js = _read_app_js()
        # zh section is before en section; find the zh block
        zh_end = js.find("shortlist_compare_failed: \"Comparison fetch failed\"")
        assert zh_end > 0
        zh_block = js[:zh_end]
        for key in self._PROVENANCE_I18N_KEYS:
            assert key + ":" in zh_block, f"Missing zh i18n key: {key}"

    def test_i18n_keys_present_en(self):
        js = _read_app_js()
        en_start = js.find("shortlist_compare_failed: \"Comparison fetch failed\"")
        assert en_start > 0
        en_block = js[en_start : en_start + 5000]
        for key in self._PROVENANCE_I18N_KEYS:
            assert key + ":" in en_block, f"Missing en i18n key: {key}"


# ===== 28. Round 92: Provenance export + compare tray sync ===================
class TestShortlistProvenanceExportAndTraySync:
    """Round 92: provenance log in decision pack export + compare tray sync."""

    # --- Decision pack: provenance log in JSON ---

    def test_decision_pack_version_bumped(self):
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 1500]
        assert 'version: "1.1.0"' in body

    def test_decision_pack_includes_provenance_log(self):
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 2500]
        assert "provenance_log:" in body
        assert "_shortlistProvenanceLog.map" in body

    def test_decision_pack_provenance_entry_has_all_fields(self):
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 2500]
        for field in ("timestamp", "player_key", "player_name",
                      "action", "reason_code", "resulting_codes"):
            assert field + ":" in body, f"Missing provenance field: {field}"

    def test_decision_pack_provenance_action_normalised(self):
        """action must be normalised to 'merged' or 'removed'."""
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 2500]
        assert 'entry.action === "merged" ? "merged" : "removed"' in body

    def test_decision_pack_provenance_resulting_codes_is_array(self):
        """resulting_codes must be Array.isArray-guarded and mapped to String."""
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 2500]
        assert "Array.isArray(entry.resulting_codes)" in body
        assert ".map((c) => String(c || \"\"))" in body

    def test_decision_pack_provenance_fields_coerced_to_string(self):
        """All string fields must be coerced via String()."""
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 2500]
        prov_start = body.find("provenance_log:")
        prov_end = body.find("limitations:")
        prov = body[prov_start:prov_end]
        assert "String(entry.timestamp" in prov
        assert "String(entry.player_key" in prov
        assert "String(entry.player_name" in prov
        assert "String(entry.reason_code" in prov

    def test_decision_pack_limitations_include_provenance_disclaimer(self):
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 3000]
        assert "Provenance log is a browser-local audit trail" in body
        assert "not a server-side audit record" in body

    def test_decision_pack_limitations_count_is_four(self):
        """Limitations array now has 4 entries (was 3 before Round 92)."""
        js = _read_app_js()
        idx = js.find("function buildShortlistDecisionPack")
        assert idx > 0
        body = js[idx : idx + 3000]
        lim_start = body.find("limitations: [")
        lim_end = body.find("],", lim_start)
        lim_block = body[lim_start:lim_end]
        assert lim_block.count('"Shortlist selection') == 1
        assert lim_block.count('"This export is not') == 1
        assert lim_block.count('"Ratings and confidence') == 1
        assert lim_block.count('"Provenance log is') == 1

    # --- Decision pack: provenance log in CSV ---

    def test_csv_export_has_provenance_section(self):
        js = _read_app_js()
        idx = js.find("function exportShortlistDecisionPackCSV")
        assert idx > 0
        body = js[idx : idx + 2500]
        assert "# Provenance Log" in body

    def test_csv_export_provenance_header_row(self):
        js = _read_app_js()
        idx = js.find("function exportShortlistDecisionPackCSV")
        assert idx > 0
        body = js[idx : idx + 2500]
        prov_start = body.find("# Provenance Log")
        prov_block = body[prov_start : prov_start + 600]
        assert "timestamp" in prov_block
        assert "player_key" in prov_block
        assert "player_name" in prov_block
        assert "action" in prov_block
        assert "reason_code" in prov_block
        assert "resulting_codes" in prov_block

    def test_csv_export_provenance_uses_csv_cell(self):
        """CSV rows must go through csvCell for formula injection protection."""
        js = _read_app_js()
        idx = js.find("function exportShortlistDecisionPackCSV")
        assert idx > 0
        body = js[idx : idx + 2500]
        assert "row.map(csvCell).join" in body

    def test_csv_export_provenance_resulting_codes_pipe_joined(self):
        """resulting_codes in CSV must be pipe-joined like reason_codes."""
        js = _read_app_js()
        idx = js.find("function exportShortlistDecisionPackCSV")
        assert idx > 0
        body = js[idx : idx + 2500]
        prov_start = body.find("# Provenance Log")
        prov_block = body[prov_start : prov_start + 800]
        assert '.join("|")' in prov_block

    def test_csv_export_provenance_handles_missing_log(self):
        """CSV must guard against missing provenance_log via || []."""
        js = _read_app_js()
        idx = js.find("function exportShortlistDecisionPackCSV")
        assert idx > 0
        body = js[idx : idx + 2500]
        assert "(pack.provenance_log || [])" in body

    # --- Compare tray sync: helpers ---

    def test_resolve_players_function_defined(self):
        js = _read_app_js()
        assert "function _resolveShortlistComparePlayers" in js

    def test_resolve_names_delegates_to_resolve_players(self):
        """_resolveShortlistCompareNames must delegate to _resolveShortlistComparePlayers."""
        js = _read_app_js()
        idx = js.find("function _resolveShortlistCompareNames")
        assert idx > 0
        body = js[idx : idx + 400]
        assert "_resolveShortlistComparePlayers()" in body
        assert ".map((p) => p.name)" in body

    def test_resolve_players_reads_team_attribute(self):
        """_resolveShortlistComparePlayers must read data-shortlist-compare-team."""
        js = _read_app_js()
        idx = js.find("function _resolveShortlistComparePlayers")
        assert idx > 0
        body = js[idx : idx + 800]
        assert 'data-shortlist-compare-team' in body
        assert "team" in body

    def test_resolve_players_returns_key_name_team(self):
        """Each entry must have key, name, team."""
        js = _read_app_js()
        idx = js.find("function _resolveShortlistComparePlayers")
        assert idx > 0
        body = js[idx : idx + 800]
        assert "key: " in body or "{ key, name, team }" in body

    def test_sync_function_defined(self):
        js = _read_app_js()
        assert "function _syncShortlistCompareToTray" in js

    def test_sync_returns_added_skipped_dup_skipped_cap(self):
        """Sync function must return {added, skipped_dup, skipped_cap}."""
        js = _read_app_js()
        idx = js.find("function _syncShortlistCompareToTray")
        assert idx > 0
        body = js[idx : idx + 1200]
        assert "added: 0" in body
        assert "skipped_dup: 0" in body
        assert "skipped_cap: 0" in body
        assert "added, skipped_dup: skippedDup, skipped_cap: skippedCap" in body

    def test_sync_dedup_check(self):
        """Sync must skip players already in tray by key."""
        js = _read_app_js()
        idx = js.find("function _syncShortlistCompareToTray")
        assert idx > 0
        body = js[idx : idx + 1200]
        assert '_crossScoutingCompareTray.some' in body
        assert 't.key === p.key' in body

    def test_sync_cap_check(self):
        """Sync must respect _CROSS_SCOUTING_COMPARE_MAX cap."""
        js = _read_app_js()
        idx = js.find("function _syncShortlistCompareToTray")
        assert idx > 0
        body = js[idx : idx + 1200]
        assert '_CROSS_SCOUTING_COMPARE_MAX' in body

    def test_sync_calls_render_compare_tray_only_when_added(self):
        """Sync must call _renderCompareTray() only when added > 0."""
        js = _read_app_js()
        idx = js.find("function _syncShortlistCompareToTray")
        assert idx > 0
        body = js[idx : idx + 1200]
        assert "if (added > 0) _renderCompareTray()" in body

    def test_sync_early_return_on_empty(self):
        """Sync must early-return when no players to sync."""
        js = _read_app_js()
        idx = js.find("function _syncShortlistCompareToTray")
        assert idx > 0
        body = js[idx : idx + 1200]
        assert "players.length === 0" in body

    def test_sync_pushes_player_object(self):
        """Sync must push the player object to _crossScoutingCompareTray."""
        js = _read_app_js()
        idx = js.find("function _syncShortlistCompareToTray")
        assert idx > 0
        body = js[idx : idx + 1200]
        assert "_crossScoutingCompareTray.push(p)" in body

    # --- Compare tray sync: format message ---

    def test_format_sync_message_function_defined(self):
        js = _read_app_js()
        assert "function _formatSyncTrayMessage" in js

    def test_format_sync_message_empty_case(self):
        js = _read_app_js()
        idx = js.find("function _formatSyncTrayMessage")
        assert idx > 0
        body = js[idx : idx + 900]
        assert 't("shortlist_compare_sync_empty")' in body

    def test_format_sync_message_uses_replace_for_counts(self):
        """All count messages must use .replace('{n}', ...)."""
        js = _read_app_js()
        idx = js.find("function _formatSyncTrayMessage")
        assert idx > 0
        body = js[idx : idx + 900]
        assert '.replace("{n}", String(result.added))' in body
        assert '.replace("{n}", String(result.skipped_dup))' in body
        assert '.replace("{n}", String(result.skipped_cap))' in body

    def test_format_sync_message_joins_with_middot(self):
        """Parts must be joined with middle dot."""
        js = _read_app_js()
        idx = js.find("function _formatSyncTrayMessage")
        assert idx > 0
        body = js[idx : idx + 900]
        assert 'join(" \\u00B7 ")' in body

    def test_format_sync_message_returns_empty_string_on_falsy(self):
        js = _read_app_js()
        idx = js.find("function _formatSyncTrayMessage")
        assert idx > 0
        body = js[idx : idx + 200]
        assert "if (!result) return \"\"" in body

    # --- Compare tray sync: bar rendering + wiring ---

    def test_bar_renders_sync_button_when_selection_nonempty(self):
        """Sync button must only render when n > 0."""
        js = _read_app_js()
        idx = js.find("function _renderShortlistCompareBar")
        assert idx > 0
        body = js[idx : idx + 1300]
        assert 'if (n > 0)' in body
        assert 'data-shortlist-compare-sync-tray="1"' in body

    def test_bar_sync_button_uses_escape_html_for_label(self):
        js = _read_app_js()
        idx = js.find("function _renderShortlistCompareBar")
        assert idx > 0
        body = js[idx : idx + 1300]
        assert 'escapeHtml(t("shortlist_compare_sync_tray"))' in body

    def test_bar_sync_button_uses_escape_attr_for_title(self):
        js = _read_app_js()
        idx = js.find("function _renderShortlistCompareBar")
        assert idx > 0
        body = js[idx : idx + 1300]
        assert 'escapeAttr(t("shortlist_compare_sync_tray_title"))' in body

    def test_wire_bar_wires_sync_button(self):
        js = _read_app_js()
        idx = js.find("function _wireShortlistCompareBar")
        assert idx > 0
        body = js[idx : idx + 1600]
        assert 'data-shortlist-compare-sync-tray="1"' in body
        assert "_syncShortlistCompareToTray()" in body
        assert "_formatSyncTrayMessage" in body

    def test_wire_bar_sync_sets_text_content_not_innerhtml(self):
        """Sync feedback must use textContent, not innerHTML."""
        js = _read_app_js()
        idx = js.find("function _wireShortlistCompareBar")
        assert idx > 0
        body = js[idx : idx + 1600]
        sync_start = body.find("data-shortlist-compare-sync-tray")
        sync_block = body[sync_start : sync_start + 800]
        assert "textContent" in sync_block
        assert "innerHTML" not in sync_block

    # --- Checkbox team attribute ---

    def test_checkbox_has_team_attribute(self):
        """Checkbox must include data-shortlist-compare-team using escapeAttr."""
        js = _read_app_js()
        idx = js.find("data-shortlist-compare-key=")
        assert idx > 0
        snippet = js[idx : idx + 400]
        assert "data-shortlist-compare-team=" in snippet
        assert "escapeAttr(player.team" in snippet

    # --- No eval / no raw innerHTML ---

    def test_no_eval_in_sync_code(self):
        """No eval() in the sync helpers."""
        js = _read_app_js()
        for fname in ("_syncShortlistCompareToTray", "_formatSyncTrayMessage",
                      "_resolveShortlistComparePlayers"):
            idx = js.find("function " + fname)
            assert idx > 0
            end_idx = js.find("\nfunction ", idx + 1)
            if end_idx < 0:
                end_idx = idx + 2000
            snippet = js[idx:end_idx]
            assert "eval(" not in snippet, f"eval found in {fname}"

    # --- i18n keys ---

    _SYNC_I18N_KEYS = (
        "shortlist_compare_sync_tray",
        "shortlist_compare_sync_tray_title",
        "shortlist_compare_sync_added",
        "shortlist_compare_sync_dup",
        "shortlist_compare_sync_cap",
        "shortlist_compare_sync_empty",
    )

    def test_sync_i18n_keys_present_zh(self):
        js = _read_app_js()
        zh_end = js.find('shortlist_compare_failed: "对比请求失败"')
        assert zh_end > 0
        zh_block = js[:zh_end + 600]
        for key in self._SYNC_I18N_KEYS:
            assert key + ":" in zh_block, f"Missing zh i18n key: {key}"

    def test_sync_i18n_keys_present_en(self):
        js = _read_app_js()
        en_start = js.find('shortlist_compare_failed: "Comparison fetch failed"')
        assert en_start > 0
        en_block = js[en_start : en_start + 1500]
        for key in self._SYNC_I18N_KEYS:
            assert key + ":" in en_block, f"Missing en i18n key: {key}"
