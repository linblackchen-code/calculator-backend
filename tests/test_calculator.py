"""Acceptance tests for arithmetic, error handling, and safe input processing."""

import unittest

from src.calculator import CalculationError, calculate


class CalculatorTests(unittest.TestCase):
    def test_required_operations(self):
        cases = {
            "12+8": "20", "12-8": "4", "12*8": "96", "12/8": "1.5",
            "1+2*3": "7", "(1+2)*3": "9", "10/2+7": "12", "8-3*2": "2",
            "-5+8": "3", "3*-2": "-6", "+5-8": "-3", "-(2+3)*4": "-20",
            "0.1+0.2": "0.3", ".5+2.25": "2.75", "5.": "5", "-0": "0",
            "12 ÷ 8 × 2": "3", "8/2/2": "2", "1--2": "3", "1 - +2": "-1",
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertEqual(calculate(expression)[1], expected)

    def test_recurring_decimal_is_bounded(self):
        self.assertEqual(calculate("1/3")[1], "0." + "3" * 50)

    def test_invalid_input_cannot_execute_code(self):
        invalid = [
            "", " ", "1+", "(1+2", "1+2)", "()", "1 2", "2(3)", "1..2",
            "1/0", "1/(2-2)", "1//2", "2**3", "1e3", "NaN", "Infinity",
            "__import__('os').system('whoami')", "<script>alert(1)</script>",
            "(" * 70 + "1" + ")" * 70, "-" * 70 + "1", "9" * 51, "1" * 1025,
        ]
        for expression in invalid:
            with self.subTest(expression=expression):
                with self.assertRaises(CalculationError):
                    calculate(expression)


if __name__ == "__main__":
    unittest.main()
