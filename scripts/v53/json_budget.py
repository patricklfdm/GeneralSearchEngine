"""Constant-space lexical budget scan; JSON syntax/schema checks remain separate."""
from .membership_model import need


def scan(raw, *, budget_error, balance_error, string_error):
    # Avoid regex backtracking storage proportional to a base64 string's size.
    depth = nodes = at = 0
    while at < len(raw):
        token = raw[at]
        if token == 34:
            nodes += 1; at += 1
            while True:
                end = raw.find(b'"', at); need(end >= 0, string_error)
                back = end - 1
                while back >= at and raw[back] == 92: back -= 1
                if (end - 1 - back) % 2 == 0:
                    at = end + 1; break
                at = end + 1
        elif token in (123, 91): depth += 1; nodes += 1; at += 1
        elif token in (125, 93): depth -= 1; at += 1
        elif token in b' \t\r\n\v\f,:': at += 1
        else:
            nodes += 1; at += 1
            while at < len(raw) and raw[at] not in b' \t\r\n\v\f{}[],:"': at += 1
        need(0 <= depth <= 16 and nodes <= 65536, budget_error)
    need(depth == 0, balance_error)
