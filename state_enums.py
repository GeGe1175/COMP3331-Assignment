from enum import Enum

class State (Enum):
    CLOSED = 'CLOSED'
    LISTEN = 'LISTEN'
    ESTABLISHED = 'ESTABLISHED'
    TIME_WAIT = 'TIME_WAIT'
    SYN_SENT = 'SYN_SENT'
    FIN_WAIT = 'FIN_WAIT'
    CLOSING = 'CLOSING'
