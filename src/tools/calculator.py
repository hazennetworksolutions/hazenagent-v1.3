"""Mathematical calculation tools."""
import math
from typing import Union, List
import re

from src.utils.logger import logger


async def calculate(expression: str) -> str:
    """Calculate mathematical expression safely.
    
    Args:
        expression: Mathematical expression (e.g., "2 + 2", "sqrt(16)", "10 * 5")
        
    Returns:
        Calculation result
    """
    try:
        # Sanitize expression - only allow safe characters
        safe_chars = r'[0-9+\-*/().\s,sqrtpowlogsincoatan]+'
        if not re.match(safe_chars, expression.replace(' ', '')):
            return "Error: Invalid characters in expression"
        
        # Replace common functions
        expression = expression.replace('sqrt', 'math.sqrt')
        expression = expression.replace('pow', 'math.pow')
        expression = expression.replace('log', 'math.log')
        expression = expression.replace('sin', 'math.sin')
        expression = expression.replace('cos', 'math.cos')
        expression = expression.replace('tan', 'math.tan')
        expression = expression.replace('pi', str(math.pi))
        expression = expression.replace('e', str(math.e))
        
        # Evaluate safely
        result = eval(expression, {"__builtins__": {}, "math": math})
        
        # Format result
        if isinstance(result, float):
            if result.is_integer():
                return str(int(result))
            return f"{result:.10f}".rstrip('0').rstrip('.')
        
        return str(result)
    except Exception as e:
        logger.error(f"Error calculating expression: {e}")
        return f"Error: {str(e)}"


async def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Convert between units.
    
    Args:
        value: Value to convert
        from_unit: Source unit
        to_unit: Target unit
        
    Returns:
        Conversion result
    """
    conversions = {
        # Length
        ("m", "km"): 0.001,
        ("km", "m"): 1000,
        ("m", "cm"): 100,
        ("cm", "m"): 0.01,
        ("m", "ft"): 3.28084,
        ("ft", "m"): 0.3048,
        ("m", "mi"): 0.000621371,
        ("mi", "m"): 1609.34,
        
        # Weight
        ("kg", "g"): 1000,
        ("g", "kg"): 0.001,
        ("kg", "lb"): 2.20462,
        ("lb", "kg"): 0.453592,
        ("kg", "oz"): 35.274,
        ("oz", "kg"): 0.0283495,
        
        # Temperature
        ("c", "f"): lambda x: (x * 9/5) + 32,
        ("f", "c"): lambda x: (x - 32) * 5/9,
        ("c", "k"): lambda x: x + 273.15,
        ("k", "c"): lambda x: x - 273.15,
    }
    
    try:
        from_unit = from_unit.lower()
        to_unit = to_unit.lower()
        
        key = (from_unit, to_unit)
        if key in conversions:
            conversion = conversions[key]
            if callable(conversion):
                result = conversion(value)
            else:
                result = value * conversion
            
            return f"{value} {from_unit} = {result:.2f} {to_unit}"
        else:
            return f"Conversion from {from_unit} to {to_unit} not supported"
    except Exception as e:
        logger.error(f"Error converting units: {e}")
        return f"Error: {str(e)}"


async def solve_equation(equation: str) -> str:
    """Solve simple linear equations.
    
    Args:
        equation: Equation string (e.g., "2x + 5 = 15")
        
    Returns:
        Solution
    """
    try:
        # Simple linear equation solver
        # Format: ax + b = c
        equation = equation.replace(" ", "").lower()
        
        if "x" not in equation:
            return "Error: Equation must contain 'x'"
        
        # Split by =
        if "=" not in equation:
            return "Error: Invalid equation format"
        
        left, right = equation.split("=")
        
        # Try to solve
        # This is a simplified solver - for production, use a proper library
        return "Error: Complex equation solving not yet implemented. Use calculate() for simple math."
    except Exception as e:
        logger.error(f"Error solving equation: {e}")
        return f"Error: {str(e)}"

