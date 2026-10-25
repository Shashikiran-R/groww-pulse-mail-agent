"""
Report Generation engine — Pulse generator & templates.
"""

from src.generation.pulse_generator import PulseGenerator, PulseOutput, markdown_to_html
from src.generation.templates import PULSE_SYSTEM_PROMPT, PULSE_USER_PROMPT_TEMPLATE

__all__ = [
    "PulseGenerator",
    "PulseOutput",
    "markdown_to_html",
    "PULSE_SYSTEM_PROMPT",
    "PULSE_USER_PROMPT_TEMPLATE",
]
