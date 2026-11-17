from __future__ import annotations

import pytest
from core.tools.handlers.repo import _undo_double_escaping


@pytest.mark.unit
def test_double_escaped_file_is_decoded() -> None:
    raw = 'import os\\n\\ndef f():\\n\\treturn "a\\\\b"\\n'
    assert _undo_double_escaping(raw) == 'import os\n\ndef f():\n\treturn "a\\b"\n'


@pytest.mark.unit
def test_plain_content_is_left_alone() -> None:
    real = 'print("x\\ny")\nprint(1)\n'  # has real newlines: a literal \n in code stays
    assert _undo_double_escaping(real) == real
    one_line = 'SEP = "\\n"'  # a single literal \n is not treated as escaping
    assert _undo_double_escaping(one_line) == one_line
