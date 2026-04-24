from enum import Enum, auto


class TriggerOutcome(Enum):
    SUCCEEDED = auto()
    ACTION_FAILED = auto()
    SKIPPED_FOR_INSTANCE = auto()
    SKIPPED_FOR_QUERYSET = auto()
