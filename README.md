# Analisador Léxico — Simple Script Language

> A continuação (VF: análise sintática, de escopo e de tipos) está em
> [`compilador/`](compilador/README.md) e reaproveita este analisador léxico.

Analisador léxico em Python (sem dependências externas) para a gramática da
disciplina de Compiladores (Prof. Luiz Guedes, IME). Implementa o projeto
descrito na apostila:

- **Enumeração de tokens** com as palavras reservadas em ordem alfabética nos
  primeiros valores, de modo que a posição no vetor de reservadas **é** o token.
- **Busca binária** no vetor de palavras reservadas para distinguir reservada de
  identificador.
- **Tabela de nomes** (hash) que atribui a cada identificador um **token
  secundário** inteiro na ordem de primeira ocorrência. Cada identificador entra
  uma só vez.
- **Tabela de constantes** (união discriminada char / int / string) cuja posição
  é o token secundário de `NUMERAL`, `CHARACTER` e `STRINGVAL`.
- **Autômato finito** com lookahead de um caractere: o léxico está sempre um
  caractere à frente para saber onde o lexema termina sem perder o caractere
  que inicia o próximo token (`a+b`, `x<=y`, `i++`).

## Lexemas reconhecidos

```
letra  = 'a'..'z' + 'A'..'Z'
digito = '0'..'9'
Id     = letra . (letra + digito)*          -> ID        (token secundário: nome)
n      = digito . digito*                   -> NUMERAL   (token secundário: índice na tabela de constantes)
c      = ''' . any . '''                    -> CHARACTER (idem)
s      = '"' . any* . '"'                   -> STRINGVAL (idem)
```

Palavras reservadas: `array boolean break char continue do else false function
if integer of return string struct true type var while` (`return` foi
acrescentada na VF; ver `compilador/README.md`).

Símbolos: `: ; , = [ ] { } ( ) && || < > <= >= != == + ++ - -- * / . !`.

Observação: seguindo a gramática à letra, `_` **não** faz parte de `Id`. Um
`_` no fonte é erro léxico. Separadores (espaço, tab, quebra de linha) são
ignorados.

## Estrutura

```
lexical_analyzer/
├── lexer/
│   ├── tokens.py    enumeração TokenKind, vetor KEYWORDS, tabelas de símbolos, classe Token
│   ├── tables.py    search_keyword (busca binária), NameTable, ConstTable
│   └── lexer.py     classe Lexer: next_token() e o autômato
├── main.py          interface de linha de comando
├── examples/        programas de exemplo (.ssl)
└── tests/           testes automatizados (unittest)
```

Requer Python 3.10 ou superior. Nenhuma instalação é necessária.

## Como rodar o analisador

Dentro da pasta `lexical_analyzer`:

```bash
# lista os tokens de um arquivo
python3 main.py examples/fatorial.ssl

# lista os tokens e imprime as tabelas de nomes e constantes ao final
python3 main.py examples/tipos.ssl --tables

# lê o programa da entrada padrão
echo 'var x, y: integer; x = y + 10;' | python3 main.py -

# modo tolerante: em vez de parar no 1º erro, emite UNKNOWN e continua
python3 main.py --lenient examples/erro.ssl
```

Saída para `echo 'var x, y: integer; x = y + 10;' | python3 main.py - --tables`:

```
LINHA  COL  TOKEN                 SEC  LEXEMA
------------------------------------------------------------
    1    1  VAR                        var
    1    5  ID                      0  x
    1    6  COMMA                      ,
    1    8  ID                      1  y
    1    9  COLON                      :
    1   11  INTEGER                    integer
    1   18  SEMI_COLON                 ;
    1   20  ID                      0  x
    1   22  EQUALS                     =
    1   24  ID                      1  y
    1   26  PLUS                       +
    1   28  NUMERAL                 0  10
    1   30  SEMI_COLON                 ;
    2    1  EOF

TABELA DE NOMES (token secundário -> identificador)
     0  x
     1  y

TABELA DE CONSTANTES (token secundário -> tipo, valor)
     0  int    10
```

Repare que o segundo `x` recebe o mesmo token secundário `0` do primeiro: é
o mesmo nome. A coluna `SEC` fica vazia em palavras reservadas e símbolos,
que não precisam de token secundário.

O programa termina com código de saída `0` se não houve erro léxico e `1` se
houve (útil em scripts).

## Como rodar os testes

Dentro da pasta `lexical_analyzer`:

```bash
python3 -m unittest -v
```

Ou apenas um grupo:

```bash
python3 -m unittest tests.test_lexer.SymbolsTests -v
python3 -m unittest tests.test_lexer.ConstantsTests.test_numeral -v
```

Se tiver `pytest` instalado, `pytest -v` também funciona.

O que os testes cobrem:

| Grupo | O que verifica |
|---|---|
| `KeywordTableTests` | vetor de reservadas ordenado e alinhado com a enumeração; busca binária devolve a posição como token |
| `KeywordsAndIdentifiersTests` | todas as reservadas; `While` e `whilex` são ID; token secundário segue a ordem de primeira ocorrência; cada nome entra uma vez na tabela |
| `ConstantsTests` | numerais, strings (inclusive vazias e contendo reservadas), caracteres; numeração única na tabela de constantes; erros de string/char malformados |
| `SymbolsTests` | todos os símbolos de 1 e 2 caracteres; o lookahead separa `a+b`, `a++b`, `a+++b`, `x<=y`, `x=-1`; `&` e `|` isolados são erro |
| `WhitespaceAndPositionTests` | separadores ignorados; entrada vazia gera só EOF; linha e coluna corretas |
| `ErrorHandlingTests` | caractere inválido lança `LexicalError` com posição; modo tolerante emite `UNKNOWN` |
| `ProgramTests` | declarações, cabeçalho de função, tipos, expressão com todos os níveis de operador; os arquivos de `examples/` tokenizam sem erro |

## Escrevendo seus próprios testes

Crie um arquivo `.ssl` e rode `python3 main.py seu_arquivo.ssl --tables`. Para
um teste automatizado, adicione um método em `tests/test_lexer.py` usando os
auxiliares já existentes:

```python
def test_meu_caso(self):
    self.assertEqual(kinds("x++;"), [T.ID, T.PLUS_PLUS, T.SEMI_COLON])
    self.assertEqual(pairs("a b a"), [(T.ID, 0), (T.ID, 1), (T.ID, 0)])
```

`kinds(src)` devolve só os tokens principais; `pairs(src)` devolve pares
(token principal, token secundário).

## Uso como biblioteca

```python
from lexer import Lexer, TokenKind

lx = Lexer("var x: integer; x = 'a';")
for tok in lx.tokens(include_eof=False):
    print(tok.kind.name, tok.secondary, tok.lexeme)

print(lx.names.get_name(0))         # 'x'
print(lx.consts.get_char_const(0))  # 'a'
```

Um analisador sintático consome os tokens chamando `lx.next_token()`
repetidamente, exatamente como `nextToken()` na apostila. Após cada chamada,
`lx.token` e `lx.token_secundario` guardam o último token principal e
secundário devolvidos.
