import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).with_name("financas.db")


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with _connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL CHECK (tipo IN ('receita', 'despesa')),
                descricao TEXT NOT NULL,
                valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
                categoria TEXT NOT NULL DEFAULT 'Outros',
                data TEXT
            )
            """
        )

        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(transacoes)")
        }
        if "categoria" not in columns:
            connection.execute(
                "ALTER TABLE transacoes "
                "ADD COLUMN categoria TEXT NOT NULL DEFAULT 'Outros'"
            )
        if "data" not in columns:
            connection.execute("ALTER TABLE transacoes ADD COLUMN data TEXT")
        connection.execute(
            "UPDATE transacoes SET data = date('now', 'localtime') WHERE data IS NULL"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                valor_alvo_centavos INTEGER NOT NULL CHECK (valor_alvo_centavos > 0),
                valor_atual_centavos INTEGER NOT NULL DEFAULT 0
                    CHECK (valor_atual_centavos >= 0),
                prazo TEXT,
                criado_em TEXT NOT NULL DEFAULT (date('now', 'localtime'))
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_transacoes_data ON transacoes(data)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_transacoes_tipo_categoria "
            "ON transacoes(tipo, categoria)"
        )


def _transaction_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def salvar_transacao(
    tipo: str,
    descricao: str,
    valor_centavos: int,
    categoria: str,
    data_transacao: date,
) -> int:
    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO transacoes (tipo, descricao, valor_centavos, categoria, data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                tipo,
                descricao,
                valor_centavos,
                categoria,
                data_transacao.isoformat(),
            ),
        )
        return int(cursor.lastrowid)


def buscar_transacao(transacao_id: int) -> dict | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM transacoes WHERE id = ?", (transacao_id,)
        ).fetchone()
        return _transaction_dict(row) if row else None


def buscar_transacoes(
    mes: str | None = None,
    tipo: str | None = None,
    categoria: str | None = None,
) -> list[dict]:
    conditions = []
    parameters: list[str] = []
    if mes:
        conditions.append("substr(data, 1, 7) = ?")
        parameters.append(mes)
    if tipo:
        conditions.append("tipo = ?")
        parameters.append(tipo)
    if categoria:
        conditions.append("categoria = ?")
        parameters.append(categoria)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with _connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, tipo, descricao, valor_centavos, categoria, data
            FROM transacoes
            {where_clause}
            ORDER BY data DESC, id DESC
            """,
            parameters,
        ).fetchall()
        return [_transaction_dict(row) for row in rows]


def atualizar_transacao(
    transacao_id: int,
    tipo: str,
    descricao: str,
    valor_centavos: int,
    categoria: str,
    data_transacao: date,
) -> bool:
    with _connection() as connection:
        cursor = connection.execute(
            """
            UPDATE transacoes
            SET tipo = ?, descricao = ?, valor_centavos = ?, categoria = ?, data = ?
            WHERE id = ?
            """,
            (
                tipo,
                descricao,
                valor_centavos,
                categoria,
                data_transacao.isoformat(),
                transacao_id,
            ),
        )
        return cursor.rowcount > 0


def excluir_transacao(transacao_id: int) -> bool:
    with _connection() as connection:
        cursor = connection.execute(
            "DELETE FROM transacoes WHERE id = ?", (transacao_id,)
        )
        return cursor.rowcount > 0


def buscar_dashboard(mes: str) -> dict:
    with _connection() as connection:
        totals = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor_centavos ELSE 0 END), 0)
                    AS receitas,
                COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor_centavos ELSE 0 END), 0)
                    AS despesas,
                COUNT(*) AS quantidade
            FROM transacoes
            WHERE substr(data, 1, 7) = ?
            """,
            (mes,),
        ).fetchone()
        top_expenses = connection.execute(
            """
            SELECT categoria, SUM(valor_centavos) AS total_centavos
            FROM transacoes
            WHERE tipo = 'despesa' AND substr(data, 1, 7) = ?
            GROUP BY categoria
            ORDER BY total_centavos DESC, categoria
            LIMIT 5
            """,
            (mes,),
        ).fetchall()

        month_date = datetime.strptime(mes, "%Y-%m").date().replace(day=1)
        first_month = month_date.replace(
            year=month_date.year - 1 if month_date.month <= 6 else month_date.year,
            month=(month_date.month - 6) % 12 + 1,
        )
        month_keys = []
        current = first_month
        for _ in range(6):
            month_keys.append(current.strftime("%Y-%m"))
            current = current.replace(
                year=current.year + (1 if current.month == 12 else 0),
                month=1 if current.month == 12 else current.month + 1,
            )

        trend_rows = connection.execute(
            """
            SELECT substr(data, 1, 7) AS mes,
                COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor_centavos ELSE 0 END), 0)
                    AS receitas,
                COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor_centavos ELSE 0 END), 0)
                    AS despesas
            FROM transacoes
            WHERE substr(data, 1, 7) BETWEEN ? AND ?
            GROUP BY substr(data, 1, 7)
            """,
            (month_keys[0], month_keys[-1]),
        ).fetchall()
        trend_by_month = {row["mes"]: row for row in trend_rows}
        evolution = [
            {
                "mes": key,
                "receitas_centavos": int(trend_by_month[key]["receitas"])
                if key in trend_by_month
                else 0,
                "despesas_centavos": int(trend_by_month[key]["despesas"])
                if key in trend_by_month
                else 0,
            }
            for key in month_keys
        ]

        return {
            "mes": mes,
            "receitas_centavos": int(totals["receitas"]),
            "despesas_centavos": int(totals["despesas"]),
            "saldo_centavos": int(totals["receitas"] - totals["despesas"]),
            "quantidade_transacoes": int(totals["quantidade"]),
            "evolucao": evolution,
            "maiores_despesas": [
                {
                    "categoria": row["categoria"],
                    "total_centavos": int(row["total_centavos"]),
                }
                for row in top_expenses
            ],
        }


def criar_meta(
    nome: str,
    valor_alvo_centavos: int,
    prazo: date | None,
) -> int:
    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO metas (nome, valor_alvo_centavos, prazo)
            VALUES (?, ?, ?)
            """,
            (nome, valor_alvo_centavos, prazo.isoformat() if prazo else None),
        )
        return int(cursor.lastrowid)


def buscar_metas() -> list[dict]:
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT id, nome, valor_alvo_centavos, valor_atual_centavos, prazo, criado_em
            FROM metas
            ORDER BY prazo IS NULL, prazo, id DESC
            """
        ).fetchall()
        return [_transaction_dict(row) for row in rows]


def atualizar_progresso_meta(meta_id: int, valor_atual_centavos: int) -> bool:
    with _connection() as connection:
        cursor = connection.execute(
            "UPDATE metas SET valor_atual_centavos = ? WHERE id = ?",
            (valor_atual_centavos, meta_id),
        )
        return cursor.rowcount > 0


def excluir_meta(meta_id: int) -> bool:
    with _connection() as connection:
        cursor = connection.execute("DELETE FROM metas WHERE id = ?", (meta_id,))
        return cursor.rowcount > 0
