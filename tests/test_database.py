import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test-financas.db"
        self.path_patcher = patch.object(database, "DB_PATH", self.database_path)
        self.path_patcher.start()
        database.init_db()

    def tearDown(self):
        self.path_patcher.stop()
        self.temp_dir.cleanup()

    def test_transactions_are_saved_filtered_and_summarized(self):
        salary_id = database.salvar_transacao(
            "receita", "Salário", 350000, "Salário", date(2026, 3, 5)
        )
        database.salvar_transacao(
            "despesa", "Aluguel", 120000, "Moradia", date(2026, 3, 7)
        )
        database.salvar_transacao(
            "despesa", "Mercado", 25000, "Alimentação", date(2026, 2, 28)
        )

        march_expenses = database.buscar_transacoes(
            mes="2026-03", tipo="despesa"
        )
        self.assertEqual(len(march_expenses), 1)
        self.assertEqual(march_expenses[0]["descricao"], "Aluguel")

        summary = database.buscar_dashboard("2026-03")
        self.assertEqual(summary["receitas_centavos"], 350000)
        self.assertEqual(summary["despesas_centavos"], 120000)
        self.assertEqual(summary["saldo_centavos"], 230000)
        self.assertEqual(summary["quantidade_transacoes"], 2)
        self.assertEqual(len(summary["evolucao"]), 6)
        self.assertEqual(summary["maiores_despesas"][0]["categoria"], "Moradia")

        saved = database.buscar_transacao(salary_id)
        self.assertEqual(saved["data"], "2026-03-05")
        self.assertTrue(
            database.atualizar_transacao(
                salary_id, "receita", "Salário mensal", 360000,
                "Salário", date(2026, 3, 5)
            )
        )
        self.assertEqual(database.buscar_transacao(salary_id)["valor_centavos"], 360000)
        self.assertTrue(database.excluir_transacao(salary_id))
        self.assertIsNone(database.buscar_transacao(salary_id))

    def test_goal_progress_can_be_created_updated_and_deleted(self):
        goal_id = database.criar_meta("Reserva", 100000, date(2026, 12, 31))
        self.assertEqual(database.buscar_metas()[0]["nome"], "Reserva")
        self.assertTrue(database.atualizar_progresso_meta(goal_id, 25000))
        self.assertEqual(database.buscar_metas()[0]["valor_atual_centavos"], 25000)
        self.assertTrue(database.excluir_meta(goal_id))
        self.assertEqual(database.buscar_metas(), [])

    def test_init_migrates_existing_transaction_table_without_losing_rows(self):
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.execute(
                """
                CREATE TABLE transacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    descricao TEXT NOT NULL,
                    valor_centavos INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO transacoes (tipo, descricao, valor_centavos) "
                "VALUES ('receita', 'Registro antigo', 12345)"
            )
            connection.commit()
        finally:
            connection.close()

        with patch.object(database, "DB_PATH", legacy_path):
            database.init_db()
            migrated = database.buscar_transacoes()

        self.assertEqual(len(migrated), 1)
        self.assertEqual(migrated[0]["descricao"], "Registro antigo")
        self.assertEqual(migrated[0]["valor_centavos"], 12345)
        self.assertEqual(migrated[0]["categoria"], "Outros")
        self.assertIsNotNone(migrated[0]["data"])


if __name__ == "__main__":
    unittest.main()
