from typing import Any, Dict, List, Optional, Tuple, Union


# UP006: Non-PEP585 annotation (fixable)
items_list: List[int] = [1, 2, 3]  # Should use list[int]
items_tuple: Tuple[str, ...] = ("a", "b", "c")  # Should use tuple[str, ...]
items_dict: Dict[str, Any] = {"key": "value"}  # Should use dict[str, Any]

# UP007: Non-PEP604 annotation union (fixable)
maybe_string: Union[str, None] = "hello"  # Should use str | None
mixed_type: Union[int, str] = "text"  # Should use int | str
multi_union: Union[int, str, bool] = True  # Should use int | str | bool


# UP037: Quoted annotation (fixable)
class Config:
    settings: "Dict[str, Any]" = {}  # Should remove quotes


# RUF013: Implicit Optional (fixable)
def find_user(user_id: int = None) -> dict:  # Should be Optional[int]
    return {"id": user_id}


# UP006 + UP007 combination (fixable)
complex_type: Optional[List[Dict[str, Union[int, str]]]] = None
# Should be: complex_type: list[dict[str, int | str]] | None = None

# Type alias without TypeAlias (potentially fixable)
Vector = list[float]  # Should have TypeAlias annotation


# Unnecessary wrapped Optional (fixable)
def process_input(data: Optional[Union[str, None]] = None) -> Optional[str]:
    # Optional[Union[str, None]] is redundant, should just be Optional[str]
    return data


# Function missing a param type (fixable by adding annotation)
def format_string(text, prefix: str = "") -> str:
    return f"{prefix}{text}"
