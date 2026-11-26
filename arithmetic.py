"""Check narrator arithmetic independently of the local model's prose."""
import ast
from fractions import Fraction
import operator


OPERATIONS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def calculate(expression):
    """Accept a bounded numeric expression, never names, calls or exponentiation."""
    if not isinstance(expression, str) or len(expression) > 120:
        raise ValueError("arithmetic expression must be short text")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 40:
        raise ValueError("arithmetic expression is too complex")

    def value(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            exact = Fraction(ast.get_source_segment(expression, node))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            exact = value(node.operand)
            if isinstance(node.op, ast.USub):
                exact = -exact
        elif isinstance(node, ast.BinOp) and type(node.op) in OPERATIONS:
            exact = OPERATIONS[type(node.op)](value(node.left), value(node.right))
        else:
            raise ValueError("only arithmetic with numbers is supported")
        if max(abs(exact.numerator), exact.denominator) > 10**12:
            raise ValueError("arithmetic exceeds the lesson magnitude limit")
        return exact

    return value(tree.body)


def checked_comparisons(entries):
    findings = []
    if not isinstance(entries, list) or len(entries) > 8:
        raise ValueError("too many arithmetic comparisons")
    for comparison in entries:
        a, b = comparison["a"], comparison["b"]
        left, right = calculate(a["expression"]), calculate(b["expression"])
        relation = "<" if left < right else ">" if left > right else "="
        findings.append({"a": a["name"], "a_value": str(left), "b": b["name"], "b_value": str(right),
                         "relation": relation, "unit": comparison["unit"]})
    return findings
