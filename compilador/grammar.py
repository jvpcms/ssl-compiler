"""Gramática efetivamente usada pelo compilador (ver README, seção 2).

Segue a recomendação do cap. 4: uma enumeração para os não terminais (N) e
outra para as regras (R). O número da regra é o valor da enumeração, e é esse
número que aparece na Tabela de Ação (redução = -regra) e em Semantics().

Os terminais são os próprios tokens do analisador léxico da VC (TokenKind).
Os não terminais recebem valores a partir de NT_BASE, de modo que um símbolo
s é terminal se, e somente se, s < NT_BASE.

Diferenças em relação à gramática oficial (justificadas no README):
  - regra 0 (gramática aumentada): P' -> P '$'
  - marcadores semânticos NB (cap. 5), NF/MF (caps. 6 e 7), MC (cap. 6) e
    MW (cap. 7, usado aqui para saber se break/continue estão num laço)
  - ID (sem verificação de escopo) no acesso a campo LV '.' ID (cap. 5)
  - comando 'return' E ';'
"""
from __future__ import annotations

from enum import IntEnum

from lexer import TokenKind as T

NT_BASE = 100


class N(IntEnum):
    """Não terminais (t_nont)."""
    P_ = NT_BASE        # P' (símbolo inicial da gramática aumentada)
    P = 101
    LDE = 102
    DE = 103
    T = 104
    DT = 105
    DC = 106
    DF = 107
    LP = 108
    B = 109
    LDV = 110
    LS = 111
    DV = 112
    LI = 113
    S = 114
    E = 115
    L = 116
    R = 117
    Y = 118
    F = 119
    LE = 120
    LV = 121
    IDD = 122
    IDU = 123
    ID = 124
    TRUE = 125
    FALSE = 126
    CHR = 127
    STR = 128
    NUM = 129
    NB = 130
    NF = 131
    MF = 132
    MC = 133
    MW = 134


class R(IntEnum):
    """Regras sintáticas (t_rule). O valor é o número da regra."""
    START = 0
    P = 1
    LDE_REC = 2
    LDE = 3
    DE_DF = 4
    DE_DT = 5
    T_INTEGER = 6
    T_CHAR = 7
    T_BOOLEAN = 8
    T_STRING = 9
    T_IDU = 10
    DT_ARRAY = 11
    DT_STRUCT = 12
    DT_ALIAS = 13
    DC_REC = 14
    DC = 15
    DF = 16
    LP_REC = 17
    LP = 18
    B = 19
    LDV_REC = 20
    LDV = 21
    LS_REC = 22
    LS = 23
    DV = 24
    LI_REC = 25
    LI = 26
    S_IF = 27
    S_IF_ELSE = 28
    S_WHILE = 29
    S_DO_WHILE = 30
    S_BLOCK = 31
    S_ASSIGN = 32
    S_BREAK = 33
    S_CONTINUE = 34
    S_RETURN = 35
    E_AND = 36
    E_OR = 37
    E_L = 38
    L_LT = 39
    L_GT = 40
    L_LE = 41
    L_GE = 42
    L_EQ = 43
    L_NE = 44
    L_R = 45
    R_PLUS = 46
    R_MINUS = 47
    R_Y = 48
    Y_TIMES = 49
    Y_DIVIDE = 50
    Y_F = 51
    F_LV = 52
    F_PRE_INC = 53
    F_PRE_DEC = 54
    F_POS_INC = 55
    F_POS_DEC = 56
    F_PAREN = 57
    F_CALL = 58
    F_MINUS = 59
    F_NOT = 60
    F_TRUE = 61
    F_FALSE = 62
    F_CHR = 63
    F_STR = 64
    F_NUM = 65
    LE_REC = 66
    LE = 67
    LV_FIELD = 68
    LV_INDEX = 69
    LV_IDU = 70
    IDD = 71
    IDU = 72
    ID = 73
    TRUE = 74
    FALSE = 75
    CHR = 76
    STR = 77
    NUM = 78
    NB = 79
    NF = 80
    MF = 81
    MC = 82
    MW = 83


# RULES[r] = (lado esquerdo, lado direito). A ordem é a da enumeração R.
RULES: list[tuple[N, tuple[int, ...]]] = [
    (N.P_,  (N.P, T.EOF)),                                              # START
    (N.P,   (N.LDE,)),
    (N.LDE, (N.LDE, N.DE)),
    (N.LDE, (N.DE,)),
    (N.DE,  (N.DF,)),
    (N.DE,  (N.DT,)),
    (N.T,   (T.INTEGER,)),
    (N.T,   (T.CHAR,)),
    (N.T,   (T.BOOLEAN,)),
    (N.T,   (T.STRING,)),
    (N.T,   (N.IDU,)),
    (N.DT,  (T.TYPE, N.IDD, T.EQUALS, T.ARRAY, T.LEFT_SQUARE, N.NUM, T.RIGHT_SQUARE,
             T.OF, N.T)),                                               # DT_ARRAY
    (N.DT,  (T.TYPE, N.IDD, T.EQUALS, T.STRUCT, N.NB, T.LEFT_BRACES, N.DC,
             T.RIGHT_BRACES)),                                          # DT_STRUCT
    (N.DT,  (T.TYPE, N.IDD, T.EQUALS, N.T)),                            # DT_ALIAS
    (N.DC,  (N.DC, T.SEMI_COLON, N.LI, T.COLON, N.T)),
    (N.DC,  (N.LI, T.COLON, N.T)),
    (N.DF,  (T.FUNCTION, N.IDD, N.NF, T.LEFT_PARENTHESIS, N.LP, T.RIGHT_PARENTHESIS,
             T.COLON, N.T, N.MF, N.B)),                                 # DF
    (N.LP,  (N.LP, T.COMMA, N.IDD, T.COLON, N.T)),
    (N.LP,  (N.IDD, T.COLON, N.T)),
    (N.B,   (T.LEFT_BRACES, N.LDV, N.LS, T.RIGHT_BRACES)),
    (N.LDV, (N.LDV, N.DV)),
    (N.LDV, (N.DV,)),
    (N.LS,  (N.LS, N.S)),
    (N.LS,  (N.S,)),
    (N.DV,  (T.VAR, N.LI, T.COLON, N.T, T.SEMI_COLON)),
    (N.LI,  (N.LI, T.COMMA, N.IDD)),
    (N.LI,  (N.IDD,)),
    (N.S,   (T.IF, T.LEFT_PARENTHESIS, N.E, T.RIGHT_PARENTHESIS, N.S)),  # S_IF
    (N.S,   (T.IF, T.LEFT_PARENTHESIS, N.E, T.RIGHT_PARENTHESIS, N.S, T.ELSE,
             N.S)),                                                     # S_IF_ELSE
    (N.S,   (T.WHILE, N.MW, T.LEFT_PARENTHESIS, N.E, T.RIGHT_PARENTHESIS, N.S)),
    (N.S,   (T.DO, N.MW, N.S, T.WHILE, T.LEFT_PARENTHESIS, N.E, T.RIGHT_PARENTHESIS,
             T.SEMI_COLON)),                                            # S_DO_WHILE
    (N.S,   (N.NB, N.B)),                                               # S_BLOCK
    (N.S,   (N.LV, T.EQUALS, N.E, T.SEMI_COLON)),                       # S_ASSIGN
    (N.S,   (T.BREAK, T.SEMI_COLON)),
    (N.S,   (T.CONTINUE, T.SEMI_COLON)),
    (N.S,   (T.RETURN, N.E, T.SEMI_COLON)),                             # S_RETURN
    (N.E,   (N.E, T.AND, N.L)),
    (N.E,   (N.E, T.OR, N.L)),
    (N.E,   (N.L,)),
    (N.L,   (N.L, T.LESS_THAN, N.R)),
    (N.L,   (N.L, T.GREATER_THAN, N.R)),
    (N.L,   (N.L, T.LESS_OR_EQUAL, N.R)),
    (N.L,   (N.L, T.GREATER_OR_EQUAL, N.R)),
    (N.L,   (N.L, T.EQUAL_EQUAL, N.R)),
    (N.L,   (N.L, T.NOT_EQUAL, N.R)),
    (N.L,   (N.R,)),
    (N.R,   (N.R, T.PLUS, N.Y)),
    (N.R,   (N.R, T.MINUS, N.Y)),
    (N.R,   (N.Y,)),
    (N.Y,   (N.Y, T.TIMES, N.F)),
    (N.Y,   (N.Y, T.DIVIDE, N.F)),
    (N.Y,   (N.F,)),
    (N.F,   (N.LV,)),
    (N.F,   (T.PLUS_PLUS, N.LV)),
    (N.F,   (T.MINUS_MINUS, N.LV)),
    (N.F,   (N.LV, T.PLUS_PLUS)),
    (N.F,   (N.LV, T.MINUS_MINUS)),
    (N.F,   (T.LEFT_PARENTHESIS, N.E, T.RIGHT_PARENTHESIS)),
    (N.F,   (N.IDU, N.MC, T.LEFT_PARENTHESIS, N.LE, T.RIGHT_PARENTHESIS)),  # F_CALL
    (N.F,   (T.MINUS, N.F)),
    (N.F,   (T.NOT, N.F)),
    (N.F,   (N.TRUE,)),
    (N.F,   (N.FALSE,)),
    (N.F,   (N.CHR,)),
    (N.F,   (N.STR,)),
    (N.F,   (N.NUM,)),
    (N.LE,  (N.LE, T.COMMA, N.E)),
    (N.LE,  (N.E,)),
    (N.LV,  (N.LV, T.DOT, N.ID)),                                       # LV_FIELD
    (N.LV,  (N.LV, T.LEFT_SQUARE, N.E, T.RIGHT_SQUARE)),                # LV_INDEX
    (N.LV,  (N.IDU,)),
    (N.IDD, (T.ID,)),
    (N.IDU, (T.ID,)),
    (N.ID,  (T.ID,)),
    (N.TRUE,  (T.TRUE,)),
    (N.FALSE, (T.FALSE,)),
    (N.CHR, (T.CHARACTER,)),
    (N.STR, (T.STRINGVAL,)),
    (N.NUM, (T.NUMERAL,)),
    (N.NB,  ()),
    (N.NF,  ()),
    (N.MF,  ()),
    (N.MC,  ()),
    (N.MW,  ()),
]

assert len(RULES) == len(R), "RULES e R devem ter o mesmo tamanho"

# Tabelas auxiliares da figura 3.18: comprimento e lado esquerdo de cada regra.
Len = [len(rhs) for _, rhs in RULES]
Left = [left for left, _ in RULES]

# Terminais da gramática: todos os tokens, exceto UNKNOWN (só existe no modo tolerante).
TERMINALS = [t for t in T if t != T.UNKNOWN]
NONTERMINALS = list(N)


def is_terminal(sym: int) -> bool:
    return sym < NT_BASE


def symbol_name(sym: int) -> str:
    """Nome legível de um símbolo, como na gramática ('if', ';', Id, LDV, ...)."""
    if not is_terminal(sym):
        return "P'" if sym == N.P_ else N(sym).name
    return TERMINAL_TEXT[T(sym)]


# Representação textual dos terminais (mensagens de erro e listagem da gramática).
TERMINAL_TEXT: dict[T, str] = {k: f"'{k.name.lower()}'" for k in T if k <= T.WHILE}
TERMINAL_TEXT.update({
    T.COLON: "':'", T.SEMI_COLON: "';'", T.COMMA: "','", T.EQUALS: "'='",
    T.LEFT_SQUARE: "'['", T.RIGHT_SQUARE: "']'", T.LEFT_BRACES: "'{'",
    T.RIGHT_BRACES: "'}'", T.LEFT_PARENTHESIS: "'('", T.RIGHT_PARENTHESIS: "')'",
    T.AND: "'&&'", T.OR: "'||'", T.LESS_THAN: "'<'", T.GREATER_THAN: "'>'",
    T.LESS_OR_EQUAL: "'<='", T.GREATER_OR_EQUAL: "'>='", T.NOT_EQUAL: "'!='",
    T.EQUAL_EQUAL: "'=='", T.PLUS: "'+'", T.PLUS_PLUS: "'++'", T.MINUS: "'-'",
    T.MINUS_MINUS: "'--'", T.TIMES: "'*'", T.DIVIDE: "'/'", T.DOT: "'.'",
    T.NOT: "'!'", T.CHARACTER: "c", T.NUMERAL: "n", T.STRINGVAL: "s", T.ID: "Id",
    T.EOF: "'$'", T.UNKNOWN: "?",
})


def rule_text(r: int) -> str:
    left, rhs = RULES[r]
    body = " ".join(symbol_name(s) for s in rhs) or "ϵ"
    return f"{symbol_name(left)} -> {body}"
