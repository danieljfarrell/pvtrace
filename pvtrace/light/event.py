from enum import Enum


class Event(Enum):
    """Events that happen to light rays as they progress through the simulation."""

    GENERATE = 0
    REFLECT = 1
    TRANSMIT = 2
    ABSORB = 3
    NONRADIATIVE = 4
    SCATTER = 5
    EMIT = 6
    EXIT = 7
    REACT = 8
    KILL = 9
