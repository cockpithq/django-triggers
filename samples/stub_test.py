from datetime import datetime
from typing import Any, Dict, List, TypeVar


# Function with incompatible return types
# mypy would catch this, but Ruff likely won't
def get_name() -> str:
    if "condition":
        return 123  # Type error: returning int when str is expected
    return "name"


# Type compatibility issues
def process_data(data: List[int]) -> Dict[str, int]:
    result = {}
    for item in data:
        result[item] = "value"  # Type error: assigning str to Dict[str, int]
    return result


# Complex type inference
def complex_operation(data: Dict[str, Any]) -> List[str]:
    if "key" in data:
        result = data["key"] * 2  # Could be type error depending on what data["key"] is
        return result  # If result isn't a List[str], mypy would catch this
    return ["default"]


# Runtime errors that mypy would catch but ruff won't
class User:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age


def print_user_details(user: User) -> None:
    # mypy would catch this undefined attribute, but Ruff wouldn't
    print(f"Email: {user.email}")  # Runtime error: 'User' has no attribute 'email'


# Function calling issues - mypy would detect mismatch in argument types
def format_date(date: datetime) -> str:
    return date.strftime("%Y-%m-%d")


def display_date() -> None:
    # mypy would complain about passing a string where datetime is expected
    date_str = "2023-05-20"
    print(format_date(date_str))  # Type error: date_str is str, not datetime


# Return value usage - mypy checks how return values are used
def get_user_ids() -> List[int]:
    return [1, 2, 3]


def process_user_ids() -> None:
    ids = get_user_ids()
    for id in ids:
        # mypy would check that operations on 'id' are valid for int
        # but Ruff wouldn't catch this issue
        print(id.lower())  # Runtime error: int has no lower() method


# Incorrect generic usage
T = TypeVar("T")


def first_item(items: List[T]) -> T:
    if items:
        return items[0]
    return None  # Type error: None is not of type T


# Django model-level type checking that mypy with django-stubs would detect
# but Ruff would not catch
from django.db import models


class Article(models.Model):
    title = models.CharField(max_length=100)

    def get_absolute_url(self) -> str:
        # mypy with django-stubs would catch this error
        # self.pk could be None, which would cause a runtime error
        return f"/article/{self.pk}/"
