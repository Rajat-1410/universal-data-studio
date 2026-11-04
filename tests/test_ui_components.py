"""
Unit test for UI Components: verify render_metric_card handles all parameter types safely
"""
from utils.ui_components import render_metric_card


class MockStreamlitColumn:
    def __init__(self):
        self.last_html = ""

    def markdown(self, html: str, unsafe_allow_html: bool = False):
        self.last_html = html


def test_render_metric_card_with_color_as_col():
    # Calling with color string as 4th positional argument (like "#60A5FA")
    # Must NOT raise AttributeError: 'str' object has no attribute 'markdown'
    render_metric_card("Test Label", "123", "Sub text", "#60A5FA")


def test_render_metric_card_with_mock_column():
    col = MockStreamlitColumn()
    render_metric_card("Test Label", "456", "Sub text", col=col, color="#34D399")
    assert "456" in col.last_html
    assert "#34D399" in col.last_html


def test_render_metric_card_defaults():
    render_metric_card("Default Label", "789")
