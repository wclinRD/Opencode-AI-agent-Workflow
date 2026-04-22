"""
Example Custom Tool: Calculate
A simple calculator tool for performing basic math operations.

This tool demonstrates the custom tool authoring API.
"""

import math


def execute(operation: str, a: float, b: float = 0) -> dict:
    """
    Execute a mathematical operation.

    Args:
        operation: The operation to perform (add, subtract, multiply, divide, sqrt, power, mod)
        a: First number
        b: Second number (not needed for sqrt)

    Returns:
        dict with result and operation details
    """
    operation = operation.lower().strip()

    if operation == "add":
        return {
            "operation": "add",
            "a": a,
            "b": b,
            "result": a + b,
            "formula": f"{a} + {b} = {a + b}",
        }

    elif operation == "subtract":
        return {
            "operation": "subtract",
            "a": a,
            "b": b,
            "result": a - b,
            "formula": f"{a} - {b} = {a - b}",
        }

    elif operation == "multiply":
        return {
            "operation": "multiply",
            "a": a,
            "b": b,
            "result": a * b,
            "formula": f"{a} * {b} = {a * b}",
        }

    elif operation == "divide":
        if b == 0:
            return {
                "operation": "divide",
                "error": "Cannot divide by zero",
            }
        return {
            "operation": "divide",
            "a": a,
            "b": b,
            "result": a / b,
            "formula": f"{a} / {b} = {a / b}",
        }

    elif operation == "sqrt":
        if a < 0:
            return {
                "operation": "sqrt",
                "error": "Cannot take square root of negative number",
            }
        return {
            "operation": "sqrt",
            "a": a,
            "result": math.sqrt(a),
            "formula": f"√{a} = {math.sqrt(a)}",
        }

    elif operation == "power":
        return {
            "operation": "power",
            "a": a,
            "b": b,
            "result": a ** b,
            "formula": f"{a}^{b} = {a ** b}",
        }

    elif operation == "mod":
        if b == 0:
            return {
                "operation": "mod",
                "error": "Cannot mod by zero",
            }
        return {
            "operation": "mod",
            "a": a,
            "b": b,
            "result": a % b,
            "formula": f"{a} % {b} = {a % b}",
        }

    else:
        return {
            "operation": operation,
            "error": f"Unknown operation: {operation}. Supported: add, subtract, multiply, divide, sqrt, power, mod",
        }
