from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from database import (
    atualizar_progresso_meta,
    atualizar_transacao,
    buscar_dashboard,
    buscar_metas,
    buscar_transacao,
    buscar_transacoes,
    criar_meta,
    excluir_meta,
    excluir_transacao,
    salvar_transacao,
)

order_router = APIRouter(prefix="/transacoes", tags=["Transações"])
api_router = APIRouter(prefix="/api", tags=["Painel e metas"])

CATEGORIAS = {
    "receita": [
        "Salário",
        "Freelance",
        "Investimentos",
        "Vendas",
        "Outros",
    ],
    "despesa": [
        "Moradia",
        "Alimentação",
        "Transporte",
        "Saúde",
        "Educação",
        "Lazer",
        "Contas",
        "Compras",
        "Outros",
    ],
}


class TransacaoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: Literal["receita", "despesa"]
    descricao: str = Field(min_length=2, max_length=100)
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    categoria: str = Field(min_length=2, max_length=40)
    data: date = Field(default_factory=date.today)

    @field_validator("descricao", "categoria", mode="before")
    @classmethod
    def limpar_texto(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validar_categoria(self):
        if self.categoria not in CATEGORIAS[self.tipo]:
            raise ValueError(f"Categoria inválida para {self.tipo}.")
        return self


class MetaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(min_length=3, max_length=80)
    valor_alvo: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    prazo: date | None = None


class ProgressoMetaInput(BaseModel):
    valor_atual: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


def _centavos(valor: Decimal) -> int:
    return int(valor * 100)


def _valor_reais(valor_centavos: int) -> float:
    return valor_centavos / 100


def _formatar_transacao(row: dict) -> dict:
    return {
        "id": row["id"],
        "tipo": row["tipo"],
        "descricao": row["descricao"],
        "valor": _valor_reais(row["valor_centavos"]),
        "categoria": row["categoria"],
        "data": row["data"],
    }


def _formatar_meta(row: dict) -> dict:
    return {
        "id": row["id"],
        "nome": row["nome"],
        "valor_alvo": _valor_reais(row["valor_alvo_centavos"]),
        "valor_atual": _valor_reais(row["valor_atual_centavos"]),
        "prazo": row["prazo"],
        "criado_em": row["criado_em"],
    }


@order_router.get("/lista", summary="Listar e filtrar transações")
def listar_transacoes(
    mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    tipo: Literal["receita", "despesa"] | None = None,
    categoria: str | None = Query(default=None, min_length=2, max_length=40),
):
    rows = buscar_transacoes(mes=mes, tipo=tipo, categoria=categoria)
    return {"transacoes": [_formatar_transacao(row) for row in rows]}


@order_router.post("/nova", status_code=201, summary="Cadastrar uma transação")
def criar_transacao(nova_transacao: TransacaoInput):
    transacao_id = salvar_transacao(
        nova_transacao.tipo,
        nova_transacao.descricao,
        _centavos(nova_transacao.valor),
        nova_transacao.categoria,
        nova_transacao.data,
    )
    row = buscar_transacao(transacao_id)
    return {"mensagem": "Transação cadastrada.", "transacao": _formatar_transacao(row)}


@order_router.put("/{transacao_id}", summary="Editar uma transação")
def editar_transacao(transacao_id: int, dados: TransacaoInput):
    updated = atualizar_transacao(
        transacao_id,
        dados.tipo,
        dados.descricao,
        _centavos(dados.valor),
        dados.categoria,
        dados.data,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    row = buscar_transacao(transacao_id)
    return {"transacao": _formatar_transacao(row)}


@order_router.delete("/{transacao_id}", status_code=204, summary="Excluir uma transação")
def remover_transacao(transacao_id: int):
    if not excluir_transacao(transacao_id):
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    return Response(status_code=204)


@api_router.get("/categorias", summary="Listar categorias disponíveis")
def listar_categorias():
    return {"categorias": CATEGORIAS}


@api_router.get("/dashboard", summary="Consultar resumo financeiro e gráficos")
def dashboard(
    mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
):
    mes_atual = mes or date.today().strftime("%Y-%m")
    return buscar_dashboard(mes_atual)


@api_router.get("/metas", summary="Listar metas financeiras")
def listar_metas():
    return {"metas": [_formatar_meta(row) for row in buscar_metas()]}


@api_router.post("/metas", status_code=201, summary="Criar uma meta financeira")
def criar_meta_financeira(dados: MetaInput):
    meta_id = criar_meta(
        dados.nome,
        _centavos(dados.valor_alvo),
        dados.prazo,
    )
    meta = next(row for row in buscar_metas() if row["id"] == meta_id)
    return {"meta": _formatar_meta(meta)}


@api_router.put("/metas/{meta_id}/progresso", summary="Atualizar o progresso de uma meta")
def atualizar_meta(meta_id: int, dados: ProgressoMetaInput):
    updated = atualizar_progresso_meta(meta_id, _centavos(dados.valor_atual))
    if not updated:
        raise HTTPException(status_code=404, detail="Meta não encontrada.")
    meta = next(row for row in buscar_metas() if row["id"] == meta_id)
    return {"meta": _formatar_meta(meta)}


@api_router.delete("/metas/{meta_id}", status_code=204, summary="Excluir uma meta")
def remover_meta(meta_id: int):
    if not excluir_meta(meta_id):
        raise HTTPException(status_code=404, detail="Meta não encontrada.")
    return Response(status_code=204)
