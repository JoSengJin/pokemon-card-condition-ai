"""Line reading for tools/rater_gate.py. Values are never repaired; NFKC is used only to detect broken input."""
import re
import unicodedata

SECOND_CARD = re.compile(r'/\s*(?:front|back)\s*=', re.I)  # another card's 'id/side=' swallowed into this line
SECOND_ZONE = re.compile(r'z\s*\d+\s*[=:]', re.I)  # a second assignment swallowed into one value
PHONE = re.compile(r'[^\s#;=-][^;=]*/[^;=/]+=[^;=]+;box:[^;]*;.+')


def line_pairs(line):
    """([(zone key, value)], whole line readable). An unreadable phone zone keeps its key with value None. From the point
    where a second card starts, nothing is attributed to the first card; a broken zone name drops only that zone."""
    numbered = re.fullmatch(r'(z[0-9]+)\s*=\s*([^#]+)', line)
    if numbered:
        merged = SECOND_ZONE.search(unicodedata.normalize('NFKC', numbered[2]))
        return ([], False) if merged else ([numbered.groups()], True)
    if not PHONE.fullmatch(line):
        return [], False
    head, box, *zones = line.split(';')
    if SECOND_CARD.search(unicodedata.normalize('NFKC', box)):
        return [], False
    pairs, readable = [], True
    for zone in zones:
        area, _, value = zone.partition(':')
        name, seen = (unicodedata.normalize('NFKC', part).strip() for part in (area, value))
        other = name == 'box' or SECOND_CARD.search(name) or SECOND_CARD.search(seen)
        unnamed = not name or '=' in name or ':' in name
        bad = other or unnamed or not seen or ':' in seen or SECOND_ZONE.search(seen)
        if not unnamed and name != 'box':
            pairs.append((f"{head.split('=')[0]}/{area}", None if bad else value))
        readable = readable and not bad
        if other:
            break
    return pairs, readable


def values(text, unread=None):
    """{zone key: value} from 'zN=값' lines or phone lines 'id/side=..;box:..;구역:상태'. '#' lines are comments.

    Without `unread` (the human answer) any other line or a conflicting repeat is refused. With a list (AI files) those
    line numbers are appended and, per zone: values from fully readable lines win; damaged lines only fill zones that no
    readable line has. Different values on the deciding side drop the zone. A zone nobody could read stays as None:
    covered, never equal to an answer, never a conflict.
    """
    seen = {True: {}, False: {}}  # line readable -> zone -> {value: first line number}
    damaged = []
    for number, line in enumerate((l.strip() for l in text.splitlines()), 1):
        if not line or line.startswith('#'):
            continue
        pairs, readable = line_pairs(line)
        if not readable:
            if unread is None:
                raise ValueError(f'읽을 수 없는 줄: {line}')
            damaged.append(number)
        for key, value in pairs:
            seen[readable].setdefault(key, {}).setdefault(value, number)
    out = {}
    for key in {**seen[True], **seen[False]}:
        found = seen[True].get(key) or {v: n for v, n in seen[False][key].items() if v is not None}
        if len(found) > 1:
            if unread is None:
                raise ValueError(f'같은 구역에 다른 값이 두 번 있음: {key}')
            damaged += found.values()
        else:
            out[key] = next(iter(found), None)
    if unread is not None:
        unread += sorted(set(damaged))
    return out


def loose(text):
    """Comparison form for detection only: NFKC, casefold, letters and digits. Never used as a value."""
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def unmatched(text, answer, found):
    """(line numbers, near count): this file points at the answer but is not compared as written. One way only: it can
    block 'no match'; it changes no value and no match count.

    Lines: a line names one of the answer's phone cards ('id/side') but does not start with it exactly as written.
    Near: a zone name, or a value of the same zone, that differs from the answer only in what loose() drops.
    """
    cards = {key.rsplit('/', 1)[0] for key in answer if '/' in key}
    lines = [number for number, line in enumerate(text.splitlines(), 1)
             if any(loose(card) in loose(line) and not line.strip().startswith(card + '=') for card in cards)]
    names = {loose(key) for key in answer}
    near = sum(loose(key) in names if key not in answer else
               value not in (None, answer[key]) and bool(loose(value)) and loose(value) == loose(answer[key])
               for key, value in found.items())
    return lines, near
