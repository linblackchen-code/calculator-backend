"""A bounded arithmetic parser. User input is never executed as program code."""

import re
from decimal import Decimal, DecimalException, localcontext

MAX_EXPRESSION_LENGTH = 1024
MAX_DEPTH = 64
TOKEN = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)|[()+*/-]")


class CalculationError(ValueError):
    """An expression that cannot safely be calculated."""


class Parser:
    """Grammar: expression -> term -> unary -> number / parenthesized expression."""

    def __init__(self, expression: str):
        self.tokens: list[str] = []
        self.position = 0
        offset = 0
        while offset < len(expression):
            if expression[offset].isspace():
                offset += 1
                continue
            match = TOKEN.match(expression, offset)
            if match is None:
                raise CalculationError(f"第 {offset + 1} 个字符不受支持")
            self.tokens.append(match.group())
            offset = match.end()

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def consume(self) -> str:
        token = self.peek()
        if token is None:
            raise CalculationError("表达式不完整，请检查数字、运算符或括号")
        self.position += 1
        return token

    def expression(self, depth: int = 0) -> Decimal:
        value = self.term(depth)
        while self.peek() in ("+", "-"):
            operator = self.consume()
            right = self.term(depth)
            value = value + right if operator == "+" else value - right
        return value

    def term(self, depth: int) -> Decimal:
        value = self.unary(depth)
        while self.peek() in ("*", "/"):
            operator = self.consume()
            right = self.unary(depth)
            if operator == "/" and right == 0:
                raise CalculationError("除数不能为 0")
            value = value * right if operator == "*" else value / right
        return value

    def unary(self, depth: int) -> Decimal:
        if depth > MAX_DEPTH:
            raise CalculationError("括号或正负号嵌套过深，最多允许 64 层")
        if self.peek() in ("+", "-"):
            operator = self.consume()
            value = self.unary(depth + 1)
            return value if operator == "+" else -value
        if self.peek() == "(":
            self.consume()
            value = self.expression(depth + 1)
            if self.consume() != ")":
                raise CalculationError("括号不匹配")
            return value
        token = self.consume()
        if token in ("+", "-", "*", "/", "(", ")"):
            raise CalculationError("此处应当输入数字，请检查表达式")
        digits = sum(character.isdigit() for character in token)
        if digits > 50:
            raise CalculationError("单个数字最多支持 50 位数字")
        return Decimal(token)


def calculate(expression: str) -> tuple[str, str]:
    """Return the normalized expression and a decimal result as a JSON-safe string."""
    normalized = expression.strip().translate(str.maketrans({"×": "*", "÷": "/", "−": "-"}))
    if not normalized:
        raise CalculationError("请输入计算表达式")
    if len(normalized) > MAX_EXPRESSION_LENGTH:
        raise CalculationError("表达式最多允许 1024 个字符")
    try:
        with localcontext() as context:
            context.prec = 50
            context.Emax = 1000
            context.Emin = -1000
            parser = Parser(normalized)
            value = parser.expression()
            if parser.peek() is not None:
                raise CalculationError("表达式格式错误，请检查相邻数字、运算符和括号")
            if not value.is_finite() or (value != 0 and abs(value.adjusted()) > 1000):
                raise CalculationError("计算结果超出支持范围")
            result = format(value, "f")
            if "." in result:
                result = result.rstrip("0").rstrip(".")
            return normalized, "0" if value == 0 else result
    except DecimalException as error:
        raise CalculationError("计算结果超出支持范围") from error
