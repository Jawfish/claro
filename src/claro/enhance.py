"""Runtime assertion error enhancement via frame introspection."""

import ast
import linecache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

# Operator name mapping
_OP_NAMES: dict[type, str] = {
    ast.Eq: "to equal",
    ast.NotEq: "to not equal",
    ast.Lt: "to be less than",
    ast.Gt: "to be greater than",
    ast.LtE: "to be at most",
    ast.GtE: "to be at least",
    ast.In: "to be in",
    ast.NotIn: "to not be in",
    ast.Is: "to be",
    ast.IsNot: "to not be",
}


def enhance_assertion_error(
    exc: AssertionError,
    tb: TracebackType | None = None,
) -> tuple[str | None, object, object]:
    """
    Extract source line and locals to build a better error message.

    Returns:
        (message, expected, actual) tuple. Values are None/MISSING if
        enhancement failed.
    """
    from .types import MISSING

    if tb is None:
        tb = exc.__traceback__

    if tb is None:
        return None, MISSING, MISSING

    # Walk to the innermost frame (where assert failed)
    while tb.tb_next:
        tb = tb.tb_next

    frame = tb.tb_frame
    lineno = tb.tb_lineno
    filename = frame.f_code.co_filename

    # Get source line
    source_line = linecache.getline(filename, lineno).strip()

    if not source_line.startswith("assert "):
        return None, MISSING, MISSING

    # Parse the assert expression
    # Remove 'assert ' prefix and any trailing message after comma
    expr = source_line[7:]
    # Handle 'assert x == y, "message"' - find the comparison part
    # This is tricky because the expression itself might contain commas
    # We'll try parsing progressively shorter strings
    for i in range(len(expr), 0, -1):
        try:
            tree = ast.parse(expr[:i], mode="eval")
            expr = expr[:i]
            break
        except SyntaxError:
            continue
    else:
        return None, MISSING, MISSING

    node = tree.body

    # Handle comparisons: 'a == b', 'a != b', 'a in b', etc.
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return None, MISSING, MISSING

    try:
        local_vars = frame.f_locals
        global_vars = frame.f_globals

        # Evaluate left and right in the frame's context
        left_code = compile(ast.Expression(node.left), "<expr>", "eval")
        right_code = compile(ast.Expression(node.comparators[0]), "<expr>", "eval")

        left_val = eval(left_code, global_vars, local_vars)  # noqa: S307
        right_val = eval(right_code, global_vars, local_vars)  # noqa: S307

        op = node.ops[0]
        op_name = _OP_NAMES.get(type(op), type(op).__name__)

        # For 'in' operator, swap expected/actual for clearer message
        if isinstance(op, (ast.In, ast.NotIn)):
            msg = f"Expected {left_val!r} {op_name} {right_val!r}"
            return msg, right_val, left_val
        else:
            msg = f"Expected {left_val!r} {op_name} {right_val!r}"
            return msg, right_val, left_val

    except Exception:
        return None, MISSING, MISSING
