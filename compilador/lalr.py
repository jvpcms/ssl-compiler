"""Construção da Tabela de Ação la-LR(1) a partir da gramática (cap. 3.6 a 3.8).

Em vez de montar à mão uma tabela para mais de 80 regras, o programa a calcula:

  1. FIRST e anuláveis de cada não terminal (ponto fixo);
  2. closure() de um conjunto de itens LR(1) (regra, ponto, look-aheads);
  3. goto() pelo símbolo após o ponto;
  4. fusão de estados com o mesmo núcleo (itens iguais a menos dos look-aheads).

A fusão é feita durante a construção, como o cap. 3.8 sugere ("reaproveitando
estados já existentes e adicionando novos look-aheads aos já existentes"):
quando goto() produz um núcleo que já existe, os look-aheads são unidos ao
estado existente e, se algum look-ahead novo apareceu, o estado é reprocessado
para propagá-lo. O resultado é o mesmo da fusão dos estados LR(1) canônicos.

Codificação da Tabela de Ação (figura 3.19):
    Action[q][a] > 0   empilha (terminal) ou transição (não terminal) para o estado
    Action[q][a] < 0   reduz pela regra -Action[q][a]
    Action[q][a] == 0  erro
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .grammar import (N, NONTERMINALS, RULES, TERMINALS, NT_BASE, is_terminal,
                      rule_text, symbol_name)
from lexer import TokenKind as T

Item = tuple[int, int]          # (regra, posição do ponto)

N_COLS = len(TERMINALS) + len(NONTERMINALS)


def col(sym: int) -> int:
    """Coluna da Tabela de Ação: terminais primeiro, não terminais em seguida."""
    return sym if is_terminal(sym) else len(TERMINALS) + (sym - NT_BASE)


def IS_SHIFT(p: int) -> bool:
    return p > 0


def IS_REDUCTION(p: int) -> bool:
    return p < 0


def RULE(p: int) -> int:
    return -p


@dataclass
class Conflict:
    state: int
    terminal: int
    kind: str           # "empilha/reduz" ou "reduz/reduz"
    chosen: str
    discarded: str

    def __str__(self) -> str:
        return (f"estado {self.state}, com {symbol_name(self.terminal)}: conflito "
                f"{self.kind}; escolhido {self.chosen}, descartado {self.discarded}")


@dataclass
class Table:
    Action: list[list[int]]
    FINAL: int
    states: list[dict[Item, set[int]]]          # closure de cada estado
    conflicts: list[Conflict] = field(default_factory=list)

    def expected(self, visited: list[int]) -> list[int]:
        """Terminais esperados quando o analisador para em visited[-1].

        visited são os estados consultados com o token corrente desde o último
        empilhamento. Como os look-aheads la-LR(1) de estados fundidos podem
        provocar reduções antes de o erro ser detectado, o último estado sozinho
        mostraria só parte dos terminais válidos ('x = (1 + 2;' pararia
        esperando apenas ')', '&&' ou '||'). Juntam-se os empilhamentos de todos os
        estados visitados às ações do estado em que o erro foi detectado."""
        q = visited[-1]
        return [a for a in TERMINALS
                if self.Action[q][col(a)] != 0
                or any(IS_SHIFT(self.Action[v][col(a)]) for v in visited)]

    def stats(self) -> dict[str, int]:
        cells = [p for row in self.Action for p in row[:len(TERMINALS)]]
        return {
            "regras": len(RULES),
            "terminais": len(TERMINALS),
            "não terminais": len(NONTERMINALS),
            "estados": len(self.Action),
            "empilhamentos": sum(1 for p in cells if IS_SHIFT(p)),
            "reduções": sum(1 for p in cells if IS_REDUCTION(p)),
            "transições": sum(1 for row in self.Action for p in row[len(TERMINALS):] if p),
            "conflitos empilha/reduz": sum(c.kind == "empilha/reduz" for c in self.conflicts),
            "conflitos reduz/reduz": sum(c.kind == "reduz/reduz" for c in self.conflicts),
        }


# ------------------------------------------------------------------ FIRST
def _first_sets() -> tuple[dict[int, set[int]], set[int]]:
    first: dict[int, set[int]] = {n: set() for n in NONTERMINALS}
    nullable: set[int] = set()
    changed = True
    while changed:
        changed = False
        for left, rhs in RULES:
            before = (len(first[left]), left in nullable)
            for sym in rhs:
                if is_terminal(sym):
                    first[left].add(sym)
                    break
                first[left] |= first[sym]
                if sym not in nullable:
                    break
            else:
                nullable.add(left)
            changed |= before != (len(first[left]), left in nullable)
    return first, nullable


FIRST, NULLABLE = _first_sets()
RULES_OF: dict[int, list[int]] = {n: [] for n in NONTERMINALS}
for _r, (_left, _) in enumerate(RULES):
    RULES_OF[_left].append(_r)


def first_of(seq: tuple[int, ...], lookaheads: set[int]) -> set[int]:
    """FIRST(seq . lookaheads): iniciadores de seq, mais os look-aheads se seq ⇒* ϵ."""
    out: set[int] = set()
    for sym in seq:
        if is_terminal(sym):
            out.add(sym)
            return out
        out |= FIRST[sym]
        if sym not in NULLABLE:
            return out
    return out | lookaheads


# ------------------------------------------------------------ closure / goto
def closure(kernel: dict[Item, set[int]]) -> dict[Item, set[int]]:
    items = {it: set(la) for it, la in kernel.items()}
    work = list(items)
    while work:
        r, d = work.pop()
        rhs = RULES[r][1]
        if d == len(rhs) or is_terminal(rhs[d]):
            continue
        la = first_of(rhs[d + 1:], items[(r, d)])
        for r2 in RULES_OF[rhs[d]]:
            cur = items.setdefault((r2, 0), set())
            if not la <= cur:
                cur |= la
                work.append((r2, 0))
    return items


def goto(items: dict[Item, set[int]]) -> dict[int, dict[Item, set[int]]]:
    """Núcleos dos estados alcançados a partir de items, por símbolo de acesso."""
    out: dict[int, dict[Item, set[int]]] = {}
    for (r, d), la in items.items():
        rhs = RULES[r][1]
        if d < len(rhs):
            out.setdefault(rhs[d], {})[(r, d + 1)] = set(la)
    return out


# ------------------------------------------------------------- construção
def build() -> Table:
    kernels: list[dict[Item, set[int]]] = [{(0, 0): set()}]   # P' -> . P '$', ϵ
    by_core: dict[frozenset[Item], int] = {frozenset(kernels[0]): 0}
    trans: dict[tuple[int, int], int] = {}
    work = [0]
    while work:
        q = work.pop()
        for sym, kern in goto(closure(kernels[q])).items():
            core = frozenset(kern)
            t = by_core.get(core)
            if t is None:                                  # estado novo
                t = len(kernels)
                kernels.append(kern)
                by_core[core] = t
                work.append(t)
            else:                                          # mesmo núcleo: funde
                changed = False
                for it, la in kern.items():
                    if not la <= kernels[t][it]:
                        kernels[t][it] |= la
                        changed = True
                if changed and t not in work:
                    work.append(t)
            trans[(q, sym)] = t

    states = [closure(k) for k in kernels]
    Action = [[0] * N_COLS for _ in states]
    table = Table(Action, FINAL=trans[(trans[(0, N.P)], T.EOF)], states=states)

    for (q, sym), t in trans.items():
        Action[q][col(sym)] = t
    for q, items in enumerate(states):
        for (r, d), la in sorted(items.items()):
            if r == 0 or d != len(RULES[r][1]):
                continue
            for a in sorted(la):
                cur = Action[q][col(a)]
                if cur == 0:
                    Action[q][col(a)] = -r
                elif IS_SHIFT(cur):                        # empilha/reduz: empilha
                    table.conflicts.append(Conflict(
                        q, a, "empilha/reduz", f"empilhar (estado {cur})",
                        f"reduzir por {rule_text(r)}"))
                else:                                      # reduz/reduz: menor regra
                    keep, drop = sorted((RULE(cur), r))
                    Action[q][col(a)] = -keep
                    table.conflicts.append(Conflict(
                        q, a, "reduz/reduz", f"reduzir por {rule_text(keep)}",
                        f"reduzir por {rule_text(drop)}"))
    return table

