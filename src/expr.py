# src/expr.py
# Minimal Pratt-style expression parser for Loom expressions.
# Precedence (highest → lowest):
#   prefix: not, +, -
#   *, /
#   +, -
#   range: ..
#   comparisons: <, <=, >, >=
#   equality: ==, !=
#   and
#   or

from __future__ import annotations
import re

TOK_REGEX = re.compile(
    r"""\s*(?:
    (?P<number>\d+(\.\d+)?)|
    (?P<string>"([^"\\]|\\.)*")|
    (?P<op>==|!=|<=|>=|\.\.|[()+\-*/<>])|
    (?P<kw>\b(?:and|or|not|true|false)\b)|
    (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
    )""", re.VERBOSE | re.IGNORECASE
)

def _unescape(s: str) -> str:
    s = s[1:-1]  # drop quotes
    return bytes(s, "utf-8").decode("unicode_escape")

class Lexer:
    def __init__(self, text: str):
        self.text = text or ""
        self.pos = 0
        self.tokens = []
        while self.pos < len(self.text):
            m = TOK_REGEX.match(self.text, self.pos)
            if not m:
                raise SyntaxError(f"Bad token at {self.pos}: {self.text[self.pos:self.pos+10]!r}")
            self.pos = m.end(0)
            if m.lastgroup == "number":
                val = m.group("number")
                if "." in val:
                    self.tokens.append(("number", float(val)))
                else:
                    self.tokens.append(("number", int(val)))
            elif m.lastgroup == "string":
                self.tokens.append(("string", _unescape(m.group("string"))))
            elif m.lastgroup == "op":
                self.tokens.append(("op", m.group("op")))
            elif m.lastgroup == "kw":
                kw = m.group("kw").lower()
                self.tokens.append(("kw", kw))
            elif m.lastgroup == "ident":
                self.tokens.append(("ident", m.group("ident")))
        self.tokens.append(("eof", None))
        self.i = 0

    def peek(self):
        return self.tokens[self.i]

    def pop(self, *kinds):
        tok = self.peek()
        if kinds and tok[0] not in kinds:
            raise SyntaxError(f"Expected {kinds}, got {tok}")
        self.i += 1
        return tok

BP = {
    "or": 10,
    "and": 20,
    "==": 30, "!=": 30,
    "<": 40, "<=": 40, ">": 40, ">=": 40,
    "..": 45,           # tighter than comparisons, looser than +,*
    "+": 50, "-": 50,
    "*": 60, "/": 60,
}

PREFIX = {"not", "+", "-"}

class Parser:
    def __init__(self, text: str):
        self.lx = Lexer(text)

    def parse(self):
        expr = self.parse_bp(0)
        if self.lx.peek()[0] != "eof":
            raise SyntaxError("Unexpected trailing tokens")
        return expr

    def nud(self, tok):
        t, v = tok
        if t == "number":
            return {"type": "Number", "value": v}
        if t == "string":
            return {"type": "String", "value": v}
        if t == "kw" and v in ("true","false"):
            return {"type": "Boolean", "value": v == "true"}
        if t == "ident":
            return {"type": "Identifier", "name": v}
        if t == "op" and v == "(":
            e = self.parse_bp(0)
            self.lx.pop("op")  # ')'
            return e
        if (t == "kw" and v in PREFIX) or (t == "op" and v in ("+","-")):
            op = v
            if t == "op":  # unify +/-
                op = v
            return {"type":"Unary","op": op, "expr": self.parse_bp(100)}
        raise SyntaxError(f"Unexpected token: {tok}")

    def led(self, left, tok):
        t, v = tok
        if t == "op" and v in ("+","-","*","/","<","<=",">",">=","==","!=",".."):
            rbp = BP[v]
            right = self.parse_bp(rbp + (0 if v == ".." else 1))
            if v == "..":
                return {"type":"Range", "start": left, "end": right, "inclusive": True}
            return {"type":"Binary","op": v, "left": left, "right": right}
        if t == "kw" and v in ("and","or"):
            rbp = BP[v]
            right = self.parse_bp(rbp + 1)
            return {"type":"Binary","op": v, "left": left, "right": right}
        raise SyntaxError(f"Unexpected infix: {tok}")

    def parse_bp(self, min_bp):
        tok = self.lx.pop()
        left = self.nud(tok)
        while True:
            t, v = self.lx.peek()
            if t == "eof":
                break
            if t == "kw" and v in ("and","or"):
                op = v
                lbp = BP[op]
                if lbp < min_bp: break
                self.lx.pop()
                left = self.led(left, ("kw", op))
                continue
            if t == "op" and v in BP:
                lbp = BP[v]
                if lbp < min_bp: break
                self.lx.pop()
                left = self.led(left, ("op", v))
                continue
            break
        return left

def parse_expr(text: str):
    return Parser(text or "").parse()
