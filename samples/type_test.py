from typing import Any, Dict, List, Tuple, TypeVar, Union

from django.db import models


# PYI026: Type alias without annotation
Vector = list[float]  # Missing TypeAlias annotation


# ANN001: Missing type function argument
def process_data(data, context=None):
    return data


# ANN201: Missing return type for public function
def get_items():
    return [1, 2, 3]


# UP006: Non-PEP585 annotation
items_list: List[int] = [1, 2, 3]  # Should use list[int]

# UP007: Non-PEP604 annotation union
maybe_string: Union[str, None] = "hello"  # Should use str | None


# RUF013: Implicit Optional
def find_user(user_id: int = None) -> dict:  # Should be Optional[int]
    return {"id": user_id}


# UP037: Quoted annotation
class Config:
    settings: "Dict[str, Any]" = {}  # Unnecessary quotes


# Mixing old and new style annotations
def process_values(
    values: List[int],  # Old style
    context: dict[str, Any],  # New style
) -> Tuple[int, ...]:  # Old style
    return tuple(values)


# Modern type annotation tests
T = TypeVar("T")

# Should be using TypeAlias
UserDict = dict[str, Any]


# Class that mypy would complain about but Ruff won't
class UserManager:
    def get_users(self):
        return [{"name": "user1"}, {"name": "user2"}]

    def create_user(self, name):
        # This would cause a runtime error but neither mypy nor Ruff would catch it
        return name.undefined_method()


# Django-specific case that mypy with django-stubs would check
class TestModel(models.Model):
    name = models.CharField(max_length=100)

    def save(self, *args, **kwargs) -> List[int]:  # Incorrect return type, should be None
        super().save(*args, **kwargs)
        return [1, 2, 3]  # Incorrect return value
