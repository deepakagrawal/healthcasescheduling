from enum import Enum


ROOM_PREFIX = "SiteA - Room"


def room(n) -> str:
    """Generate a room string for a given number, e.g. room(7) -> 'SiteA - Room 7'."""
    return f"{ROOM_PREFIX} {n}"


class Task(str, Enum):
    """Named task/assignment slots used throughout the scheduling model."""
    ROOM_1 = "SiteA - Room 1"
    ROOM_2 = "SiteA - Room 2"
    ROOM_3 = "SiteA - Room 3"
    ROOM_4 = "SiteA - Room 4"
    ROOM_5 = "SiteA - Room 5"
    ROOM_6 = "SiteA - Room 6"
    ROOM_7 = "SiteA - Room 7"
    ROOM_8 = "SiteA - Room 8"
    ROOM_9 = "SiteA - Room 9"
    ROOM_10 = "SiteA - Room 10"
    ROOM_11 = "SiteA - Room 11"
    ROOM_12 = "SiteA - Room 12"
    ROOM_13 = "SiteA - Room 13"
    ROOM_14 = "SiteA - Room 14"
    ROOM_15 = "SiteA - Room 15"
    ROOM_16 = "SiteA - Room 16"
    ROOM_17 = "SiteA - Room 17"
    ROOM_18 = "SiteA - Room 18"
    ROOM_19 = "SiteA - Room 19"
    ROOM_20 = "SiteA - Room 20"
    LEAD = "SiteA - Lead"
    EVE_SHIFT1 = "SiteA - EveShift1 3p"
    EVE_SHIFT2 = "SiteA - EveShift2 12p"
    BACKUP1 = "SiteA - Backup1"
    BACKUP2 = "SiteA - Backup2"
    SPECIALTY2_DAY = "SiteA - Specialty2 Day"
    SITEB_ROOM = "SiteB - Room"


class GridValue(str, Enum):
    """Assignment strings that appear in the input grid CSV."""
    ROOM = "SiteA - Room"
    ROOM8 = "SiteA - Room8"
    NO_CALL = "No Call"
    COORDINATOR = "SiteA - Coordinator"


class DetectionKey(str, Enum):
    """Substrings used for detecting assignment types in grid values."""
    SPECIALTY1 = "Specialty1"
    SPECIALTY2_ONCALL = "Specialty2 OnCall"
    SPECIALTY2_CLINIC = "Specialty2 Clinic"
    SPECIALTY3 = "Specialty3"
    SITEC = "SiteC"


class Column(str, Enum):
    """DataFrame column names used in output."""
    AVG_COST = "Avg. Cost"
    TOTAL_COST = "Total Cost"
    ROOM_DAYS = "SiteA Room days"
    TOTAL_ROOM_COST = "Total SiteA Room Cost"
    AVG_ROOM_COST = "Avg. Room Cost"
    SLOTS_TO_ASSIGN = "SlotsToAssign"


# Commonly used room lists
ROOM_LIST_1_TO_14 = [
    Task.ROOM_1, Task.ROOM_2, Task.ROOM_3, Task.ROOM_4, Task.ROOM_5,
    Task.ROOM_6, Task.ROOM_7, Task.ROOM_8, Task.ROOM_9, Task.ROOM_10,
    Task.ROOM_11, Task.ROOM_12, Task.ROOM_13, Task.ROOM_14,
]

ROOM_LIST_1_TO_6 = [
    Task.ROOM_1, Task.ROOM_2, Task.ROOM_3, Task.ROOM_4, Task.ROOM_5, Task.ROOM_6,
]

ROOM_LIST_1_TO_5 = [
    Task.ROOM_1, Task.ROOM_2, Task.ROOM_3, Task.ROOM_4, Task.ROOM_5,
]

HIGH_COST_TASKS = [
    Task.ROOM_1, Task.ROOM_2, Task.ROOM_3, Task.EVE_SHIFT1, Task.EVE_SHIFT2,
]

PARTTIME_EXCLUDED = [
    Task.ROOM_1, Task.ROOM_2, Task.ROOM_3, Task.ROOM_4, Task.ROOM_5,
    Task.ROOM_10, Task.ROOM_11, Task.ROOM_12,
]
