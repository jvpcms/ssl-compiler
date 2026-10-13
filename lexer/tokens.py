"""Enumeração de tokens (token principal).

Segue a convenção da apostila: as palavras reservadas ocupam os primeiros
valores da enumeração, em ORDEM ALFABÉTICA. Isso permite que a busca binária
em KEYWORDS devolva diretamente o valor do token (a posição no vetor é o token).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class TokenKind(IntEnum):
    # ---- palavras reservadas (ordem alfabética, começando em 0) ----
    ARRAY = 0
    BOOLEAN = 1
    BREAK = 2
    CHAR = 3
    CONTINUE = 4
    DO = 5
    ELSE = 6
    FALSE = 7
    FUNCTION = 8
    IF = 9
    INTEGER = 10
    OF = 11
    RETURN = 12             # extensão da VF (ver compilador/README.md)
    STRING = 13
    STRUCT = 14
    TRUE = 15
    TYPE = 16
    VAR = 17
    WHILE = 18
    # ---- símbolos ----
    COLON = 19              # :
    SEMI_COLON = 20         # ;
    COMMA = 21              # ,
    EQUALS = 22             # =
    LEFT_SQUARE = 23        # [
    RIGHT_SQUARE = 24       # ]
    LEFT_BRACES = 25        # {
    RIGHT_BRACES = 26       # }
    LEFT_PARENTHESIS = 27   # (
    RIGHT_PARENTHESIS = 28  # )
    AND = 29                # &&
    OR = 30                 # ||
    LESS_THAN = 31          # <
    GREATER_THAN = 32       # >
    LESS_OR_EQUAL = 33      # <=
    GREATER_OR_EQUAL = 34   # >=
    NOT_EQUAL = 35          # !=
    EQUAL_EQUAL = 36        # ==
    PLUS = 37               # +
    PLUS_PLUS = 38          # ++
    MINUS = 39              # -
    MINUS_MINUS = 40        # --
    TIMES = 41              # *
    DIVIDE = 42             # /
    DOT = 43                # .
    NOT = 44                # !
    # ---- tokens regulares (classes infinitas: precisam de token secundário) ----
    CHARACTER = 45          # c  = ''' . any . '''
    NUMERAL = 46            # n  = digito . digito*
    STRINGVAL = 47          # s  = '"' . any* . '"'
    ID = 48                 # Id = letra . (letra + digito)*
    # ---- fim de arquivo e desconhecido ----
    EOF = 49
    UNKNOWN = 50


# Vetor de palavras reservadas ORDENADO. KEYWORDS[i] corresponde a TokenKind(i).
KEYWORDS: tuple[str, ...] = (
    "array", "boolean", "break", "char", "continue", "do", "else", "false",
    "function", "if", "integer", "of", "return", "string", "struct", "true", "type",
    "var", "while",
)

# Garantia estrutural: a ordem do vetor casa com a enumeração.
assert list(KEYWORDS) == sorted(KEYWORDS), "KEYWORDS deve estar em ordem alfabética"
assert all(TokenKind(i).name.lower() == kw for i, kw in enumerate(KEYWORDS)), \
    "KEYWORDS[i] deve corresponder a TokenKind(i)"

# Símbolos de um caractere que não são prefixo de nenhum outro símbolo.
SINGLE_CHAR_SYMBOLS: dict[str, TokenKind] = {
    ":": TokenKind.COLON,
    ";": TokenKind.SEMI_COLON,
    ",": TokenKind.COMMA,
    "[": TokenKind.LEFT_SQUARE,
    "]": TokenKind.RIGHT_SQUARE,
    "{": TokenKind.LEFT_BRACES,
    "}": TokenKind.RIGHT_BRACES,
    "(": TokenKind.LEFT_PARENTHESIS,
    ")": TokenKind.RIGHT_PARENTHESIS,
    "*": TokenKind.TIMES,
    "/": TokenKind.DIVIDE,
    ".": TokenKind.DOT,
}

# Símbolos em que o 2º caractere decide o token: (sozinho, com o 2º char, token composto)
# Se "sozinho" é None, o símbolo só existe na forma composta (ex.: '&' só vale em '&&').
TWO_CHAR_SYMBOLS: dict[str, tuple[Optional[TokenKind], str, TokenKind]] = {
    "=": (TokenKind.EQUALS,       "=", TokenKind.EQUAL_EQUAL),
    "<": (TokenKind.LESS_THAN,    "=", TokenKind.LESS_OR_EQUAL),
    ">": (TokenKind.GREATER_THAN, "=", TokenKind.GREATER_OR_EQUAL),
    "!": (TokenKind.NOT,          "=", TokenKind.NOT_EQUAL),
    "+": (TokenKind.PLUS,         "+", TokenKind.PLUS_PLUS),
    "-": (TokenKind.MINUS,        "-", TokenKind.MINUS_MINUS),
    "&": (None,                   "&", TokenKind.AND),
    "|": (None,                   "|", TokenKind.OR),
}


@dataclass(frozen=True)
class Token:
    """Resultado de uma chamada a next_token().

    kind      -- token principal (o terminal da gramática)
    secondary -- token secundário: índice na tabela de nomes (ID) ou na tabela
                 de constantes (NUMERAL, CHARACTER, STRINGVAL). None nos demais.
    lexeme    -- o texto original, guardado apenas para diagnóstico/depuração
    line, col -- posição do início do lexema no arquivo (1-based)
    """
    kind: TokenKind
    secondary: Optional[int]
    lexeme: str
    line: int
    col: int

    def __str__(self) -> str:
        sec = "" if self.secondary is None else f"({self.secondary})"
        return f"{self.kind.name}{sec}"
