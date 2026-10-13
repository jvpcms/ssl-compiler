# Compilador da Simple Script Language: VF (sintático, escopo e tipos)

Continuação da VC (analisador léxico, na raiz deste repositório) para a
disciplina de Compiladores (Prof. Luiz Guedes, IME). A VF acrescenta ao léxico:

- **análise sintática** ascendente la-LR(1) dirigida por tabela (cap. 3.8),
  com avaliação de atributos a cada redução (cap. 4, figura 4.6);
- **análise de escopo** com tabela de símbolos em pilha de níveis (cap. 5);
- **análise de tipos** com kinds, tipos pré-definidos e tipo universal (cap. 6).

A **geração de código** (cap. 7) está fora do escopo desta entrega, conforme o
enunciado: ela fica para um trabalho futuro. Os pontos do cap. 7 que afetam as
fases implementadas estão registrados na seção 7.

> **Sobre a linguagem de implementação.** O roteiro da VF pedia C++11 "como na
> VC", mas a VC entregue (este repositório) foi escrita em **Python 3.10+**, sem
> dependências. Como o roteiro também exige reaproveitar o léxico sem reescrevê-lo,
> a VF foi feita em Python e importa o pacote `lexer/` da VC. A VC continua
> intacta na raiz (o roteiro falava em `analisador/`, pasta que não existe neste
> repositório); a única alteração nela foi a palavra reservada `return` (seção 2).

## Sumário

1. [Entendimento](#1-entendimento)
2. [Gramática efetivamente usada](#2-gramática-efetivamente-usada)
3. [Análise sintática](#3-análise-sintática)
4. [Análise de escopo](#4-análise-de-escopo)
5. [Análise de tipos](#5-análise-de-tipos)
6. [Geração de código](#6-geração-de-código)
7. [Decisões e ambiguidades](#7-decisões-e-ambiguidades)
8. [Como compilar, executar e testar](#8-como-compilar-executar-e-testar)
9. [Exemplos de entrada e saída](#9-exemplos-de-entrada-e-saída)
10. [Revisão final: regras × ações semânticas](#10-revisão-final-regras--ações-semânticas)

## Estrutura

```
lexical_analyzer/
├── lexer/                VC: analisador léxico (só ganhou a reservada 'return')
├── main.py, tests/, examples/   VC, sem alterações
└── compilador/           VF
    ├── grammar.py        enumerações N (não terminais) e R (regras), RULES, Len, Left
    ├── lalr.py           FIRST, closure, goto, fusão de núcleos -> Action[q][a]
    ├── parser.py         algoritmo da figura 4.6 e encadeamento léxico -> sintático
    ├── scope.py          Kind, Object, tipos pré-definidos, SymbolTable, CheckTypes
    ├── semantics.py      pilha semântica, Semantics(rule) com um case por regra
    ├── __main__.py       linha de comando
    ├── examples/         programas .ssl válidos e com erros
    └── tests/test_compiler.py   todos os testes da VF
```

## 1. Entendimento

| Fase | Capítulo | O que faz aqui | Onde |
|---|---|---|---|
| Léxica | 2 (VC) | Produz `Token(kind, secondary, lexeme, line, col)`; `secondary` é o índice na tabela de nomes (Id) ou de constantes (n, c, s). | `lexer/` |
| Sintática | 3.5 a 3.8 | Autômato la-LR(1): a pilha guarda estados; `Action[q][a]` diz se empilha, reduz ou dá erro. A tabela é calculada pelo programa a partir da gramática. | `lalr.py`, `parser.py` |
| Atributos | 4 | A cada redução, `Semantics(r)` desempilha os nós dos não terminais do lado direito e empilha o do lado esquerdo (pilha semântica paralela à sintática). Herdados à esquerda são lidos com `TopSem(k)` nos marcadores. | `semantics.py` |
| Escopo | 5 | Os `Id` da gramática viram `IDD` (declaração) ou `IDU` (uso). `IDD` procura só no nível corrente (`Search`) e acusa redeclaração; `IDU` procura em todos os níveis visíveis (`Find`) e acusa não declaração. `NB` abre um nível em struct e bloco; `NF` na função. | `scope.py`, casos `IDD`, `IDU`, `NB`, `NF` |
| Tipos | 6 | Cada identificador tem um `object` com seu kind e as informações do kind (tipo de variável, parâmetros e retorno de função, elemento e tamanho de array, campos de struct, base de alias). As regras de expressão sintetizam `type`; comandos conferem com `CheckTypes`. | `scope.py`, demais casos de `Semantics` |

O encadeamento é: o léxico lê o arquivo inteiro em modo tolerante; se houver
qualquer erro léxico, todos são listados e a análise para. Senão, o analisador
sintático consome os tokens e chama `Semantics(r)` em cada redução, de modo que
escopo e tipos são verificados numa única passada, dirigida pela sintaxe. Os
erros de escopo e de tipo são acumulados; o primeiro erro sintático encerra a
análise (não há recuperação de erro sintático no livro).

## 2. Gramática efetivamente usada

Listagem gerada por `python3 -m compilador --gramatica`. O número da regra é o
valor de `R` e é o que aparece na tabela (`-r` = reduzir pela regra `r`). Os
terminais entre aspas são palavras reservadas e símbolos; `Id`, `n`, `c` e `s`
são os tokens `ID`, `NUMERAL`, `CHARACTER` e `STRINGVAL` da VC; `'$'` é `EOF`.

```
  0  START       P' -> P '$'
  1  P           P -> LDE
  2  LDE_REC     LDE -> LDE DE
  3  LDE         LDE -> DE
  4  DE_DF       DE -> DF
  5  DE_DT       DE -> DT
  6  T_INTEGER   T -> 'integer'
  7  T_CHAR      T -> 'char'
  8  T_BOOLEAN   T -> 'boolean'
  9  T_STRING    T -> 'string'
 10  T_IDU       T -> IDU
 11  DT_ARRAY    DT -> 'type' IDD '=' 'array' '[' NUM ']' 'of' T
 12  DT_STRUCT   DT -> 'type' IDD '=' 'struct' NB '{' DC '}'
 13  DT_ALIAS    DT -> 'type' IDD '=' T
 14  DC_REC      DC -> DC ';' LI ':' T
 15  DC          DC -> LI ':' T
 16  DF          DF -> 'function' IDD NF '(' LP ')' ':' T MF B
 17  LP_REC      LP -> LP ',' IDD ':' T
 18  LP          LP -> IDD ':' T
 19  B           B -> '{' LDV LS '}'
 20  LDV_REC     LDV -> LDV DV
 21  LDV         LDV -> DV
 22  LS_REC      LS -> LS S
 23  LS          LS -> S
 24  DV          DV -> 'var' LI ':' T ';'
 25  LI_REC      LI -> LI ',' IDD
 26  LI          LI -> IDD
 27  S_IF        S -> 'if' '(' E ')' S
 28  S_IF_ELSE   S -> 'if' '(' E ')' S 'else' S
 29  S_WHILE     S -> 'while' MW '(' E ')' S
 30  S_DO_WHILE  S -> 'do' MW S 'while' '(' E ')' ';'
 31  S_BLOCK     S -> NB B
 32  S_ASSIGN    S -> LV '=' E ';'
 33  S_BREAK     S -> 'break' ';'
 34  S_CONTINUE  S -> 'continue' ';'
 35  S_RETURN    S -> 'return' E ';'
 36  E_AND       E -> E '&&' L
 37  E_OR        E -> E '||' L
 38  E_L         E -> L
 39  L_LT        L -> L '<' R
 40  L_GT        L -> L '>' R
 41  L_LE        L -> L '<=' R
 42  L_GE        L -> L '>=' R
 43  L_EQ        L -> L '==' R
 44  L_NE        L -> L '!=' R
 45  L_R         L -> R
 46  R_PLUS      R -> R '+' Y
 47  R_MINUS     R -> R '-' Y
 48  R_Y         R -> Y
 49  Y_TIMES     Y -> Y '*' F
 50  Y_DIVIDE    Y -> Y '/' F
 51  Y_F         Y -> F
 52  F_LV        F -> LV
 53  F_PRE_INC   F -> '++' LV
 54  F_PRE_DEC   F -> '--' LV
 55  F_POS_INC   F -> LV '++'
 56  F_POS_DEC   F -> LV '--'
 57  F_PAREN     F -> '(' E ')'
 58  F_CALL      F -> IDU MC '(' LE ')'
 59  F_MINUS     F -> '-' F
 60  F_NOT       F -> '!' F
 61  F_TRUE      F -> TRUE
 62  F_FALSE     F -> FALSE
 63  F_CHR       F -> CHR
 64  F_STR       F -> STR
 65  F_NUM       F -> NUM
 66  LE_REC      LE -> LE ',' E
 67  LE          LE -> E
 68  LV_FIELD    LV -> LV '.' ID
 69  LV_INDEX    LV -> LV '[' E ']'
 70  LV_IDU      LV -> IDU
 71  IDD         IDD -> Id
 72  IDU         IDU -> Id
 73  ID          ID -> Id
 74  TRUE        TRUE -> 'true'
 75  FALSE       FALSE -> 'false'
 76  CHR         CHR -> c
 77  STR         STR -> s
 78  NUM         NUM -> n
 79  NB          NB -> ϵ
 80  NF          NF -> ϵ
 81  MF          MF -> ϵ
 82  MC          MC -> ϵ
 83  MW          MW -> ϵ
```

### Diferenças em relação à gramática oficial (Gramática.pdf)

| # | Diferença | Justificativa |
|---|---|---|
| G1 | Regra 0 `P' -> P '$'` | Gramática aumentada do cap. 3: o estado após empilhar `'$'` é o `FINAL` da figura 4.6. Não altera a linguagem. |
| G2 | `'T'` em `DC` lido como o não terminal `T` | Decisão da VC: não existe terminal `T` no léxico, e o cap. 5 repete `'T'` onde só faz sentido o tipo do campo. Não altera a linguagem pretendida. |
| G3 | `LV -> LV '.' ID` com `ID -> Id`, em vez de `IDU` | O cap. 5 explica que o campo só pode ser resolvido pelo tipo da struct; com `IDU`, `p.x` acusaria "x não declarado", pois os campos ficam num nível já fechado. Não altera a linguagem. |
| G4 | Marcadores `NB`, `NF`, `MF`, `MC`, `MW` (regras ϵ) | Ações no meio de regras (caps. 5, 6 e 7). `NB` em struct (fig. 5.9) e em bloco-comando (fig. 6.14); `NF` no lugar do `NB` da função (fig. 7.18); `MF` antes do corpo (fig. 6.13); `MC` antes dos argumentos (fig. 6.23); `MW` no início dos laços (mesmo nome e posição da fig. 7.22), usado para validar `break`/`continue`. Não alteram a linguagem: a tabela continua com um único conflito. |
| G5 | **`S -> 'return' E ';'`** e a palavra reservada `return` | **Única alteração da linguagem.** Sem ela uma função não tem como devolver valor; como os parâmetros são passados por valor (cap. 7.1) e não há variáveis globais, nenhum programa teria efeito observável, e os exemplos do cap. 7.4 usam `return`. No léxico, `return` entrou em `KEYWORDS` na ordem alfabética (entre `of` e `string`), e `TokenKind.RETURN = 12` (os valores seguintes subiram uma unidade; a VC não depende dos números). |

Todo o resto foi mantido como na gramática oficial, mesmo onde ela restringe
os exemplos do livro (ver D4, D21 a D24): bloco com ao menos uma declaração e
um comando, função com ao menos um parâmetro, chamada com ao menos um
argumento, declaração de tipo sem `;` no fim, e nenhum comando-expressão.

## 3. Análise sintática

### Construção la-LR(1) (`lalr.py`)

1. **FIRST e anuláveis** por ponto fixo sobre as regras.
2. **Item LR(1)**: `(regra, ponto)` com um conjunto de look-aheads. Um estado é
   um dicionário `item -> look-aheads`.
3. **closure**: para cada item `A -> α . B β, s`, acrescenta `B -> . γ` com
   look-aheads `FIRST(β s)`; repete até não mudar nada (cap. 3.7).
4. **goto**: avança o ponto sobre cada símbolo; o resultado é o núcleo do estado destino.
5. **Fusão de núcleos**: o núcleo é o conjunto de itens sem os look-aheads. Se
   o goto produz um núcleo já existente, os look-aheads são unidos ao estado
   existente e, se algum for novo, o estado é reprocessado para propagá-lo. É o
   cálculo direto que o cap. 3.8 descreve ("reaproveitando estados já existentes
   e adicionando novos look-aheads"). Um teste constrói o LR(1) canônico
   completo, funde os estados de mesmo núcleo e confere que dá exatamente os
   mesmos estados e look-aheads.
6. **Tabela de Ação** codificada como na figura 3.19: `Action[q][a] > 0`
   empilha (ou, nas colunas de não terminais, é a transição após a redução),
   `< 0` reduz pela regra `-Action[q][a]`, `0` é erro. `Len[r]` e `Left[r]`
   são as tabelas auxiliares da figura 3.18. As colunas são os 50 terminais
   (os tokens da VC, sem `UNKNOWN`) seguidos dos 35 não terminais.

### Estatísticas (`python3 -m compilador --tabela`)

```
regras                   84
terminais                50
não terminais            35
estados                  171
empilhamentos            464
reduções                 876
transições               320
conflitos empilha/reduz  1
conflitos reduz/reduz    0
estado final             170
  estado 143, com 'else': conflito empilha/reduz; escolhido empilhar (estado 144), descartado reduzir por S -> 'if' '(' E ')' S
```

O LR(1) canônico da mesma gramática tem 549 estados; a fusão reduz para 171,
sem introduzir conflito reduz/reduz (cap. 3.8 mostra que a fusão só pode criar
conflitos desse tipo). A tabela é recalculada a cada execução (cerca de 30 ms).

### Else pendente

O único conflito é o clássico: no estado com os itens
`S -> 'if' '(' E ')' S .` e `S -> 'if' '(' E ')' S . 'else' S`, o
look-ahead `'else'` permite reduzir ou empilhar. A construção resolve todo
conflito empilha/reduz **empilhando** (e reduz/reduz pela regra de menor número,
mas não há nenhum), o que associa o `else` ao `if` mais próximo. Os conflitos
são contados e listados com o estado, o terminal, a escolha e a ação
descartada. Um teste confere que `if (a) if (b) x=1; else x=2;` reduz primeiro
um `S_IF_ELSE` (o interno) e depois um `S_IF`.

### Algoritmo (`parser.py`)

É o da figura 4.6. A pilha sintática guarda o estado e a posição
(linha, coluna) do símbolo de acesso; na redução, a posição do 1º símbolo da
regra é passada a `Semantics`, para as mensagens. O último terminal empilhado
também é passado: é dele que `IDD`, `IDU`, `ID`, `NUM`, `CHR` e `STR` tiram o
token secundário (ver D16).

### Mensagens de erro sintático

`linha L, coluna C: erro sintático: encontrado X; esperado: a, b, ...`.
Os esperados são os terminais com ação no estado onde o erro foi detectado,
mais os que seriam empilhados em qualquer estado percorrido com o mesmo token
desde o último empilhamento. Sem isso, as reduções feitas por causa dos
look-aheads fundidos esconderiam opções: em `y = (x + 2;` o analisador reduz `2`
até `E` antes de ver o erro, e o último estado só esperaria `)`, `&&` ou `||`.
Com a união, a mensagem lista também os operadores relacionais e aritméticos.

## 4. Análise de escopo

**Estrutura** (`scope.py`): `SymbolTable.levels` é a pilha de níveis da
figura 5.1; cada nível é um dicionário `nome -> Object` (o nome é o token
secundário do `Id`). `NewBlock`, `EndBlock`, `Define`, `Search` (só o nível
corrente) e `Find` (do corrente ao 0) seguem as figuras 5.4 a 5.7.

**Regras:**

| Situação | Regra | Ação |
|---|---|---|
| Declaração | `IDD -> Id` | `Search`; se achou, `ERR_REDECL` e usa um objeto avulso (D9); senão `Define`. Kind `NO_KIND_DEF_` (fig. 6.4). |
| Uso | `IDU -> Id` | `Find`; se não achou, `ERR_NOT_DECL` e `Define` no nível corrente com kind `UNIVERSAL_`, para não repetir o erro no bloco nem gerar erros de tipo (D19). |
| Campo | `ID -> Id` | Sem busca: resolvido pelo tipo em `LV '.' ID` (G3). |
| Programa | início | Nível 0 aberto antes da análise (D17). |
| Struct | `NB` antes de `'{'`; `EndBlock` em `DT_STRUCT` | Campos num nível próprio: podem repetir nomes externos, não podem repetir entre si. |
| Bloco-comando | `S -> NB B`; `EndBlock` na redução | Variáveis do bloco escondem as externas até o `'}'`. |
| Função | `NF` logo após o nome; `EndBlock` em `DF` | O nome fica no nível externo (já foi definido por `IDD`); parâmetros e variáveis locais ficam no mesmo nível, novo, pois o corpo `B` da função não tem `NB` (fig. 5.2). Um local com o nome de um parâmetro é redeclaração. Recursão é permitida: o kind `FUNCTION_` é dado em `NF` e o resto em `MF`, antes do corpo. |
| Laço | `MW` no início de `while`/`do` | Conta os laços abertos; `break`/`continue` fora de laço dão `ERR_NO_LOOP` (D15). |

Consequências: um nome só é visível depois da sua declaração. Não há
declaração antecipada, então funções mutuamente recursivas não são possíveis.
Em `var x: x;` ou `struct { x: x }`, o `x` declarado já esconde o tipo `x`
quando `T` é reduzido, e o resultado é `ERR_TYPE_EXPECTED`.

## 5. Análise de tipos

### Kinds e objetos

`Kind` reproduz a figura 6.1: `NO_KIND_DEF_, VAR_, PARAM_, FUNCTION_, FIELD_,
ARRAY_TYPE_, STRUCT_TYPE_, ALIAS_TYPE_, SCALAR_TYPE_, UNIVERSAL_`. `Object`
corresponde à figura 6.2 (os campos da união viram atributos):
`pType` (var, param, field), `pRetType` e `pParams` (function),
`pElemType` e `nNumElems` (array), `pFields` (struct) e `pBaseType` (alias).
Os tipos pré-definidos são as instâncias `pInteger`, `pChar`, `pBool`,
`pString` (kind `SCALAR_TYPE_`) e `pUniversal` (kind `UNIVERSAL_`, D7).

### Compatibilidade (`CheckTypes`)

Por nome (figura 6.16), considerando que um alias é **o mesmo tipo** que o seu
tipo base (D10): dois tipos são compatíveis se, depois de atravessar os aliases,
são o mesmo objeto, ou se algum é universal. Assim `type texto = string`
mistura-se livremente com `string`, mas dois `struct` ou dois `array`
declarados separadamente são incompatíveis, mesmo com estrutura igual.

### Regras implementadas

| Construção | Figura | Verificação |
|---|---|---|
| `T -> IDU` | 6.5 | o identificador deve ter kind de tipo (ou universal), senão `ERR_TYPE_EXPECTED` e `T.type = pUniversal` |
| `var`, parâmetros, campos | 6.6, 6.10, 6.12 | preenche kind e tipo de cada nome da lista |
| `array`, `struct`, alias | 6.8, 6.9, 6.11 | preenche `nNumElems`/`pElemType`, `pFields`, `pBaseType` |
| função | 6.13 | `NF`: kind `FUNCTION_` e novo nível; `MF`: `pRetType`, `pParams`, função corrente |
| literais | 6.7 | `true`/`false`: boolean; `c`: char; `s`: string; `n`: integer (o valor vem da tabela de constantes da VC) |
| `if`, `while`, `do-while` | 6.15 | condição boolean, senão `ERR_BOOL_TYPE_EXPECTED` |
| `LV = E;` | 6.15 | `CheckTypes(LV, E)`, senão `ERR_TYPE_MISMATCH` |
| `return E;` | extensão | `CheckTypes(E, retorno da função corrente)`, senão `ERR_RETURN_TYPE` |
| `&&`, `||` | 6.18 | operandos boolean; resultado boolean |
| `< > <= >= == !=` | 6.19 | operandos compatíveis entre si; resultado boolean |
| `+` | 6.20 | operandos compatíveis; integer ou string (concatenação); resultado: tipo do 1º |
| `- * /` | 6.20 | operandos compatíveis; integer; resultado: tipo do 1º |
| `++`/`--` (pré e pós), `-` unário | 6.21 | integer; resultado integer |
| `!` | 6.21 | boolean; resultado boolean |
| `LV . ID` | 6.22 | o tipo (sem alias) deve ser struct (`ERR_KIND_NOT_STRUCT`) e ter o campo (`ERR_FIELD_NOT_DECL`) |
| `LV [ E ]` | 6.22 | string dá char; senão deve ser array (`ERR_KIND_NOT_ARRAY`), resultado é o tipo do elemento; índice integer (`ERR_INVALID_INDEX_TYPE`) |
| `LV -> IDU` | 6.22 | deve ser variável ou parâmetro (`ERR_KIND_NOT_VAR`) |
| `IDU MC ( LE )` | 6.23 | `MC`: deve ser função (`ERR_KIND_NOT_FUNC`); cada argumento compatível com o parâmetro na mesma posição (`ERR_PARAM_TYPE`), nem a mais (`ERR_TOO_MANY_ARGS`) nem a menos (`ERR_TOO_FEW_ARGS`); o tipo da chamada é o retorno |

Em todas as regras que testam kind, um operando universal não gera mensagem e
o resultado também é universal. Esse é o mecanismo do cap. 6 contra erros em
cascata (testes `test_universal_type_avoids_cascades`).

### Lista de erros

| Código | Categoria | Mensagem (exemplo) |
|---|---|---|
| `ERR_LEXICAL` | léxico | `caractere inválido '#'` (mensagem do léxico da VC) |
| `ERR_SYNTAX` | sintático | `encontrado ';'; esperado: ')', '&&', ...` |
| `ERR_REDECL` | escopo | `'x' já foi declarado neste escopo` |
| `ERR_NOT_DECL` | escopo | `'z' não foi declarado` |
| `ERR_NO_LOOP` | escopo | `'break' fora de um comando de repetição` |
| `ERR_TYPE_EXPECTED` | tipo | `'a' não é um tipo` |
| `ERR_BOOL_TYPE_EXPECTED` | tipo | `a condição do if deve ser boolean, mas é integer` |
| `ERR_TYPE_MISMATCH` | tipo | `tipos incompatíveis em atribuição: boolean e integer` |
| `ERR_INVALID_TYPE` | tipo | `operador '-' não se aplica ao tipo string` |
| `ERR_KIND_NOT_STRUCT` | tipo | `acesso ao campo 'x' em valor do tipo integer, que não é struct` |
| `ERR_FIELD_NOT_DECL` | tipo | `o tipo ponto não tem campo 'z'` |
| `ERR_KIND_NOT_ARRAY` | tipo | `indexação de valor do tipo integer, que não é array nem string` |
| `ERR_INVALID_INDEX_TYPE` | tipo | `índice deve ser integer, mas é boolean` |
| `ERR_KIND_NOT_VAR` | tipo | `'f' não é variável nem parâmetro` |
| `ERR_KIND_NOT_FUNC` | tipo | `'a' não é função` |
| `ERR_TOO_MANY_ARGS` | tipo | `argumentos demais na chamada de 'f' (espera 2)` |
| `ERR_PARAM_TYPE` | tipo | `argumento 1 de 'f' deve ser integer, mas é string` |
| `ERR_TOO_FEW_ARGS` | tipo | `argumentos de menos na chamada de 'f' (espera 2, recebeu 1)` |
| `ERR_RETURN_TYPE` | tipo | `'f' deve retornar boolean, mas o return é integer` |

Os códigos são os do livro, mais `ERR_NO_LOOP` e `ERR_RETURN_TYPE`, que vêm de
construções sem regra de atributos no livro (`break`/`continue` e `return`).

## 6. Geração de código

**Não implementada nesta entrega**, por decisão do enunciado ("a parte e
capítulos referentes a geração de código não vão ser abordadas neste momento").
Por isso não há instruções da máquina virtual, endereçamento (`nIndex`,
`nSize`), labels, `BEGIN_FUNC`/`END_FUNC` nem testes de código gerado.

O que já ficou pronto para o trabalho futuro:

- os marcadores `NF`, `MF` e `MW` têm o nome e a posição das figuras 7.18 e
  7.22. Faltam só `MT` e `ME` (fig. 7.21), que não têm efeito em escopo nem em tipos;
- `Semantics` empilha um nó para todo não terminal (convenção do cap. 4.1), de
  modo que os atributos de código (`size`, `offset`, `label`) podem ser
  acrescentados sem mudar os `TopSem` existentes;
- `MF` já guarda a função corrente (`curFunction`), que a fig. 7.19 usa para
  numerar as variáveis;
- as inconsistências do cap. 7 encontradas na leitura estão em D12 a D15 e D25,
  com a decisão proposta.

## 7. Decisões e ambiguidades

**Implementação e escopo do trabalho**

- **D0. Python em vez de C++11; sem geração de código.** Decididos com o
  usuário antes da implementação: a VC deste repositório é Python, e o
  enunciado exclui o cap. 7. A estrutura de código do livro foi mantida:
  tabela `Action`/`Len`/`Left`, pilha semântica com `PushSem`/`PopSem`/`TopSem`
  e `Semantics` com um `case` por regra (o `match` do Python 3.10). As
  adaptações a Python são vetores no lugar de listas encadeadas e objetos
  referenciados no lugar de ponteiros.

**Gramática**

- **D1. `'T'` em `DC`** é o não terminal `T` (G2, decisão da VC).
- **D2. Acesso a campo com `ID`**, não `IDU` (G3).
- **D3. `return`** acrescentado (G5). Não se verifica se toda execução de uma
  função termina em `return`: isso exige análise de fluxo, que o livro não trata.
- **D4. `B -> '{' LDV LS '}'` exige uma declaração e um comando.** Mantido, pois
  alterar não é indispensável para as fases. Os exemplos do livro que violam a
  regra (blocos de `while` sem `var`, por exemplo) foram reescritos com uma
  variável local no bloco, o que às vezes é artificial (`troca` em
  `bsort.ssl`). `if (b) { a = 1; }` é erro sintático, mas `if (b) a = 1;` não.
- **D21. Sem `;` após declaração de tipo.** A gramática oficial não tem `;` em
  `DT` (o exemplo 7.4.4 e o `tipos.ssl` da VC têm); vale a gramática.
- **D22. Função com ao menos um parâmetro e chamada com ao menos um argumento**
  (`LP` e `LE` não têm regra ϵ). O `tipos.ssl` da VC (`main()`) só servia ao léxico.
- **D23. Não há comando-expressão.** A figura 7.5 fala em `POP` para "expressões
  tratadas como comandos", mas a gramática não tem `S -> E ';'`, então `i++;` e
  `f(x);` são erros sintáticos (o `fatorial.ssl` da VC usa `i++;`). Mantido, por
  não ser indispensável: `i = i + 1;` e `x = f(x);` cobrem esses usos.
- **D24. `do S while (E);`**: o `while` sem aspas na gramática é a palavra
  reservada.

**Análise sintática**

- **D16. Token secundário na redução.** As figuras 5.8 e 6.7 usam a global
  `tokenSecundario` ao reduzir `IDD -> Id`. Num analisador LR(1) o léxico já
  leu o look-ahead nesse momento, e a global seria a do token seguinte. O
  analisador guarda o último terminal **empilhado**, que nessas regras é sempre
  o `Id`/literal reduzido, porque nenhuma redução ocorre entre o empilhamento
  dele e a redução.
- **D18. Sinal de `TopSem`.** A fig. 4.9 usa `TopSem(1)` para o nó abaixo do
  topo, e a fig. 6.13 usa `TopSem(-1)`. Usamos a convenção da fig. 4.9 (`0` = topo).
- **D30. Política de conflitos:** empilha/reduz → empilha; reduz/reduz → menor
  regra (não ocorre).

**Escopo**

- **D9. Redeclaração (fig. 6.4).** O livro faz `p = Search(name)` e, mesmo
  quando acha, executa `p->eKind = NO_KIND_DEF_`, ou seja, apaga o kind do
  identificador original, e a declaração seguinte o sobrescreve. Ao detectar a
  redeclaração, criamos um objeto avulso, fora da tabela, que recebe kind e
  tipo da declaração errada sem estragar a original.
- **D17. Nível 0.** `nCurrentLevel` começa em `-1` (fig. 5.3) e nenhuma regra
  chama `NewBlock()` para as declarações globais. Chamamos ao criar a análise.
- **D19. Identificador não declarado.** O `Define` da fig. 5.8 deixa o kind
  indefinido; em `T -> IDU` isso geraria `ERR_TYPE_EXPECTED` e, em `MC`,
  `ERR_KIND_NOT_FUNC` (a fig. 6.23 não exclui o universal), ambos em cascata.
  O objeto recebe kind `UNIVERSAL_`, e `MC` não acusa erro para ele. Se o nome
  for declarado depois no mesmo nível (`type a = b type b = integer`), a
  declaração não é acusada como redeclaração: o erro real (uso antes da
  declaração) já foi dado.
- **D5. NF × NB na função.** As figs. 5.10 e 6.13 usam `NB` após o nome da
  função; a fig. 7.18 o substitui por `NF`, que chama `NewBlock()` e já dá o
  kind `FUNCTION_` (no PDF lido, o `NewBlock()` está em `NF`; o `MF` da mesma
  figura ainda chama o nó de `NB` em `TopSem(-2)`). Usamos `NF`, como no cap. 7.
  O novo nível precisa existir antes de `LP` para os parâmetros não caírem no
  nível da função.
- **D15. `break`/`continue`.** Aparecem na fig. 7.5, mas sem regra de atributos
  em nenhum capítulo. Acrescentamos a verificação de que estão dentro de um
  laço, com o marcador `MW` da fig. 7.22. Para a geração de código: o
  `continue` de um `do-while` deve desviar para a avaliação da condição, que
  fica **depois** do corpo (`JMP_FW`), e não para o início (`JMP_BW`).

**Tipos**

- **D7. Tipo universal.** Na fig. 6.3 ele tem kind `SCALAR_TYPE_`; então
  `t->eKind != UNIVERSAL_` (fig. 6.22) é verdadeiro para ele, e `u.x` ou `u[0]`
  de um valor universal acusariam erro em cascata. Ele tem kind `UNIVERSAL_`.
- **D8. Listas por `pNext` (figs. 6.6 a 6.13).** Parâmetros e variáveis locais
  estão no mesmo nível, então a cadeia `pNext` que começa no 1º parâmetro
  continua pelas variáveis locais, e `MC`/`LE` contariam as locais como
  parâmetros (`ERR_TOO_FEW_ARGS` indevido). Também o laço de `DV`
  (`while p && p->eKind == NO_KIND_DEF_`) depende da ordem da cadeia. As listas
  `LI.list`, `LP.list`, `DC.list`, `pParams` e `pFields` são vetores próprios.
- **D10. `CheckTypes`.** A versão estrutural (fig. 6.17) entra em laço infinito
  em structs (o `while` não avança `f1` nem `f2`) e só compara aliases com
  aliases. A versão por nome (fig. 6.16) torna `type texto = string`
  incompatível com `string`, o que contraria a ideia de "sinônimo" (cap. 6).
  Usamos a compatibilidade por nome, atravessando aliases.
- **D11. Alias em acesso a campo e índice.** A fig. 6.22 testa
  `t->eKind != STRUCT_TYPE_` e `t == pString` direto no tipo do left-value,
  então um alias de struct, de array ou de string não poderia ser acessado.
  O teste é feito no tipo base.
- **D20. `LE` (fig. 6.23).** Além do problema de D8, `LE.n` não é atribuído
  quando `MC.err` é verdadeiro, e `LE -> LE ',' E` lê `LE.param` em vez de
  `LE1.param`. `LE` guarda o nó de `MC` e o número `n` de argumentos já lidos.
  O n-ésimo argumento é conferido com `pParams[n-1]`.
- **D26. Tipo do resultado aritmético com erro.** Pela fig. 6.20,
  `R0.type = R1.type` mesmo quando o operando é inválido; `a = s - 1` (com `s`
  string) gera `ERR_TYPE_MISMATCH`, `ERR_INVALID_TYPE` e o erro da atribuição.
  Mantido como no livro.
- **D27. Relacionais** aceitam quaisquer tipos compatíveis (strings, chars,
  booleans, structs), como na fig. 6.19.
- **D28. `!`** com operando não booleano dá `ERR_INVALID_TYPE` (fig. 6.21), e
  não `ERR_BOOL_TYPE_EXPECTED`.
- **D29. Tipos recursivos** (`type t = struct { x: t }`) dão `ERR_TYPE_EXPECTED`:
  o tipo só ganha kind ao fim da sua declaração.

**Capítulo 7 (registradas para o trabalho futuro; nada disso foi implementado)**

- **D12. `true`/`false`:** a fig. 7.7 gera `LOAD_TRUE`/`LOAD_FALSE`, e a 7.26
  gera `LOAD_CONST` sem token secundário (os literais booleanos não estão na
  tabela de constantes da VC). Proposta: `LOAD_TRUE`/`LOAD_FALSE`.
- **D13. `BEGIN_FUNC` n p v:** o texto e a fig. 7.18 dizem que `v` inclui os
  parâmetros (`nVars` começa em `LP.size`), mas os exemplos 7.4 informam só os
  locais (fatorial: `BEGIN_FUNC 0 1 2`, com 1 parâmetro e 2 locais). Proposta:
  seguir o texto e a figura.
- **D14. Indexação de string:** está nas regras de tipos (fig. 6.22, e foi
  implementada), mas a geração com left-values (fig. 7.27) só trata arrays, e a
  fig. 7.27 gera `LOAD_REF` com o tamanho do tipo em vez do índice da
  variável. Proposta: strings via `CHAR_AT`/`SET_CHAR` (fig. 7.5) ou `CALL_LIB`,
  como o livro recomenda para linguagens com tipos estruturados.
- **D25. Exemplos 7.4**, reescritos em `examples/` para obedecer à gramática e
  às regras de tipos:
  - *Fatorial*: a função se chama `fatorial`, mas `somaFat` chama `fat`. Usamos `fat`.
  - *strcmp*: `return s1[i] - s2[i]` subtrai chars (inválido pela fig. 6.20 e
    incompatível com o retorno integer), e `'\0'` não é um lexema `c`
    (`''' any '''` tem um único caractere). O exemplo recebe os comprimentos e
    devolve -1, 0 ou 1.
  - *strinv*: depende de `'\0'`, começa com `l` igual ao comprimento (índice
    fora da string) e faz `l++` em vez de `l--`. O exemplo recebe o comprimento.
  - *bSort*: usa o parâmetro `n` como temporário da troca (destrói o limite do
    laço), declara `v` sem usar e não avança `i`/`j` quando não há troca, o que
    dá laço infinito. Reescrito como ordenação por trocas, com a temporária `v`.
  - Todos tinham blocos sem declaração (D4) e `type ...;` com `;` (D21).

## 8. Como compilar, executar e testar

Requer **Python 3.10+** (usa `match`), sem instalação nem dependências. Não
há etapa de compilação: a tabela la-LR(1) é construída na execução. Todos os
comandos rodam na **raiz do repositório** (onde está `lexer/`).

```bash
# compilar (verificar) um programa: código de saída 0 se correto, 1 se houver erro
python3 -m compilador compilador/examples/tipos.ssl

# também listar tipos e funções declarados no nível 0, com seus kinds e tipos
python3 -m compilador compilador/examples/tipos.ssl --simbolos

# modo léxico: exatamente a saída da VC (python3 main.py ...)
python3 -m compilador compilador/examples/fatorial.ssl --tokens [--tables]

# estatísticas e conflitos da tabela; regras numeradas
python3 -m compilador --tabela
python3 -m compilador --gramatica

# entrada padrão
echo 'type t = integer' | python3 -m compilador -
```

Testes (um único módulo para a VF; o `unittest` da raiz roda VC e VF juntos):

```bash
python3 -m unittest -v                                  # VC (35) + VF (48)
python3 -m unittest compilador.tests.test_compiler -v   # só a VF
```

| Grupo | O que verifica |
|---|---|
| `TableTests` | exatamente 1 conflito empilha/reduz (o do `else`, resolvido por empilhar) e 0 reduz/reduz; toda regra é reduzida em algum estado; estado final; **la-LR(1) = fusão do LR(1) canônico**; toda regra tem `case` em `Semantics` (os exemplos válidos reduzem todas as 83 regras reduzíveis) |
| `SyntaxTests` | exemplos válidos sem erro; linha, coluna, encontrado e esperados; esperados após reduções la-LR; `;` faltando; fim de arquivo; programa vazio; else pendente; precedência e associatividade; restrições da gramática oficial (D4, D21 a D23); erros léxicos impedem o sintático e são todos listados |
| `ScopeTests` | redeclaração; parâmetros e locais no mesmo nível; nome da função no nível externo e recursão; sombreamento em bloco e fim do bloco; não declarado (uma vez por bloco); campos em nível próprio; acesso a campo sem busca de escopo; uso antes da declaração; `break`/`continue` |
| `TypeTests` | expressões válidas (alias = base, string indexada, struct/array aninhados, concatenação); um caso para cada código de erro de tipo; universal sem cascata; acúmulo de erros com linha; os exemplos de erro cobrem **todos** os códigos de escopo e de tipo |
| `ExampleAndCliTests` | exemplos de erro; código de saída; `--tokens` idêntico à VC; `return` reservado; `--tabela`; `--simbolos` |

Verificação estática, no lugar do `-Wall -Wextra -Wpedantic` do C++:

```bash
ruff check --select E,W,F,B --line-length 100 compilador/   # All checks passed!
python3 -W error -m unittest                                 # OK
```

Com `-W error`, o Python avisa de um arquivo não fechado em `main.py` da VC
(`open(...).read()`), que o modo `--tokens` reaproveita. O aviso não altera
o resultado e não foi corrigido para manter a VC intacta.

## 9. Exemplos de entrada e saída

Programas em `compilador/examples/`:

| Arquivo | Conteúdo |
|---|---|
| `fatorial.ssl`, `strcmp.ssl`, `strinv.ssl`, `bsort.ssl` | exemplos 7.4.1 a 7.4.4 do livro, reescritos (D25) |
| `tipos.ssl` | todos os tipos, aliases, struct de struct, array de struct, string indexada, concatenação, operadores lógicos, relacionais e aritméticos, `do`/`break`/`continue` |
| `erro_lexico.ssl`, `erro_sintatico.ssl`, `erro_escopo.ssl`, `erro_tipos.ssl` | um erro de cada natureza (os dois últimos cobrem todos os códigos) |

**Programa correto** (`tipos.ssl --simbolos`):

```
Programa correto: nenhum erro léxico, sintático, de escopo ou de tipo.

DECLARAÇÕES DO NÍVEL 0
  vetor        type array [10] of integer
  ponto        type struct { x: integer; y: integer; nome: string }
  linha        type struct { a: ponto; b: ponto }
  caminho      type array [5] of linha
  texto        type alias de string
  inteiro      type alias de integer
  dist         function (p: ponto, q: ponto): inteiro
  inicial      function (t: texto): char
  teste        function (c: caminho, v: vetor, s: texto): boolean
```

**Erros léxicos** (`erro_lexico.ssl`): todos listados, sem análise sintática.

```
linha 4, coluna 9: erro léxico: caractere inválido '#'
linha 5, coluna 12: erro léxico: símbolo inválido '&' (esperado '&&')
2 erro(s).
```

**Erro sintático** (`erro_sintatico.ssl`, linha 4: `y = (x + 2;`):

```
linha 4, coluna 13: erro sintático: encontrado ';'; esperado: ')', '&&', '||', '<', '>', '<=', '>=', '!=', '==', '+', '-', '*', '/'
1 erro(s).
```

**Erros de escopo** (`erro_escopo.ssl`):

```
type par = struct { a: integer; a: char }

function f(x: integer, x: integer): integer
{
  var x, y: integer;
  y = z;
  {
    var y: boolean;
    y = w;
  }
  break;
  return y;
}

function f(n: integer): integer
{
  var m: integer;
  m = g(n);
  return m;
}
```

```
linha 1, coluna 33: erro escopo: 'a' já foi declarado neste escopo
linha 3, coluna 24: erro escopo: 'x' já foi declarado neste escopo
linha 5, coluna 7: erro escopo: 'x' já foi declarado neste escopo
linha 6, coluna 7: erro escopo: 'z' não foi declarado
linha 9, coluna 9: erro escopo: 'w' não foi declarado
linha 11, coluna 3: erro escopo: 'break' fora de um comando de repetição
linha 15, coluna 10: erro escopo: 'f' já foi declarado neste escopo
linha 18, coluna 7: erro escopo: 'g' não foi declarado
8 erro(s).
```

Note que `y = z` e `return y` não geram erro de tipo: `z` passa a ser
universal; o `y` do bloco interno (boolean) esconde o externo só até o `}`; e a
chamada `g(n)` a uma função não declarada não gera `ERR_KIND_NOT_FUNC`.

**Erros de tipo** (`erro_tipos.ssl`, trecho e saída):

```
  var t: a;              linha 9, coluna 10: erro tipo: 'a' não é um tipo
  b = 1;                 linha 10, coluna 7: erro tipo: tipos incompatíveis em atribuição: boolean e integer
  if (a) b = true;       linha 11, coluna 7: erro tipo: a condição do if deve ser boolean, mas é integer
  while ("x") b = false; linha 12, coluna 10: erro tipo: a condição do while deve ser boolean, mas é string
  v[true] = 1;           linha 13, coluna 5: erro tipo: índice deve ser integer, mas é boolean
  p.z = 2;               linha 14, coluna 5: erro tipo: o tipo ponto não tem campo 'z'
  a.x = 3;               linha 15, coluna 5: erro tipo: acesso ao campo 'x' em valor do tipo integer, que não é struct
  a[0] = 4;              linha 16, coluna 3: erro tipo: indexação de valor do tipo integer, que não é array nem string
  b = a && b;            linha 17, coluna 7: erro tipo: o operando de '&&' deve ser boolean, mas é integer
  a = s - 1;             linha 18, coluna 11: erro tipo: tipos incompatíveis em '-': string e integer
                         linha 18, coluna 7: erro tipo: operador '-' não se aplica ao tipo string
                         linha 18, coluna 7: erro tipo: tipos incompatíveis em atribuição: integer e string
  a = -b;                linha 19, coluna 8: erro tipo: operador '-' unário não se aplica ao tipo boolean
  b = !a;                linha 20, coluna 8: erro tipo: operador '!' não se aplica ao tipo integer
  a = b++;               linha 21, coluna 7: erro tipo: operador '++' não se aplica ao tipo boolean
  f = b;                 linha 22, coluna 3: erro tipo: 'f' não é variável nem parâmetro
  a = a(1);              linha 23, coluna 7: erro tipo: 'a' não é função
  b = f(1);              linha 24, coluna 7: erro tipo: argumentos de menos na chamada de 'f' (espera 2, recebeu 1)
  b = f(1, "x", 2);      linha 25, coluna 17: erro tipo: argumentos demais na chamada de 'f' (espera 2)
  b = f("x", 1);         linha 26, coluna 9: erro tipo: argumento 1 de 'f' deve ser integer, mas é string
                         linha 26, coluna 14: erro tipo: argumento 2 de 'f' deve ser string, mas é integer
  return 0;              linha 27, coluna 10: erro tipo: 'f' deve retornar boolean, mas o return é integer
```

## 10. Revisão final: regras × ações semânticas

- **Toda regra da gramática tem ação** em `Semantics`: as 83 regras reduzíveis
  têm `case` (a 0 nunca é reduzida, porque a análise termina ao empilhar `'$'`).
  Regras sem atributos, como `P -> LDE` ou `B -> '{' LDV LS '}'`, só trocam
  os nós da pilha. O `case _` lança erro, e um teste confere que os exemplos
  válidos reduzem todas as 83.
- **Regras de atributos do cap. 5:** fig. 5.8 (`IDD`, `IDU`, `ID`), 5.9 (`NB`
  em struct) e 5.10 (`NB` da função, substituído por `NF`, D5) foram
  implementadas; as funções 5.4 a 5.7 estão em `SymbolTable`.
- **Cap. 6:** figs. 6.4 a 6.15 e 6.18 a 6.23 foram implementadas, com as
  correções D7 a D11, D19 e D20; `CheckTypes` (6.16/6.17) com D10.
- **Cap. 7:** fora do escopo (seção 6). Dele foram usados `NF`, `MF` (com
  `curFunction`) e `MW`. O texto sobre `break`/`continue` (fig. 7.5) originou
  `ERR_NO_LOOP`. `MT`, `ME`, `newLabel` e as figuras 7.11 a 7.29 (tamanhos,
  endereços e emissão de código) não foram implementados, por serem só de
  geração de código.
