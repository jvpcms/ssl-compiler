"""Objetos dos identificadores e Tabela de Símbolos (caps. 5 e 6).

Adaptações a Python em relação ao livro:
  - cada nível da tabela é um dicionário nome -> object (insere e busca como a
    lista encadeada das figuras 5.3 a 5.7, mas sem percorrer a lista);
  - listas de campos e de parâmetros são vetores (list) guardados no próprio
    objeto, e não a cadeia pNext da tabela (ver README, decisão D8);
  - os objects vivem enquanto alguém os referencia, então EndBlock() pode
    descartar o nível sem perder os campos e parâmetros (fig. 5.4).
"""
from __future__ import annotations

from enum import IntEnum
from typing import Optional


class Kind(IntEnum):
    """t_kind (figura 6.1)."""
    NO_KIND_DEF_ = -1
    VAR_ = 0
    PARAM_ = 1
    FUNCTION_ = 2
    FIELD_ = 3
    ARRAY_TYPE_ = 4
    STRUCT_TYPE_ = 5
    ALIAS_TYPE_ = 6
    SCALAR_TYPE_ = 7
    UNIVERSAL_ = 8


TYPE_KINDS = (Kind.ARRAY_TYPE_, Kind.STRUCT_TYPE_, Kind.ALIAS_TYPE_, Kind.SCALAR_TYPE_)


def IS_TYPE_KIND(k: Kind) -> bool:
    return k in TYPE_KINDS


class Object:
    """struct object (figura 6.2). Só os campos do kind corrente são usados.

    nName  -- token secundário do identificador (-1 nos tipos pré-definidos)
    eKind  -- kind
    pType                 Var, Param, Field
    pRetType, pParams     Function (pParams é a lista de parâmetros, em ordem)
    pElemType, nNumElems  Array
    pFields               Struct (lista de campos, em ordem)
    pBaseType             Alias
    """

    def __init__(self, nName: int, eKind: Kind = Kind.NO_KIND_DEF_, label: str = "") -> None:
        self.nName = nName
        self.eKind = eKind
        self.label = label                       # nome dos tipos pré-definidos
        self.pType: Optional[Object] = None
        self.pRetType: Optional[Object] = None
        self.pParams: list[Object] = []
        self.pElemType: Optional[Object] = None
        self.nNumElems = 0
        self.pFields: list[Object] = []
        self.pBaseType: Optional[Object] = None


# Instâncias dos tipos pré-definidos (figura 6.3). O universal tem kind
# UNIVERSAL_ (e não SCALAR_TYPE_ como na figura) para não gerar erros em cascata.
pInteger = Object(-1, Kind.SCALAR_TYPE_, "integer")
pChar = Object(-1, Kind.SCALAR_TYPE_, "char")
pBool = Object(-1, Kind.SCALAR_TYPE_, "boolean")
pString = Object(-1, Kind.SCALAR_TYPE_, "string")
pUniversal = Object(-1, Kind.UNIVERSAL_, "universal")


class SymbolTable:
    """Pilha de níveis de escopo (figura 5.1)."""

    def __init__(self) -> None:
        self.levels: list[dict[int, Object]] = []
        self.nCurrentLevel = -1

    def NewBlock(self) -> int:
        self.levels.append({})
        self.nCurrentLevel += 1
        return self.nCurrentLevel

    def EndBlock(self) -> int:
        self.levels.pop()
        self.nCurrentLevel -= 1
        return self.nCurrentLevel

    def Define(self, aName: int) -> Object:
        obj = Object(aName)
        self.levels[self.nCurrentLevel][aName] = obj
        return obj

    def Search(self, aName: int) -> Optional[Object]:
        """Busca só no nível corrente (declaração)."""
        return self.levels[self.nCurrentLevel].get(aName)

    def Find(self, aName: int) -> Optional[Object]:
        """Busca do nível corrente para os externos (uso)."""
        for level in reversed(self.levels):
            if aName in level:
                return level[aName]
        return None


def base_type(t: Object) -> Object:
    """Tipo base de um tipo, atravessando os sinônimos (alias)."""
    while t.eKind == Kind.ALIAS_TYPE_:
        assert t.pBaseType is not None
        t = t.pBaseType
    return t


def CheckTypes(t1: Object, t2: Object) -> bool:
    """Compatibilidade por nome (figura 6.16), considerando um alias o mesmo tipo
    que o seu tipo base (README, decisão D10)."""
    if t1 is t2:
        return True
    if t1 is pUniversal or t2 is pUniversal:
        return True
    if t1.eKind == Kind.UNIVERSAL_ or t2.eKind == Kind.UNIVERSAL_:
        return True
    b1, b2 = base_type(t1), base_type(t2)
    return b1 is b2 or b1.eKind == Kind.UNIVERSAL_ or b2.eKind == Kind.UNIVERSAL_
