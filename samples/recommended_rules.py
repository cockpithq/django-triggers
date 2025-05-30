# Recommended Ruff Type Checking Rules for Django Projects
# Based on testing and research

"""
This file documents recommended Ruff rules for type checking in Django projects.
These rules can be added to the pyproject.toml configuration to enable type-related
linting that complements mypy's comprehensive type checking.
"""

# Recommended configuration for pyproject.toml:

"""
[tool.ruff.lint]
select = [
    # ... existing rules ...
    
    # Type annotation rules
    "ANN",     # flake8-annotations for detecting missing type annotations
    "UP006",   # Use Python 3.9+ style annotations (PEP 585)
    "UP007",   # Use Python 3.10+ style union annotations (PEP 604)
    "UP037",   # Remove unnecessary quotes from type annotations
    "RUF013",  # Detect implicit Optional from default=None
]

# Optionally, add settings for these rules:
[tool.ruff.lint.pep8-naming]
# Configuration options for type checking rules

[tool.ruff.lint.flake8-annotations]
# Allow dynamically typed expressions (typing.Any) in function signatures
allow-any = true
# Ignore arguments with type Any
ignore-any = true
"""

# Rule Descriptions:

# ANN - Missing Type Annotations:
# ANN001-ANN003: Ensure function arguments have type annotations
# ANN201-ANN206: Ensure functions have return type annotations

# UP - Modern Type Annotation Syntax:
# UP006: Use modern Python 3.9+ style type annotations (e.g., list[int] vs List[int])
# UP007: Use Python 3.10+ style type unions (e.g., int | str vs Union[int, str])
# UP037: Remove unnecessary quotes from type annotations

# RUF - Ruff-specific Type Checks:
# RUF013: Detects implicit Optional types (e.g., param: int = None should be param: Optional[int] = None)

# Notes:
# - These rules complement mypy rather than replace it
# - Mypy should still be used for full type checking
# - ANN rules help ensure code has proper annotations for mypy to check
# - These rules primarily focus on syntax and style, not deep type checking
