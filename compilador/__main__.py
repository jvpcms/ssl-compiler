"""Linha de comando do compilador da Simple Script Language (VF).

Uso (na raiz do repositório):
    python3 -m compilador programa.ssl            # análise léxica, sintática, de escopo e de tipos
    python3 -m compilador programa.ssl --tokens   # só o léxico, com a saída da VC
    python3 -m compilador programa.ssl --simbolos # também lista as declarações globais
    python3 -m compilador --tabela                # estatísticas e conflitos da tabela la-LR(1)
    python3 -m compilador --gramatica             # regras numeradas, como em Semantics()
    echo '...' | python3 -m compilador -
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .grammar import R, rule_text
from .parser import compile_source, table
from .scope import Kind, Object
from .semantics import Semantic


def describe(sem: Semantic, o: Object) -> str:
    """Uma linha com o kind e as informações de tipo de um object."""
    tn = sem.type_name
    k = o.eKind
    if k == Kind.FUNCTION_:
        params = ", ".join(f"{sem.name(p.nName)}: {tn(p.pType)}" for p in o.pParams)
        return f"function ({params}): {tn(o.pRetType)}"
    if k == Kind.ARRAY_TYPE_:
        return f"type array [{o.nNumElems}] of {tn(o.pElemType)}"
    if k == Kind.STRUCT_TYPE_:
        fields = "; ".join(f"{sem.name(f.nName)}: {tn(f.pType)}" for f in o.pFields)
        return f"type struct {{ {fields} }}"
    if k == Kind.ALIAS_TYPE_:
        return f"type alias de {tn(o.pBaseType)}"
    return k.name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m compilador",
                                 description="Compilador da Simple Script Language (VF)")
    ap.add_argument("source", nargs="?", help="arquivo fonte ('-' para stdin)")
    ap.add_argument("--tokens", action="store_true", help="saída do analisador léxico da VC")
    ap.add_argument("--tables", action="store_true", help="com --tokens: tabelas da VC")
    ap.add_argument("--simbolos", action="store_true", help="lista as declarações do nível 0")
    ap.add_argument("--tabela", action="store_true", help="estatísticas da tabela la-LR(1)")
    ap.add_argument("--gramatica", action="store_true", help="lista as regras numeradas")
    args = ap.parse_args(argv)

    if args.gramatica:
        for r in R:
            print(f"{r.value:>3}  {r.name:<11} {rule_text(r)}")
    if args.tabela:
        tb = table()
        for k, v in tb.stats().items():
            print(f"{k:<24} {v}")
        print(f"{'estado final':<24} {tb.FINAL}")
        for c in tb.conflicts:
            print(f"  {c}")
    if args.source is None:
        if not (args.gramatica or args.tabela):
            ap.error("informe o arquivo fonte")
        return 0

    if args.tokens:                      # reaproveita a interface da VC sem alterá-la
        import main as vc
        return vc.main([args.source] + (["--tables"] if args.tables else []))

    text = sys.stdin.read() if args.source == "-" else Path(args.source).read_text(encoding="utf-8")
    result = compile_source(text)
    for err in result.errors:
        print(err)
    if result.ok:
        print("Programa correto: nenhum erro léxico, sintático, de escopo ou de tipo.")
    else:
        print(f"{len(result.errors)} erro(s).")
    if args.simbolos and result.semantic is not None:
        sem = result.semantic
        print("\nDECLARAÇÕES DO NÍVEL 0")
        for o in sem.table.levels[0].values():
            print(f"  {sem.name(o.nName):<12} {describe(sem, o)}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
