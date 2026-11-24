import json

import pytest

from board_engine.canvas import _strip_comments, compile_source, pretty_json
from board_engine.canvas_prompt import EXAMPLE
from board_engine.json_repair import repair_json

SRC = pretty_json(EXAMPLE)
parse = lambda s: json.loads(_strip_comments(s))


def fix(text):
    res = repair_json(text, parse)
    assert res is not None, 'not repaired'
    return parse(res[0]), res[1]


def broken(old, new, count=1):
    assert SRC.count(old) >= count, old
    return SRC.replace(old, new, count)


# (name, broken text) -> must parse back to exactly the original design
EXACT = [
    ('missing comma between boards', lambda: broken('\n    },\n    {', '\n    }\n    {')),
    ('missing comma between members', lambda: broken('"name": "Table top",', '"name": "Table top"')),
    ('missing commas in a number list', lambda: broken('[0, 732, 0]', '[0 732 0]')),
    ('truncated reply', lambda: SRC.rstrip()[:-12].rstrip().rstrip(',')),
    ('object never closed before the next one', lambda: broken('\n    },\n    {', '\n    ,\n    {')),
    ('] used to close an object', lambda: broken('"thickness": 18,\n    "clearance": 0.2\n  }', '"thickness": 18,\n    "clearance": 0.2\n  ]')),
    ('extra } closes the design early', lambda: broken('"clearance": 0.2\n  },', '"clearance": 0.2\n  }},')),
    ('extra ] at the end', lambda: SRC + '\n]'),
    ('single quotes', lambda: SRC.replace('"', "'")),
    ('curly quotes', lambda: broken('"name": "Table top"', '“name”: “Table top”')),
    ('unquoted keys', lambda: broken('"name": "Table top"', 'name: "Table top"')),
    ('missing colon', lambda: broken('"name": "Table top"', '"name" "Table top"')),
    ('= instead of :', lambda: broken('"grain": "x"', '"grain" = "x"')),
    ('Python literals', lambda: SRC.replace('"tabs": 2', '"tabs": 2, "flag": True').replace('"tabs": 3', '"tabs": 3, "flag": None')),
    ('key lost its closing quote', lambda: broken('"name": "Table top"', '"name: "Table top"')),
    ('key lost its opening quote', lambda: broken('"name": "Table top"', 'name": "Table top"')),
    ('value lost its opening quote', lambda: broken('"name": "Table top"', '"name": Table top"')),
    ('value lost its closing quote', lambda: broken('"name": "Table top",', '"name": "Table top,')),
    ('list lost its [', lambda: broken('[0, 732, 0]', '0, 732, 0]')),
    ('list lost its ]', lambda: broken('"position": [0, 732, 0],', '"position": [0, 732, 0,')),
    ('object lost its {', lambda: broken('\n    },\n    {', '\n    },\n    ')),
]


@pytest.mark.parametrize('name,make', EXACT, ids=[c[0] for c in EXACT])
def test_repairs_back_to_the_original(name, make):
    data, changes = fix(make())
    expected = json.loads(SRC)
    if name == 'Python literals':
        expected = parse(SRC.replace('"tabs": 2', '"tabs": 2, "flag": true').replace('"tabs": 3', '"tabs": 3, "flag": null'))
    assert data == expected
    assert changes and all(c['line'] >= 1 and c['message'] for c in changes)


def test_unterminated_string_and_numbers():
    data, changes = fix(broken('"name": "Table top",', '"name": "Table top\n').replace('"length": 1200', '"length": +1200'))
    assert data['boards'][0]['name'] == 'Table top' and data['product']['overall']['length'] == 1200
    assert {'Closed a string that was never closed', 'Added a missing comma'} <= {c['message'] for c in changes}


def test_keeps_formatting_and_comments():
    text = broken('"name": "Table top",', '"name": "Table top" // the top board')
    fixed, _ = repair_json(text, parse)
    assert '// the top board' in fixed and fixed.count('\n') == text.count('\n')
    assert fixed.replace(',', '') == text.replace(',', '')        # only the missing comma was added


def test_valid_or_hopeless_input_is_not_touched():
    assert repair_json(SRC, parse) is None                      # nothing to repair
    assert repair_json('[1, 2, 3', parse) is None               # repaired, but not a design object
    assert repair_json('hello there', parse) is None


def test_compiler_offers_the_repair_as_a_safe_fix():
    res = compile_source(broken('\n    },\n    {', '\n    }\n    {'), run_production=False)
    d = res['diagnostics'][0]
    assert d['code'] == 'JSON_SYNTAX' and d['fixes'][0]['kind'] == 'repair_json' and d['fixes'][0]['safe']
    assert compile_source(d['fixes'][0]['source'], run_production=False)['ok']
