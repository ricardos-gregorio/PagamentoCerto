"""Cenários de vencimento mensal, coluna Pago? e atraso diário."""

import unittest
from datetime import date

from pagamento_certo.due_dates import (
    days_until,
    next_due_date,
    reminder_due_and_offset,
    should_send_reminder,
)
from pagamento_certo.parse_table import BillRow


class TestMonthlyReminder(unittest.TestCase):
    def test_vence_dia_20_hoje_19_envia(self):
        """Hoje 19/4, vencimento dia 20 do mês → falta 1 dia → deve lembrar."""
        today = date(2026, 4, 19)
        row = BillRow("Escola", 1.0, "20", "")
        due = next_due_date(today, row)
        self.assertEqual(due, date(2026, 4, 20))
        self.assertEqual(days_until(today, due), 1)
        self.assertTrue(should_send_reminder(today, due))
        ctx = reminder_due_and_offset(today, row)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx[0], date(2026, 4, 20))
        self.assertEqual(ctx[1], 1)

    def test_vence_dia_20_hoje_17_18_envia(self):
        today17 = date(2026, 4, 17)
        today18 = date(2026, 4, 18)
        row = BillRow("X", 1.0, "20", "")
        due17 = next_due_date(today17, row)
        due18 = next_due_date(today18, row)
        self.assertEqual(days_until(today17, due17), 3)
        self.assertEqual(days_until(today18, due18), 2)
        self.assertTrue(should_send_reminder(today17, due17))
        self.assertTrue(should_send_reminder(today18, due18))

    def test_vence_dia_20_hoje_16_nao_envia(self):
        """16/4 → faltam 4 dias para 20/4 → fora da janela."""
        today = date(2026, 4, 16)
        row = BillRow("X", 1.0, "20", "")
        due = next_due_date(today, row)
        self.assertEqual(days_until(today, due), 4)
        self.assertFalse(should_send_reminder(today, due))
        self.assertIsNone(reminder_due_and_offset(today, row))

    def test_vence_dia_20_hoje_20_envia(self):
        """No dia do vencimento (n=0) também enviamos."""
        today = date(2026, 4, 20)
        row = BillRow("X", 1.0, "20", "")
        due = next_due_date(today, row)
        self.assertEqual(days_until(today, due), 0)
        self.assertTrue(should_send_reminder(today, due))
        ctx = reminder_due_and_offset(today, row)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx[1], 0)

    def test_coluna_pago_x_nao_envia(self):
        today = date(2026, 4, 19)
        row = BillRow("Escola", 1.0, "20", "", pago=True)
        self.assertIsNone(reminder_due_and_offset(today, row))

    def test_atraso_apos_vencimento_mesmo_mes(self):
        """25/4 com venc. dia 20 → atraso diário até marcar X."""
        today = date(2026, 4, 25)
        row = BillRow("Conta", 1.0, "20", "")
        ctx = reminder_due_and_offset(today, row)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx[0], date(2026, 4, 20))
        self.assertEqual(ctx[1], -5)

    def test_atraso_mes_anterior_antes_do_proximo_vencimento(self):
        """5/6, venc. dia 20 → ainda cobra maio em atraso antes do venc. de junho."""
        today = date(2026, 6, 5)
        row = BillRow("Conta", 1.0, "20", "")
        ctx = reminder_due_and_offset(today, row)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx[0], date(2026, 5, 20))
        self.assertEqual(ctx[1], -16)

    def test_nao_cobra_marco_no_inicio_de_abril(self):
        """10/4: ainda não entra na janela de abril; não cobra atraso de março."""
        today = date(2026, 4, 10)
        row = BillRow("Conta", 1.0, "20", "")
        self.assertIsNone(reminder_due_and_offset(today, row))


if __name__ == "__main__":
    unittest.main()
