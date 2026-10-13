"""Testes da VF (sintático, escopo e tipos). Na raiz do repositório:

    python3 -m unittest compilador.tests.test_compiler -v     # só a VF
    python3 -m unittest -v                                    # VC e VF
"""
from __future__ import annotations

import contextlib
import io
import pathlib
import unittest

from compilador import lalr
from compilador.__main__ import main as cli
from compilador.grammar import N, R, RULES, rule_text
from compilador.parser import compile_source, table
from compilador.semantics import MESSAGES, Semantic
from lexer import TokenKind as T

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"
VALID_EXAMPLES = ("fatorial.ssl", "strcmp.ssl", "strinv.ssl", "bsort.ssl", "tipos.ssl")


def errors(src: str) -> list[tuple[str, int]]:
    """(código, linha) de cada erro, na ordem em que foram detectados."""
    return [(e.code, e.line) for e in compile_source(src).errors]


def codes(src: str) -> list[str]:
    return [c for c, _ in errors(src)]


def func(body: str, decls: str = "", header: str = "f(a: integer): integer") -> str:
    """Programa com uma função; body são os comandos, decls as variáveis locais."""
    return f"function {header}\n{{\n var dummy: integer;\n{decls}\n{body}\n return 0;\n}}\n"


def reductions(src: str) -> list[R]:
    """Regras reduzidas, em ordem (instrumenta Semantics)."""
    seen: list[R] = []
    original = Semantic.Semantics

    def spy(self: Semantic, rule: R) -> None:
        seen.append(rule)
        original(self, rule)

    Semantic.Semantics = spy                      # type: ignore[method-assign]
    try:
        compile_source(src)
    finally:
        Semantic.Semantics = original             # type: ignore[method-assign]
    return seen


# ====================================================================== tabela
class TableTests(unittest.TestCase):
    def test_exactly_one_shift_reduce_conflict_the_dangling_else(self):
        conflicts = table().conflicts
        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.kind, "empilha/reduz")
        self.assertEqual(c.terminal, T.ELSE)
        self.assertIn(rule_text(R.S_IF), c.discarded)
        self.assertTrue(c.chosen.startswith("empilhar"))

    def test_no_reduce_reduce_conflict(self):
        self.assertEqual(table().stats()["conflitos reduz/reduz"], 0)

    def test_every_rule_but_start_is_reduced_somewhere(self):
        reduced = {-p for row in table().Action for p in row if p < 0}
        self.assertEqual(reduced, set(range(1, len(RULES))))

    def test_final_state_is_after_eof(self):
        tb = table()
        self.assertEqual(set(tb.states[tb.FINAL]), {(0, 2)})        # P' -> P '$' .

    def test_lalr_equals_merge_of_canonical_lr1(self):
        """Constrói o LR(1) canônico (sem fusão), funde os estados de mesmo núcleo
        e confere que dá exatamente os estados e look-aheads la-LR(1)."""
        start = frozenset({((0, 0), frozenset())})
        seen, work = {start}, [start]
        while work:
            st = work.pop()
            for _, kern in lalr.goto(lalr.closure({i: set(la) for i, la in st})).items():
                key = frozenset((i, frozenset(la)) for i, la in kern.items())
                if key not in seen:
                    seen.add(key)
                    work.append(key)
        merged: dict[frozenset, dict] = {}
        for st in seen:
            kern = {i: set(la) for i, la in st}
            target = merged.setdefault(frozenset(kern), {i: set() for i in kern})
            for i, la in kern.items():
                target[i] |= la
        lalr_kernels = {}
        for items in table().states:
            kern = {i: la for i, la in items.items() if i[1] > 0 or i == (0, 0)}
            lalr_kernels[frozenset(kern)] = kern
        self.assertGreater(len(seen), len(merged))                  # houve fusão
        self.assertEqual(set(merged), set(lalr_kernels))
        for core, kern in merged.items():
            self.assertEqual(kern, lalr_kernels[core])

    def test_semantics_has_a_case_for_every_rule(self):
        """Toda regra reduzível tem ação em Semantics (o caso padrão lança erro)."""
        src = "\n".join((EXAMPLES / f).read_text() for f in VALID_EXAMPLES)
        self.assertEqual(set(reductions(src)), set(R) - {R.START})


# ================================================================= sintático
class SyntaxTests(unittest.TestCase):
    def test_valid_examples_compile_without_errors(self):
        for name in VALID_EXAMPLES:
            with self.subTest(name):
                self.assertEqual(errors((EXAMPLES / name).read_text()), [])

    def test_error_reports_position_found_and_expected(self):
        res = compile_source("function f(a: integer): integer\n{\n var x: integer;\n x = (1 + ;\n}")
        self.assertEqual(len(res.errors), 1)
        e = res.errors[0]
        self.assertEqual((e.category, e.line, e.col), ("sintático", 4, 11))
        self.assertIn("encontrado ';'", e.message)
        self.assertIn("identificador", e.message)
        self.assertIn("'('", e.message)

    def test_expected_tokens_survive_lalr_reductions(self):
        # '2' é reduzido até E antes de o erro aparecer; os operadores continuam esperados
        e = compile_source((EXAMPLES / "erro_sintatico.ssl").read_text()).errors[0]
        for t in ("')'", "'&&'", "'<'", "'+'", "'*'"):
            self.assertIn(t, e.message)

    def test_missing_semicolon(self):
        e = compile_source(func("a = 1")).errors[0]
        self.assertEqual(e.code, "ERR_SYNTAX")
        self.assertIn("';'", e.message)

    def test_unexpected_end_of_file(self):
        e = compile_source("function f(a: integer): integer { var x: integer; x = 1;").errors[0]
        self.assertIn("encontrado fim de arquivo", e.message)

    def test_empty_program_is_syntax_error(self):
        self.assertEqual(codes(""), ["ERR_SYNTAX"])

    def test_dangling_else_binds_to_nearest_if(self):
        src = func("if (true) if (false) a = 1; else a = 2;")
        rs = [r for r in reductions(src) if r in (R.S_IF, R.S_IF_ELSE)]
        self.assertEqual(rs, [R.S_IF_ELSE, R.S_IF])       # o interno é o if-else

    def test_operator_precedence_and_associativity(self):
        # a - b - c: a redução de R -> R '-' Y acontece duas vezes, à esquerda
        rs = reductions(func("a = a - a - a * a;"))
        self.assertEqual(rs.count(R.R_MINUS), 2)
        self.assertLess(rs.index(R.Y_TIMES), rs.index(R.R_MINUS, rs.index(R.R_MINUS) + 1))

    def test_official_grammar_restrictions_are_kept(self):
        # bloco exige ao menos uma declaração e um comando
        self.assertEqual(codes(func("if (true) { a = 1; }")), ["ERR_SYNTAX"])
        # função exige ao menos um parâmetro; chamada, ao menos um argumento
        self.assertEqual(codes("function f(): integer { var x: integer; x = 1; }"),
                         ["ERR_SYNTAX"])
        # declaração de tipo não termina com ';'
        self.assertEqual(codes("type t = integer;"), ["ERR_SYNTAX"])
        # chamada e incremento não são comandos
        self.assertEqual(codes(func("a++;")), ["ERR_SYNTAX"])

    def test_return_is_a_statement(self):
        self.assertEqual(codes(func("return a + 1;")), [])

    def test_lexical_errors_prevent_parsing(self):
        res = compile_source("function f(a: integer): integer { var x: integer; x = 1 # 2; ; }")
        self.assertEqual([e.code for e in res.errors], ["ERR_LEXICAL"])
        self.assertIsNone(res.semantic)

    def test_all_lexical_errors_are_listed(self):
        self.assertEqual(codes("var x # @ & y"), ["ERR_LEXICAL"] * 3)


# =================================================================== escopo
class ScopeTests(unittest.TestCase):
    def test_redeclaration_in_same_level(self):
        self.assertEqual(errors(func("", "var x, x: integer;")), [("ERR_REDECL", 4)])

    def test_params_and_locals_share_a_level(self):
        self.assertEqual(codes(func("", "var a: integer;")), ["ERR_REDECL"])
        self.assertEqual(codes("function f(a: integer, a: char): integer"
                               "{ var x: integer; return 0; }"), ["ERR_REDECL"])

    def test_function_name_is_in_outer_level_and_recursion_is_allowed(self):
        self.assertEqual(codes(func("a = f(a - 1);")), [])
        self.assertEqual(codes(func("", "var f: integer;")), [])     # f local esconde a função
        self.assertEqual(codes(func("") + func("")), ["ERR_REDECL"])

    def test_inner_block_may_shadow_and_ends_at_close(self):
        src = func("{ var a: boolean; a = true; } a = 1;")
        self.assertEqual(codes(src), [])
        self.assertEqual(codes(func("{ var z: integer; z = 1; } z = 2;")), ["ERR_NOT_DECL"])

    def test_undeclared_use(self):
        self.assertEqual(errors(func("a = y;")), [("ERR_NOT_DECL", 5)])

    def test_undeclared_is_reported_once_per_block(self):
        self.assertEqual(codes(func("a = y + y; y = y;")), ["ERR_NOT_DECL"])

    def test_struct_fields_have_their_own_level(self):
        self.assertEqual(codes("type p = struct { x: integer; x: char }"), ["ERR_REDECL"])
        self.assertEqual(codes("type t = integer type p = struct { x: t }"), [])
        self.assertEqual(codes("type p = struct { x: integer }\n" + func("x = 1;")),
                         ["ERR_NOT_DECL"])                   # campo não é visível fora

    def test_scope_of_a_name_starts_at_its_declaration(self):
        # o campo x já esconde o tipo x quando T é reduzido
        self.assertEqual(codes("type x = integer type p = struct { x: x }"),
                         ["ERR_TYPE_EXPECTED"])

    def test_field_access_is_not_a_scope_check(self):
        src = "type p = struct { campo: integer }\n" + func("a = v.campo;", "var v: p;")
        self.assertEqual(codes(src), [])

    def test_use_before_declaration_is_not_also_a_redeclaration(self):
        self.assertEqual(errors("type a = b\ntype b = integer"), [("ERR_NOT_DECL", 1)])

    def test_declaration_order_matters(self):
        self.assertEqual(codes(func("a = g(1);") + func("", header="g(b: integer): integer")),
                         ["ERR_NOT_DECL"])

    def test_break_and_continue_outside_loop(self):
        self.assertEqual(codes(func("break;")), ["ERR_NO_LOOP"])
        self.assertEqual(codes(func("if (true) continue;")), ["ERR_NO_LOOP"])
        self.assertEqual(codes(func("while (true) { var b: boolean; b = true; break; } continue;")),
                         ["ERR_NO_LOOP"])
        self.assertEqual(codes(func("do continue; while (true);")), [])


# ==================================================================== tipos
class TypeTests(unittest.TestCase):
    DECLS = ("type vetor = array [3] of integer\n"
             "type ponto = struct { x, y: integer; nome: string }\n"
             "type texto = string\n"
             "type inteiro = integer\n"
             "type pontos = array [2] of ponto\n")

    def check(self, body: str, decls: str = "") -> list[str]:
        locals_ = ("var v: vetor; var p: ponto; var s: texto; var b: boolean;"
                   " var c: char; var i: inteiro; var ps: pontos;")
        return codes(self.DECLS + func(body, locals_ + decls,
                                       "f(a: integer, t: string): integer"))

    def test_valid_expressions(self):
        ok = [
            "a = v[0] + p.x * i / 2 - -a;",
            "s = t + s + \"!\";",                     # concatenação; alias == base
            "c = s[a];", "s[0] = c;", "t[1] = 'x';",  # string indexada -> char
            "ps[1].nome[0] = ps[0].nome[1];",
            "b = a < i && c == 'x' || !(s != t) && true;",
            "i = a++ + --v[1];",
            "p = ps[0]; ps[1] = p;",                   # struct inteira, mesmo tipo
            "a = f(i, s);",
            "if (b) a = 1; else a = 2;", "while (a > 0) a = a - 1;",
            "do a = a - 1; while (a > 0);",
            "return i;",
        ]
        for body in ok:
            with self.subTest(body):
                self.assertEqual(self.check(body), [])

    def test_type_expected(self):
        self.assertEqual(self.check("", "var z: a;"), ["ERR_TYPE_EXPECTED"])
        self.assertEqual(codes("type t = struct { x: t }"), ["ERR_TYPE_EXPECTED"])

    def test_bool_expected_in_conditions_and_logic(self):
        for body in ("if (a) a = 1;", "while (s) a = 1;", "do a = 1; while (c);",
                     "b = a && b;", "b = b || 'c';"):
            with self.subTest(body):
                self.assertEqual(self.check(body), ["ERR_BOOL_TYPE_EXPECTED"])

    def test_type_mismatch(self):
        for body in ("a = b;", "b = a < c;", "s = c;", "p = v;", "a = a + s;"):
            with self.subTest(body):
                self.assertIn("ERR_TYPE_MISMATCH", self.check(body))

    def test_invalid_operand_type(self):
        for body in ("a = b - b;", "b = b + b;", "a = s * s;", "a = -b;", "b = !a;",
                     "a = c++;", "a = --s;"):
            with self.subTest(body):
                self.assertIn("ERR_INVALID_TYPE", self.check(body))

    def test_left_values(self):
        self.assertEqual(self.check("a = a.x;"), ["ERR_KIND_NOT_STRUCT"])
        self.assertEqual(self.check("a = p.z;"), ["ERR_FIELD_NOT_DECL"])
        self.assertEqual(self.check("a = a[0];"), ["ERR_KIND_NOT_ARRAY"])
        self.assertEqual(self.check("a = v[b];"), ["ERR_INVALID_INDEX_TYPE"])
        self.assertEqual(self.check("a = vetor;"), ["ERR_KIND_NOT_VAR"])
        self.assertEqual(self.check("f = 1;"), ["ERR_KIND_NOT_VAR"])

    def test_calls(self):
        self.assertEqual(self.check("a = a(1);"), ["ERR_KIND_NOT_FUNC"])
        self.assertEqual(self.check("a = f(1);"), ["ERR_TOO_FEW_ARGS"])
        self.assertEqual(self.check("a = f(1, s, 2, 3);"), ["ERR_TOO_MANY_ARGS"])
        self.assertEqual(self.check("a = f(s, 1);"), ["ERR_PARAM_TYPE", "ERR_PARAM_TYPE"])
        self.assertEqual(self.check("b = f(1, s);"), ["ERR_TYPE_MISMATCH"])   # retorno integer

    def test_return_type(self):
        self.assertEqual(self.check("return s;"), ["ERR_RETURN_TYPE"])

    def test_universal_type_avoids_cascades(self):
        # identificador e tipo não declarados: um único erro cada
        self.assertEqual(self.check("a = y.campo[3] + 1;"), ["ERR_NOT_DECL"])
        self.assertEqual(self.check("a = g(1, 2) + 1;"), ["ERR_NOT_DECL"])
        self.assertEqual(self.check("a = z.x;", "var z: desconhecido;"), ["ERR_NOT_DECL"])
        # tipo com erro (variável usada como tipo) não gera erros nos usos
        self.assertEqual(self.check("z = 1; z.q = 'c';", "var z: a;"), ["ERR_TYPE_EXPECTED"])
        # campo inexistente: o acesso seguinte não acusa nada
        self.assertEqual(self.check("a = p.z.w[1];"), ["ERR_FIELD_NOT_DECL"])

    def test_errors_are_accumulated_with_lines(self):
        src = func("a = b;\nb = 1;\nif (a) a = 1;", "var b: boolean;")
        self.assertEqual(errors(src), [("ERR_TYPE_MISMATCH", 5), ("ERR_TYPE_MISMATCH", 6),
                                       ("ERR_BOOL_TYPE_EXPECTED", 7)])

    def test_every_semantic_error_code_is_covered(self):
        """Cada código de erro de escopo e de tipo aparece no exemplo de erro."""
        found = set()
        for name in ("erro_escopo.ssl", "erro_tipos.ssl"):
            found |= set(codes((EXAMPLES / name).read_text()))
        self.assertEqual(found, set(MESSAGES))


# ======================================================== exemplos e CLI
class ExampleAndCliTests(unittest.TestCase):
    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = cli(list(argv))
        return status, out.getvalue()

    def test_error_examples(self):
        expected = {"erro_lexico.ssl": "ERR_LEXICAL", "erro_sintatico.ssl": "ERR_SYNTAX"}
        for name, code in expected.items():
            with self.subTest(name):
                self.assertTrue(codes((EXAMPLES / name).read_text()))
                self.assertEqual(set(codes((EXAMPLES / name).read_text())), {code})

    def test_exit_status(self):
        self.assertEqual(self.run_cli(str(EXAMPLES / "fatorial.ssl"))[0], 0)
        self.assertEqual(self.run_cli(str(EXAMPLES / "erro_tipos.ssl"))[0], 1)

    def test_tokens_mode_is_the_vc_output(self):
        import main as vc
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            vc.main([str(EXAMPLES / "fatorial.ssl")])
        self.assertEqual(self.run_cli(str(EXAMPLES / "fatorial.ssl"), "--tokens")[1],
                         out.getvalue())

    def test_return_is_a_keyword(self):
        _, out = self.run_cli(str(EXAMPLES / "fatorial.ssl"), "--tokens")
        self.assertIn("RETURN", out)

    def test_table_stats(self):
        _, out = self.run_cli("--tabela")
        self.assertIn("conflitos empilha/reduz  1", out)
        self.assertIn("conflitos reduz/reduz    0", out)

    def test_symbols_listing(self):
        _, out = self.run_cli(str(EXAMPLES / "tipos.ssl"), "--simbolos")
        self.assertIn("type struct { x: integer; y: integer; nome: string }", out)
        self.assertIn("function (p: ponto, q: ponto): inteiro", out)

    def test_nonterminal_enum_matches_rules(self):
        self.assertEqual({left for left, _ in RULES}, set(N))


if __name__ == "__main__":
    unittest.main()
