"""
Repair the JSON syntax mistakes AIs make, keeping the author's formatting.

`repair_json(text)` walks the text like a JSON parser that never gives up: it keeps a stack of open { / [ and
what each one expects next (key, colon, value, comma), and when the next token does not fit it makes the smallest
edit that does: a missing comma or colon is inserted right after the previous token, a bracket closed with the
wrong character is corrected, a missing } or ] is inserted where the structure shows it belongs (or appended at the
end of a truncated reply), stray closers and characters are dropped, ' and curly quotes become ", unquoted keys
and words are quoted, Python / JavaScript literals become JSON. Whitespace and comments are copied through, so
line numbers stay meaningful.

Returns (repaired_text, changes) where changes is [{'line', 'message'}], or None when the result still does not
parse to a JSON object. The caller decides whether to apply it; nothing here guesses at design content.
"""
import json
import re

_NUMBER = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_WORD = re.compile(r'[A-Za-z_$][\w$\-]*')
_UNOPENED_KEY = re.compile(r'[^"\n:{}\[\],]*"(?=[ \t]*[:=])')          # name": ...      (opening quote left out)
_UNOPENED_VALUE = re.compile(r'[^"\n:{}\[\]]*"(?=[ \t]*(?:[,}\]]|\r?\n|$))')   # ...: Table top",
_LITERALS = {'true': 'true', 'false': 'false', 'null': 'null', 'True': 'true', 'False': 'false', 'None': 'null',
             'TRUE': 'true', 'FALSE': 'false', 'NULL': 'null', 'undefined': 'null', 'NaN': 'null', 'Infinity': 'null'}
# opening quote -> the characters that may close it (curly quotes are often closed with a straight one)
_QUOTES = {'"': '"', "'": "'", '“': '”“"', '”': '”“"', '‘': "’‘'", '’': "’‘'"}
_CLOSE = {'{': '}', '[': ']'}
_OPEN = {'}': '{', ']': '['}


class _Box:
    """An open { or [ : what it expects next and where its last complete token ended in the output."""
    def __init__(self, kind, end):
        self.kind, self.state, self.end, self.comma = kind, ('key' if kind == '{' else 'value'), end, False
        self.last = None        # [ : kind of the last item ('obj' / 'scalar'), to tell what a stray key means
        self.vstart = None      # { : where the current value started, to add a [ that was left out


def repair_json(text, parse=json.loads):
    out, changes, stack = [], [], []
    i, n, line = 0, len(text), 1
    root = {'started': False, 'closed_at': None}

    def note(msg, at=None):
        changes.append({'line': at or line, 'message': msg})

    def insert(box, s, msg):
        """Insert s right after the box's last complete token (before any whitespace / comment / comma)."""
        out.insert(box.end, s)
        for b in stack:
            if b.end >= box.end and b is not box:
                b.end += 1
        box.end += 1
        note(msg)

    def finish_value(kind='scalar'):
        if stack:
            top = stack[-1]
            top.state, top.end, top.comma, top.last = 'next', len(out), False, kind

    def close_top(closer_char=None, msg=None):
        """Close the innermost box (completing a dangling key / value first)."""
        top = stack[-1]
        if top.kind == '{' and top.state == 'colon':
            insert(top, ': null', 'Gave a key without a value the value null')
        elif top.kind == '{' and top.state == 'value':
            insert(top, ' null', 'Gave a key without a value the value null')
        if closer_char is None:
            insert(top, _CLOSE[top.kind], msg or f'Added a missing {_CLOSE[top.kind]}')
            pos = top.end - 1
        else:
            out.append(closer_char)
            pos = len(out) - 1
        comma_after = top.comma
        stack.pop()
        if not stack:
            root['closed_at'] = pos
            return
        parent = stack[-1]
        parent.state, parent.end, parent.comma, parent.last = 'next', pos + 1, False, 'obj' if top.kind == '{' else 'arr'
        if comma_after and closer_char is None:          # the comma typed after the last item now separates parents
            parent.state, parent.comma = ('key' if parent.kind == '{' else 'value'), True

    def reopen_root():
        """Content after the root closed: the closer was an extra one; take it back out."""
        pos = root['closed_at']
        kind = _OPEN[out[pos]]
        out[pos] = ''
        box = _Box(kind, pos)
        box.state = 'next'
        stack.append(box)
        root['closed_at'] = None
        note(f'Removed an extra {_CLOSE[kind]} that ended the design too early')

    def before_value(kind, role=None):
        """Make room for a value / key token of `kind` ('str', 'num', 'word', 'open'); `role` is what the text after a
        string says it is ('key' before a colon, 'item' before , or ]). False = drop the token."""
        if not stack:
            if root['closed_at'] is not None:
                reopen_root()
            elif root['started']:
                return False
            else:
                return True
        top = stack[-1]
        if top.kind == '[':
            if role == 'key':
                if top.last in (None, 'obj'):            # a list of objects: this object's { was left out
                    if top.state == 'next':
                        insert(top, ',', 'Added a missing comma')
                    out.append('{')
                    stack.append(_Box('{', len(out)))
                    note('Added a missing {')
                    return True
                if len(stack) > 1 and stack[-2].kind == '{':  # a list of values that was never closed
                    close_top()
                    return before_value(kind, role)
            if top.state == 'next':
                insert(top, ',', 'Added a missing comma')
                top.state = 'value'
            return True
        if top.state == 'key' and top.comma and top.vstart is not None and (kind == 'num' or role == 'item'):
            # values after a comma where a key belongs: the list they belong to lost its [
            out.insert(top.vstart, '[')
            for b in stack:
                if b.end >= top.vstart:
                    b.end += 1
            note('Added a missing [')
            arr = _Box('[', top.end)
            arr.state, arr.comma, arr.last = 'value', True, 'scalar'
            top.state = 'value'
            stack.append(arr)
            return True
        if top.state == 'next':
            insert(top, ',', 'Added a missing comma')
            top.state = 'key'
        if top.state == 'colon':
            insert(top, ':', 'Added a missing colon')
            top.state = 'value'
        if top.state == 'value':
            top.vstart = len(out)
        if top.state == 'key' and kind == 'open':
            # an object where a key belongs: the previous object was never closed
            if len(stack) > 1 and stack[-2].kind == '[':
                close_top()
                return before_value(kind)
            return False
        return True

    def role_after(j):
        while j < n and text[j] in ' \t\r\n':
            j += 1
        return 'key' if j < n and text[j] in ':=' else 'item' if j < n and text[j] in ',]' else None

    def emit_string(token, role, at):
        """Place a string token as a key or a value. False = it was dropped."""
        if not before_value('str', role):
            note('Removed text after the end of the design', at)
            return False
        out.append(token)
        top = stack[-1] if stack else None
        if top and top.kind == '{' and top.state == 'key':
            top.state, top.end = 'colon', len(out)
        else:
            root['started'] = True
            finish_value()
        return True

    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            out.append(c)
            line += c == '\n'
            i += 1
            continue
        if text.startswith('//', i) or text.startswith('/*', i):          # comments are kept (the parser skips them)
            if text[i + 1] == '/':
                j = text.find('\n', i)
                j = n if j < 0 else j
            else:
                j = text.find('*/', i + 2)
                j = n if j < 0 else j + 2
            out.append(text[i:j])
            line += text.count('\n', i, j)
            i = j
            continue

        if c in _QUOTES:
            close = _QUOTES[c]
            buf, j, start_line = [], i + 1, line
            closed = False
            while j < n:
                ch = text[j]
                if ch == '\\' and j + 1 < n:
                    buf.append(text[j:j + 2])
                    j += 2
                    continue
                if ch in close:
                    closed = True
                    j += 1
                    break
                if ch == '\n':
                    break
                buf.append('\\"' if ch == '"' else '\\t' if ch == '\t' else ch)
                j += 1
            if c != '"':
                note('Replaced non-standard quotes with "', start_line)
            content = ''.join(buf)
            top = stack[-1] if stack else None
            km = re.match(r'^(.*?)\s*:\s*$', content, re.S)
            if closed and km and km.group(1) and top and top.kind == '{' and top.state in ('key', 'next') \
                    and j < n and text[j] not in ' \t\r\n,}:]':
                # "name: "Table top" -- the key lost its closing quote; the quote we stopped at opens the value
                note('Closed a key that was missing its closing quote', start_line)
                if emit_string('"' + km.group(1) + '"', 'key', start_line):
                    out.append(':')
                    stack[-1].state = 'value'
                i = j - 1
                continue
            if not closed:
                note('Closed a string that was never closed', start_line)
                comma = text.rfind(',', i + 1, j)
                if comma >= 0 and not text[comma + 1:j].strip():      # "Table top,  <- the comma was the separator
                    content = text[i + 1:comma].rstrip().replace('\t', '\\t')
                    if c != '"':                                       # a " inside ' / curly quotes is content
                        content = content.replace('"', '\\"')
                    j = comma
            i = j
            emit_string('"' + content + '"', role_after(j), start_line)
            continue

        if c.isdigit() or (c in '-+.' and i + 1 < n and (text[i + 1].isdigit() or text[i + 1] == '.')):
            m = _NUMBER.match(text, i)
            raw = m.group(0)
            num = raw.lstrip('+')
            num = re.sub(r'^(-?)\.', r'\g<1>0.', num)
            num = re.sub(r'\.(?=$|[eE])', '', num)
            num = re.sub(r'^(-?)0+(?=\d)', r'\1', num)
            if num != raw:
                note(f'Wrote the number {raw} as {num}')
            i = m.end()
            if not before_value('num'):
                continue
            top = stack[-1] if stack else None
            if top and top.kind == '{' and top.state == 'key':           # a number used as a key
                out.append(f'"{num}"')
                note('Quoted a key')
                top.state, top.end = 'colon', len(out)
                continue
            out.append(num)
            root['started'] = True
            finish_value()
            continue

        top = stack[-1] if stack else None
        if top and (c.isalpha() or c in '_$'):
            pat = _UNOPENED_KEY if top.kind == '{' and top.state in ('key', 'next') else _UNOPENED_VALUE
            um = pat.match(text, i)
            if um and um.group(0)[:-1].strip():
                # Table top",  /  name": ...  -- the opening quote was left out
                note('Added a missing opening quote')
                content = json.dumps(um.group(0)[:-1].rstrip())
                i = um.end()
                emit_string(content, role_after(i), line)
                continue

        m = _WORD.match(text, i)
        if m:
            word = m.group(0)
            i = m.end()
            if not before_value('word'):
                continue
            top = stack[-1] if stack else None
            if top and top.kind == '{' and top.state == 'key':
                out.append(json.dumps(word))
                note(f'Quoted the key {word}')
                top.state, top.end = 'colon', len(out)
                continue
            if word in _LITERALS:
                if _LITERALS[word] != word:
                    note(f'Wrote {word} as {_LITERALS[word]}')
                out.append(_LITERALS[word])
            else:
                out.append(json.dumps(word))
                note(f'Quoted the word {word}')
            root['started'] = True
            finish_value()
            continue

        i += 1
        if c in '{[':
            if not before_value('open'):
                note(f'Removed a misplaced {c}')
                continue
            root['started'] = True
            if stack and stack[-1].kind == '[':
                stack[-1].last = 'obj' if c == '{' else 'arr'
            out.append(c)
            stack.append(_Box(c, len(out)))
            continue
        if c in '}]':
            if not stack:
                note(f'Removed an extra {c}')
                continue
            if c == _CLOSE[stack[-1].kind]:
                close_top(c)
                continue
            if any(b.kind == _OPEN[c] for b in stack[:-1]):          # closes an outer box: inner ones were left open
                while stack[-1].kind != _OPEN[c]:
                    close_top()
                close_top(c)
            else:
                note(f'Replaced {c} with {_CLOSE[stack[-1].kind]} to match its opening {stack[-1].kind}')
                close_top(_CLOSE[stack[-1].kind])
            continue
        if c in ',;':
            if not stack and root['closed_at'] is not None:
                reopen_root()
            top = stack[-1] if stack else None
            if top and top.state == 'next':
                out.append(',')
                if c == ';':
                    note('Replaced ; with ,')
                top.state, top.comma = ('key' if top.kind == '{' else 'value'), True
            elif top and top.kind == '{' and top.state == 'colon':
                insert(top, ': null', 'Gave a key without a value the value null')
                out.append(',')
                top.state, top.comma = 'key', True
            else:
                note('Removed an extra comma')
            continue
        if c in ':=':
            top = stack[-1] if stack else None
            if top and top.kind == '{' and top.state == 'colon':
                out.append(':')
                top.state = 'value'
                if c == '=':
                    note('Replaced = with :')
            else:
                note(f'Removed a misplaced {c}')
            continue
        note(f'Removed the unexpected character {c!r}')

    while stack:
        depth = len(stack) - 1
        top = stack[-1]
        if top.kind == '{' and top.state in ('colon', 'value'):
            close_top()                      # completes the value, then inserts the closer after it
            continue
        out.append('\n' + '  ' * depth + _CLOSE[top.kind])
        note(f'Added a missing {_CLOSE[top.kind]} at the end')
        comma_after = top.comma
        stack.pop()
        if stack:
            finish_value()
            stack[-1].comma = comma_after

    fixed = ''.join(out)
    try:
        data = parse(fixed)
    except ValueError:
        return None
    if not isinstance(data, dict) or not changes:
        return None
    return fixed, changes


def summarize(changes, limit=6):
    """'Added 2 missing commas (lines 4, 9); closed 1 string (line 7)' style summary, most frequent first."""
    groups = {}
    for ch in changes:
        groups.setdefault(ch['message'], []).append(ch['line'])
    parts = []
    for msg, lines in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:limit]:
        where = ', '.join(str(x) for x in sorted(set(lines))[:5]) + ('…' if len(set(lines)) > 5 else '')
        parts.append(f"{msg}{f' ×{len(lines)}' if len(lines) > 1 else ''} (line{'s' if len(set(lines)) > 1 else ''} {where})")
    return '; '.join(parts)
