from enum import Enum


class Event(Enum):
    """ Events that happen to light rays as they progress through the simulation.
    """

    GENERATE = 0
    REFLECT = 1
    TRANSMIT = 2
    ABSORB = 3
    SCATTER = 4
    EMIT = 5
    EXIT = 6
    KILL = 7
    REACT = 8
