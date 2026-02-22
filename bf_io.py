"""
I/O operations for BF chess engine.

read_line: Read characters until newline into INPUT_BUF, set INPUT_LEN.
Work cells at MG area (94-99) for proximity to INPUT_BUF (100+).
"""

from bf_memory import INPUT_BUF, INPUT_LEN, MG_T1, MG_T2, MG_T3, MG_T4, MG_T5, MG_T6
from bf_primitives import compare_eq


def read_line(e):
    """
    Read a line from stdin into INPUT_BUF.
    Stops at newline (10) or EOF (0). Sets INPUT_LEN.
    """
    # Work cells near INPUT_BUF for minimal pointer travel
    idx = MG_T1       # 94
    cont = MG_T2      # 95
    char_cell = MG_T3 # 96
    tmp1 = MG_T4      # 97
    tmp2 = MG_T5      # 98
    tmp3 = MG_T6      # 99

    e.clear(idx)
    e.set_cell(cont, 1)

    e.move_to(cont)
    e.emit('[')

    # Read a character
    e.clear(char_cell)
    e.input(char_cell)

    # Check if it's 0 (EOF) -> stop
    e.copy_to(char_cell, tmp1, tmp2)
    e.set_cell(tmp2, 1)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.move_to(tmp2)
    e.emit('[')
    e.clear(cont)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')

    # Check if it's 10 (newline) -> stop
    e.copy_to(char_cell, tmp1, tmp2)
    e.dec(tmp1, 10)
    e.set_cell(tmp2, 1)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.move_to(tmp2)
    e.emit('[')
    e.clear(cont)
    e.clear(char_cell)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')

    # If cont still set, store char in buffer at idx position
    e.copy_to(char_cell, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')

    for i in range(128):
        compare_eq(e, idx, i, tmp2, tmp3)
        e.move_to(tmp2)
        e.emit('[')
        e.copy_to(char_cell, INPUT_BUF + i, tmp3)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')

    e.inc(idx)

    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    e.move_to(cont)
    e.emit(']')

    # Copy final idx to INPUT_LEN
    e.copy_to(idx, INPUT_LEN, tmp1)


def print_newline(e):
    """Print a newline character."""
    e.print_char(10)


def print_space(e):
    """Print a space character."""
    e.print_char(32)


def print_buf_char(e, cell):
    """Print the character at the given cell."""
    e.output(cell)
