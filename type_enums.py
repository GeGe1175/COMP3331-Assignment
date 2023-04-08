from enum import Enum

class HeaderType (Enum):
    DATA = 0
    ACK = 1
    SYN = 2
    FIN = 3
    RESET = 4