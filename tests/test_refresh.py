import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('update', Path(__file__).resolve().parents[1] / 'scripts/update_employment_dynamics.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
class RefreshTests(unittest.TestCase):
    def test_calendar_lags(self):
        self.assertEqual(u.prior_date('2026-01-01', 1), '2025-12-01')
        self.assertEqual(u.prior_date('2026-01-01', 12), '2025-01-01')
    def test_missing_state_observation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(u, 'OUT_DIR', Path(folder)):
            u.write_state_data({'Alabama': {'2026-01-01':100}}, {'Total nonfarm': {'2026-01-01':200, '2026-02-01':201}})
            text=(Path(folder)/'state_employment.csv').read_text()
            self.assertIn('2026-02-01,Alabama,AL,,,,,,',text)
    def test_missing_values_have_no_growth(self):
        self.assertIsNone(u.pct_change(None, 100))
        self.assertIsNone(u.pct_change(100, None))
if __name__ == '__main__': unittest.main()
