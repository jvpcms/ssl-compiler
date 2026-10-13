"""Analisador sintático ascendente la-LR(1) com avaliação de atributos (fig. 4.6)
e o encadeamento das fases: léxico -> sintático (+ escopo e tipos).

A pilha sintática guarda, além do estado, a posição (linha, coluna) do símbolo
de acesso do estado; na redução, a posição do 1º símbolo da regra é entregue
a Semantics() para as mensagens de erro.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from lexer import Lexer, Token, TokenKind

from . import lalr
from .grammar import Left, Len, R, TERMINAL_TEXT
from .lalr import IS_REDUCTION, IS_SHIFT, RULE, col
from .semantics import CompileError, Semantic


@lru_cache(maxsize=1)
def table() -> lalr.Table:
    """A tabela é calculada uma vez por execução a partir da gramática."""
    return lalr.build()


@dataclass
class Result:
    errors: list[CompileError] = field(default_factory=list)
    semantic: Semantic | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


# Nomes dos terminais nas mensagens; os demais aparecem como na gramática.
EXPECTED_TEXT = {**TERMINAL_TEXT, TokenKind.ID: "identificador", TokenKind.NUMERAL: "número",
                 TokenKind.CHARACTER: "caractere", TokenKind.STRINGVAL: "string",
                 TokenKind.EOF: "fim de arquivo"}


def found_text(tok: Token) -> str:
    if tok.kind == TokenKind.EOF:
        return "fim de arquivo"
    if tok.kind in (TokenKind.STRINGVAL, TokenKind.CHARACTER):
        return tok.lexeme                                 # o lexema já tem as aspas
    return f"'{tok.lexeme}'"


def compile_source(source: str) -> Result:
    # ---- léxico: todos os erros léxicos são listados e impedem o sintático
    lx = Lexer(source, strict=False)
    tokens = list(lx.tokens(include_eof=True))
    lexical = [CompileError("léxico", "ERR_LEXICAL", t.line, t.col, t.lexeme)
               for t in tokens if t.kind == TokenKind.UNKNOWN]
    if lexical:
        return Result(lexical)

    # ---- sintático com avaliação de atributos (figura 4.6)
    tb = table()
    Action, FINAL = tb.Action, tb.FINAL
    sem = Semantic(lx.names, lx.consts)
    result = Result(sem.errors, sem)

    stream = iter(tokens)
    nextToken = lambda: next(stream, tokens[-1])          # noqa: E731  (EOF repetido)

    stack: list[tuple[int, int, int]] = []                # (estado, linha, coluna)
    a = nextToken()
    stack.append((0, a.line, a.col))
    q = 0
    visited = [q]                                         # estados vistos com o token a
    while q != FINAL:
        p = Action[q][col(a.kind)]
        if IS_SHIFT(p):
            stack.append((p, a.line, a.col))
            sem.token = a
            a = nextToken()
            visited = []
        elif IS_REDUCTION(p):
            r = RULE(p)
            n = Len[r]
            line, column = (stack[-n][1], stack[-n][2]) if n else (a.line, a.col)
            if n:
                del stack[-n:]
            stack.append((Action[stack[-1][0]][col(Left[r])], line, column))
            sem.pos = (line, column)
            sem.Semantics(R(r))
        else:
            expected = ", ".join(EXPECTED_TEXT[TokenKind(t)] for t in tb.expected(visited))
            sem.errors.append(CompileError(
                "sintático", "ERR_SYNTAX", a.line, a.col,
                f"encontrado {found_text(a)}; esperado: {expected}"))
            break
        q = stack[-1][0]
        visited.append(q)
    return result
