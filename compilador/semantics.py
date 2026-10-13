"""Pilha semântica e função Semantics(rule) (caps. 4, 5 e 6).

Semantics() é chamada pelo analisador sintático a cada redução (figura 4.6).
Como no livro, só os não terminais têm nó na pilha semântica, e TODO não
terminal empilha um nó, mesmo sem atributos (convenção do fim do cap. 4.1):
assim a distância de cada nó ao topo é sempre a posição do não terminal na
regra, contando da direita para a esquerda e pulando os terminais.

TopSem(k) devolve o k-ésimo nó a partir do topo (0 = topo), como na figura 4.9.
(A figura 6.13 escreve TopSem(-1), TopSem(-2)... para o mesmo fim.)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from lexer import ConstTable, NameTable, Token

from .grammar import N, R, RULES
from .scope import (CheckTypes, IS_TYPE_KIND, Kind, Object, SymbolTable, base_type,
                    pBool, pChar, pInteger, pString, pUniversal)

Pos = tuple[int, int]                                      # (linha, coluna)

# código -> (categoria, mensagem). Os códigos são os do livro, mais os da extensão.
MESSAGES: dict[str, tuple[str, str]] = {
    "ERR_REDECL": ("escopo", "'{}' já foi declarado neste escopo"),
    "ERR_NOT_DECL": ("escopo", "'{}' não foi declarado"),
    "ERR_NO_LOOP": ("escopo", "'{}' fora de um comando de repetição"),
    "ERR_TYPE_EXPECTED": ("tipo", "'{}' não é um tipo"),
    "ERR_BOOL_TYPE_EXPECTED": ("tipo", "{} deve ser boolean, mas é {}"),
    "ERR_TYPE_MISMATCH": ("tipo", "tipos incompatíveis em {}: {} e {}"),
    "ERR_INVALID_TYPE": ("tipo", "operador {} não se aplica ao tipo {}"),
    "ERR_KIND_NOT_STRUCT": ("tipo", "acesso ao campo '{}' em valor do tipo {}, que não é struct"),
    "ERR_FIELD_NOT_DECL": ("tipo", "o tipo {} não tem campo '{}'"),
    "ERR_KIND_NOT_ARRAY": ("tipo", "indexação de valor do tipo {}, que não é array nem string"),
    "ERR_INVALID_INDEX_TYPE": ("tipo", "índice deve ser integer, mas é {}"),
    "ERR_KIND_NOT_VAR": ("tipo", "'{}' não é variável nem parâmetro"),
    "ERR_KIND_NOT_FUNC": ("tipo", "'{}' não é função"),
    "ERR_TOO_MANY_ARGS": ("tipo", "argumentos demais na chamada de '{}' (espera {})"),
    "ERR_PARAM_TYPE": ("tipo", "argumento {} de '{}' deve ser {}, mas é {}"),
    "ERR_TOO_FEW_ARGS": ("tipo", "argumentos de menos na chamada de '{}' (espera {}, recebeu {})"),
    "ERR_RETURN_TYPE": ("tipo", "'{}' deve retornar {}, mas o return é {}"),
}


@dataclass
class CompileError:
    category: str           # léxico | sintático | escopo | tipo
    code: str
    line: int
    col: int
    message: str

    def __str__(self) -> str:
        return f"linha {self.line}, coluna {self.col}: erro {self.category}: {self.message}"


class Attrib:
    """t_attrib: nó da pilha semântica. nont diz qual não terminal o nó representa;
    os demais atributos (type, obj, list, ...) dependem do não terminal."""

    def __init__(self, nont: N, pos: Pos, **attrs: Any) -> None:
        self.nont = nont
        self.pos = pos
        self.__dict__.update(attrs)

    def __getattr__(self, name: str) -> Any:      # atributo ausente: erro claro
        raise AttributeError(f"{self.nont.name} não tem atributo {name}")


class Semantic:
    def __init__(self, names: NameTable, consts: ConstTable) -> None:
        self.names = names
        self.consts = consts
        self.table = SymbolTable()
        self.table.NewBlock()                    # nível 0: declarações do programa
        self.StackSem: list[Attrib] = []
        self.errors: list[CompileError] = []
        self.curFunction: Optional[Object] = None
        self.nLoops = 0                          # laços abertos (break/continue)
        # Preenchidos pelo analisador sintático antes de cada chamada:
        self.token: Optional[Token] = None       # último terminal empilhado
        self.pos: Pos = (0, 0)                   # posição do 1º símbolo da regra

    # ----------------------------------------------------- pilha semântica
    def PushSem(self, attrib: Attrib) -> None:
        self.StackSem.append(attrib)

    def PopSem(self, nToPop: int) -> None:
        if nToPop:
            del self.StackSem[-nToPop:]

    def TopSem(self, offFromTop: int) -> Attrib:
        return self.StackSem[-1 - offFromTop]

    # ------------------------------------------------------------ apoio
    def Error(self, code: str, pos: Pos, *args: Any) -> None:
        category, text = MESSAGES[code]
        self.errors.append(CompileError(category, code, pos[0], pos[1], text.format(*args)))

    def name(self, nName: int) -> str:
        return self.names.get_name(nName)

    def type_name(self, t: Object) -> str:
        return t.label or self.name(t.nName)

    def check_bool(self, e: Attrib, what: str) -> None:
        if not CheckTypes(e.type, pBool):
            self.Error("ERR_BOOL_TYPE_EXPECTED", e.pos, what, self.type_name(e.type))

    def binary(self, rule: R, allowed: tuple[Object, ...]) -> None:
        """Regras das figuras 6.19 e 6.20: operandos compatíveis entre si e, nas
        aritméticas, de um dos tipos permitidos ao operador. Relacionais
        (allowed vazio) são boolean; aritméticas têm o tipo do 1º operando."""
        right, left = self.TopSem(0), self.TopSem(1)
        self.PopSem(2)
        if not CheckTypes(left.type, right.type):
            self.Error("ERR_TYPE_MISMATCH", right.pos, _OPS[rule],
                       self.type_name(left.type), self.type_name(right.type))
        if allowed and not any(CheckTypes(left.type, t) for t in allowed):
            self.Error("ERR_INVALID_TYPE", left.pos, _OPS[rule], self.type_name(left.type))
        self.PushSem(Attrib(_LEFT[rule], left.pos, type=left.type if allowed else pBool))

    def define_list(self, objs: list[Object], kind: Kind, t: Object) -> None:
        """Laço das figuras 6.6 e 6.10: preenche kind e tipo da lista declarada."""
        for p in objs:
            p.eKind = kind
            p.pType = t

    # ========================================================== Semantics
    def Semantics(self, rule: R) -> None:
        pos = self.pos
        match rule:
            # ------------------------------------------------ programa e listas
            case R.P | R.LDE | R.DE_DF | R.DE_DT | R.LDV | R.LS:
                self.PopSem(1)
                self.PushSem(Attrib(_LEFT[rule], pos))
            case R.LDE_REC | R.LDV_REC | R.LS_REC | R.B:
                self.PopSem(2)
                self.PushSem(Attrib(_LEFT[rule], pos))

            # ------------------------------------------------ tipos (fig. 6.5)
            case R.T_INTEGER:
                self.PushSem(Attrib(N.T, pos, type=pInteger))
            case R.T_CHAR:
                self.PushSem(Attrib(N.T, pos, type=pChar))
            case R.T_BOOLEAN:
                self.PushSem(Attrib(N.T, pos, type=pBool))
            case R.T_STRING:
                self.PushSem(Attrib(N.T, pos, type=pString))
            case R.T_IDU:
                IDU = self.TopSem(0)
                self.PopSem(1)
                p = IDU.obj
                if IS_TYPE_KIND(p.eKind) or p.eKind == Kind.UNIVERSAL_:
                    t = p
                else:
                    t = pUniversal
                    self.Error("ERR_TYPE_EXPECTED", pos, self.name(IDU.name))
                self.PushSem(Attrib(N.T, pos, type=t))

            # -------------------------------- declarações de tipo (6.8 a 6.11)
            case R.DT_ARRAY:                     # 'type' IDD '=' 'array' '[' NUM ']' 'of' T
                T, NUM, IDD = self.TopSem(0), self.TopSem(1), self.TopSem(2)
                self.PopSem(3)
                p = IDD.obj
                p.eKind = Kind.ARRAY_TYPE_
                p.nNumElems = NUM.val
                p.pElemType = T.type
                self.PushSem(Attrib(N.DT, pos))
            case R.DT_STRUCT:                    # 'type' IDD '=' 'struct' NB '{' DC '}'
                DC, IDD = self.TopSem(0), self.TopSem(2)
                self.PopSem(3)
                p = IDD.obj
                p.eKind = Kind.STRUCT_TYPE_
                p.pFields = DC.list
                self.table.EndBlock()
                self.PushSem(Attrib(N.DT, pos))
            case R.DT_ALIAS:                     # 'type' IDD '=' T
                T, IDD = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                p = IDD.obj
                p.eKind = Kind.ALIAS_TYPE_
                p.pBaseType = T.type
                self.PushSem(Attrib(N.DT, pos))
            case R.DC_REC:                       # DC ';' LI ':' T
                T, LI, DC1 = self.TopSem(0), self.TopSem(1), self.TopSem(2)
                self.PopSem(3)
                self.define_list(LI.list, Kind.FIELD_, T.type)
                self.PushSem(Attrib(N.DC, pos, list=DC1.list + LI.list))
            case R.DC:                           # LI ':' T
                T, LI = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                self.define_list(LI.list, Kind.FIELD_, T.type)
                self.PushSem(Attrib(N.DC, pos, list=LI.list))

            # ------------------------------------------ funções (6.12, 6.13)
            case R.DF:                           # 'function' IDD NF '(' LP ')' ':' T MF B
                self.PopSem(6)
                self.table.EndBlock()
                self.curFunction = None
                self.PushSem(Attrib(N.DF, pos))
            case R.LP_REC:                       # LP ',' IDD ':' T
                T, IDD, LP1 = self.TopSem(0), self.TopSem(1), self.TopSem(2)
                self.PopSem(3)
                self.define_list([IDD.obj], Kind.PARAM_, T.type)
                self.PushSem(Attrib(N.LP, pos, list=LP1.list + [IDD.obj]))
            case R.LP:                           # IDD ':' T
                T, IDD = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                self.define_list([IDD.obj], Kind.PARAM_, T.type)
                self.PushSem(Attrib(N.LP, pos, list=[IDD.obj]))
            case R.NF:                           # ϵ  (substitui NB na função, fig. 7.18)
                IDD = self.TopSem(0)
                IDD.obj.eKind = Kind.FUNCTION_
                self.table.NewBlock()
                self.PushSem(Attrib(N.NF, pos))
            case R.MF:                           # ϵ  (após o tipo de retorno, fig. 6.13)
                T, LP, IDD = self.TopSem(0), self.TopSem(1), self.TopSem(3)
                f = IDD.obj
                f.eKind = Kind.FUNCTION_
                f.pRetType = T.type
                f.pParams = LP.list
                self.curFunction = f
                self.PushSem(Attrib(N.MF, pos))

            # -------------------------------- variáveis e listas de nomes (6.6)
            case R.DV:                           # 'var' LI ':' T ';'
                T, LI = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                self.define_list(LI.list, Kind.VAR_, T.type)
                self.PushSem(Attrib(N.DV, pos))
            case R.LI_REC:                       # LI ',' IDD
                IDD, LI1 = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                self.PushSem(Attrib(N.LI, pos, list=LI1.list + [IDD.obj]))
            case R.LI:                           # IDD
                IDD = self.TopSem(0)
                self.PopSem(1)
                self.PushSem(Attrib(N.LI, pos, list=[IDD.obj]))

            # ------------------------------------------- comandos (6.14, 6.15)
            case R.S_IF:                         # 'if' '(' E ')' S
                E = self.TopSem(1)
                self.PopSem(2)
                self.check_bool(E, "a condição do if")
                self.PushSem(Attrib(N.S, pos))
            case R.S_IF_ELSE:                    # 'if' '(' E ')' S 'else' S
                E = self.TopSem(2)
                self.PopSem(3)
                self.check_bool(E, "a condição do if")
                self.PushSem(Attrib(N.S, pos))
            case R.S_WHILE:                      # 'while' MW '(' E ')' S
                E = self.TopSem(1)
                self.PopSem(3)
                self.check_bool(E, "a condição do while")
                self.nLoops -= 1
                self.PushSem(Attrib(N.S, pos))
            case R.S_DO_WHILE:                   # 'do' MW S 'while' '(' E ')' ';'
                E = self.TopSem(0)
                self.PopSem(3)
                self.check_bool(E, "a condição do do-while")
                self.nLoops -= 1
                self.PushSem(Attrib(N.S, pos))
            case R.MW:                           # ϵ  (início de laço)
                self.nLoops += 1
                self.PushSem(Attrib(N.MW, pos))
            case R.S_BLOCK:                      # NB B
                self.PopSem(2)
                self.table.EndBlock()
                self.PushSem(Attrib(N.S, pos))
            case R.NB:                           # ϵ
                self.table.NewBlock()
                self.PushSem(Attrib(N.NB, pos))
            case R.S_ASSIGN:                     # LV '=' E ';'
                E, LV = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                if not CheckTypes(LV.type, E.type):
                    self.Error("ERR_TYPE_MISMATCH", E.pos, "atribuição",
                               self.type_name(LV.type), self.type_name(E.type))
                self.PushSem(Attrib(N.S, pos))
            case R.S_BREAK | R.S_CONTINUE:       # 'break' ';'  |  'continue' ';'
                if self.nLoops == 0:
                    self.Error("ERR_NO_LOOP", pos, "break" if rule == R.S_BREAK else "continue")
                self.PushSem(Attrib(N.S, pos))
            case R.S_RETURN:                     # 'return' E ';'
                E = self.TopSem(0)
                self.PopSem(1)
                f = self.curFunction
                assert f is not None and f.pRetType is not None
                if not CheckTypes(E.type, f.pRetType):
                    self.Error("ERR_RETURN_TYPE", E.pos, self.name(f.nName),
                               self.type_name(f.pRetType), self.type_name(E.type))
                self.PushSem(Attrib(N.S, pos))

            # ------------------------------------ expressões (6.18 a 6.20)
            case R.E_AND | R.E_OR:
                Lr, E1 = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                op = "&&" if rule == R.E_AND else "||"
                self.check_bool(E1, f"o operando de '{op}'")
                self.check_bool(Lr, f"o operando de '{op}'")
                self.PushSem(Attrib(N.E, pos, type=pBool))
            case R.L_LT | R.L_GT | R.L_LE | R.L_GE | R.L_EQ | R.L_NE:
                self.binary(rule, ())
            case R.R_PLUS:                       # soma de inteiros ou concatenação
                self.binary(rule, (pInteger, pString))
            case R.R_MINUS | R.Y_TIMES | R.Y_DIVIDE:
                self.binary(rule, (pInteger,))
            case R.E_L | R.L_R | R.R_Y | R.Y_F | R.F_LV | R.F_PAREN:   # renomeação
                X = self.TopSem(0)
                self.PopSem(1)
                self.PushSem(Attrib(_LEFT[rule], X.pos if rule != R.F_PAREN else pos,
                                    type=X.type))

            # --------------------------------- expressões elementares (6.21)
            case R.F_PRE_INC | R.F_PRE_DEC | R.F_POS_INC | R.F_POS_DEC | R.F_MINUS:
                X = self.TopSem(0)
                self.PopSem(1)
                if not CheckTypes(X.type, pInteger):
                    self.Error("ERR_INVALID_TYPE", X.pos, _OPS[rule], self.type_name(X.type))
                self.PushSem(Attrib(N.F, pos, type=pInteger))
            case R.F_NOT:
                F1 = self.TopSem(0)
                self.PopSem(1)
                if not CheckTypes(F1.type, pBool):
                    self.Error("ERR_INVALID_TYPE", F1.pos, "'!'", self.type_name(F1.type))
                self.PushSem(Attrib(N.F, pos, type=pBool))
            case R.F_TRUE | R.F_FALSE | R.F_CHR | R.F_STR | R.F_NUM:
                X = self.TopSem(0)
                self.PopSem(1)
                self.PushSem(Attrib(N.F, pos, type=X.type))

            # --------------------------------------- chamada de função (6.23)
            case R.MC:                           # ϵ, logo após IDU
                IDU = self.TopSem(0)
                f = IDU.obj
                if f.eKind != Kind.FUNCTION_:
                    if f.eKind != Kind.UNIVERSAL_:
                        self.Error("ERR_KIND_NOT_FUNC", IDU.pos, self.name(IDU.name))
                    self.PushSem(Attrib(N.MC, pos, type=pUniversal, params=[], err=True,
                                        fname=IDU.name))
                else:
                    self.PushSem(Attrib(N.MC, pos, type=f.pRetType, params=f.pParams,
                                        err=False, fname=IDU.name))
            case R.LE:                           # E   (MC está logo abaixo de E)
                E, MC = self.TopSem(0), self.TopSem(1)
                self.PopSem(1)
                self.PushSem(self.argument(MC, E, 1, MC.err))
            case R.LE_REC:                       # LE ',' E
                E, LE1 = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                self.PushSem(self.argument(LE1.mc, E, LE1.n + 1, LE1.err))
            case R.F_CALL:                       # IDU MC '(' LE ')'
                LE, MC = self.TopSem(0), self.TopSem(1)
                self.PopSem(3)
                if not LE.err and LE.n < len(MC.params):
                    self.Error("ERR_TOO_FEW_ARGS", pos, self.name(MC.fname),
                               len(MC.params), LE.n)
                self.PushSem(Attrib(N.F, pos, type=MC.type))

            # ---------------------------------------- left-values (6.22)
            case R.LV_FIELD:                     # LV '.' ID
                ID, LV1 = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                t = base_type(LV1.type)
                if t.eKind != Kind.STRUCT_TYPE_:
                    if t.eKind != Kind.UNIVERSAL_:
                        self.Error("ERR_KIND_NOT_STRUCT", ID.pos, self.name(ID.name),
                                   self.type_name(LV1.type))
                    lt = pUniversal
                else:
                    p = next((f for f in t.pFields if f.nName == ID.name), None)
                    if p is None:
                        self.Error("ERR_FIELD_NOT_DECL", ID.pos, self.type_name(LV1.type),
                                   self.name(ID.name))
                        lt = pUniversal
                    else:
                        lt = p.pType
                self.PushSem(Attrib(N.LV, pos, type=lt))
            case R.LV_INDEX:                     # LV '[' E ']'
                E, LV1 = self.TopSem(0), self.TopSem(1)
                self.PopSem(2)
                t = base_type(LV1.type)
                if t is pString:
                    lt = pChar
                elif t.eKind != Kind.ARRAY_TYPE_:
                    if t.eKind != Kind.UNIVERSAL_:
                        self.Error("ERR_KIND_NOT_ARRAY", LV1.pos, self.type_name(LV1.type))
                    lt = pUniversal
                else:
                    lt = t.pElemType
                if not CheckTypes(E.type, pInteger):
                    self.Error("ERR_INVALID_INDEX_TYPE", E.pos, self.type_name(E.type))
                self.PushSem(Attrib(N.LV, pos, type=lt))
            case R.LV_IDU:                       # IDU
                IDU = self.TopSem(0)
                self.PopSem(1)
                p = IDU.obj
                if p.eKind not in (Kind.VAR_, Kind.PARAM_):
                    if p.eKind != Kind.UNIVERSAL_:
                        self.Error("ERR_KIND_NOT_VAR", pos, self.name(IDU.name))
                    lt = pUniversal
                else:
                    lt = p.pType
                self.PushSem(Attrib(N.LV, pos, type=lt))

            # ----------------------------------- identificadores (5.8, 6.4)
            case R.IDD:                          # Id
                name = self.token.secondary
                p = self.table.Search(name)
                if p is not None and p.eKind != Kind.UNIVERSAL_:
                    self.Error("ERR_REDECL", pos, self.name(name))
                    p = Object(name)             # objeto avulso: não altera o original
                else:                            # novo, ou usado antes sem declaração
                    p = self.table.Define(name)
                p.eKind = Kind.NO_KIND_DEF_
                self.PushSem(Attrib(N.IDD, pos, name=name, obj=p))
            case R.IDU:                          # Id
                name = self.token.secondary
                p = self.table.Find(name)
                if p is None:
                    self.Error("ERR_NOT_DECL", pos, self.name(name))
                    p = self.table.Define(name)
                    p.eKind = Kind.UNIVERSAL_    # evita erros em cascata
                self.PushSem(Attrib(N.IDU, pos, name=name, obj=p))
            case R.ID:                           # Id  (campo: resolvido pelo tipo)
                self.PushSem(Attrib(N.ID, pos, name=self.token.secondary, obj=None))

            # ------------------------------------------- literais (6.7)
            case R.TRUE:
                self.PushSem(Attrib(N.TRUE, pos, type=pBool, val=True))
            case R.FALSE:
                self.PushSem(Attrib(N.FALSE, pos, type=pBool, val=False))
            case R.CHR:
                n = self.token.secondary
                self.PushSem(Attrib(N.CHR, pos, type=pChar, pos_const=n,
                                    val=self.consts.get_char_const(n)))
            case R.STR:
                n = self.token.secondary
                self.PushSem(Attrib(N.STR, pos, type=pString, pos_const=n,
                                    val=self.consts.get_string_const(n)))
            case R.NUM:
                n = self.token.secondary
                self.PushSem(Attrib(N.NUM, pos, type=pInteger, pos_const=n,
                                    val=self.consts.get_int_const(n)))
            case _:
                raise AssertionError(f"regra sem ação semântica: {rule!r}")

    def argument(self, MC: Attrib, E: Attrib, n: int, err: bool) -> Attrib:
        """Regras de LE (figura 6.23): confere o n-ésimo argumento com o n-ésimo
        parâmetro. Um erro de quantidade desliga as verificações seguintes."""
        if not err:
            if n > len(MC.params):
                self.Error("ERR_TOO_MANY_ARGS", E.pos, self.name(MC.fname), len(MC.params))
                err = True
            elif not CheckTypes(MC.params[n - 1].pType, E.type):
                self.Error("ERR_PARAM_TYPE", E.pos, n, self.name(MC.fname),
                           self.type_name(MC.params[n - 1].pType), self.type_name(E.type))
        return Attrib(N.LE, E.pos, mc=MC, n=n, err=err)


_LEFT = {r: left for r, (left, _) in zip(R, RULES)}
_OPS = {
    R.L_LT: "'<'", R.L_GT: "'>'", R.L_LE: "'<='", R.L_GE: "'>='", R.L_EQ: "'=='",
    R.L_NE: "'!='", R.R_PLUS: "'+'", R.R_MINUS: "'-'", R.Y_TIMES: "'*'", R.Y_DIVIDE: "'/'",
    R.F_PRE_INC: "'++'", R.F_PRE_DEC: "'--'", R.F_POS_INC: "'++'", R.F_POS_DEC: "'--'",
    R.F_MINUS: "'-' unário",
}
