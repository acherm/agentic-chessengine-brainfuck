"""
UCI protocol implementation for BF chess engine.
"""

from bf_memory import TEMP, INPUT_BUF, INPUT_LEN
from bf_io import read_line
from bf_primitives import compare_eq
from bf_chess import parse_position_command, apply_single_move
from bf_movegen import generate_moves, generate_legal_move, output_bestmove


def emit_uci_loop(e):
    """Emit the main UCI loop."""
    running = TEMP + 14
    tmp1 = TEMP + 0
    tmp2 = TEMP + 1
    handled = TEMP + 15

    e.clear(running)
    e.set_cell(running, 1)

    e.move_to(running)
    e.emit('[')

    # Clear input buffer
    for i in range(128):
        e.clear(INPUT_BUF + i)
    e.clear(INPUT_LEN)

    read_line(e)

    e.clear(handled)

    # 'u' (117) = uci
    compare_eq(e, INPUT_BUF, 117, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.print_string("id name BFChess\n")
    e.print_string("id author BFChess\n")
    e.print_string("uciok\n")
    e.set_cell(handled, 1)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # 'i' (105) = isready
    compare_eq(e, INPUT_BUF, 105, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, INPUT_BUF + 1, 115, tmp2, TEMP + 3)
    e.move_to(tmp2)
    e.emit('[')
    e.print_string("readyok\n")
    e.set_cell(handled, 1)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # 'p' (112) = position
    compare_eq(e, INPUT_BUF, 112, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, handled, 0, tmp2, TEMP + 3)
    e.move_to(tmp2)
    e.emit('[')
    parse_position_command(e)
    e.set_cell(handled, 1)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # 'g' (103) = go
    compare_eq(e, INPUT_BUF, 103, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, handled, 0, tmp2, TEMP + 3)
    e.move_to(tmp2)
    e.emit('[')
    generate_legal_move(e)
    output_bestmove(e)
    e.set_cell(handled, 1)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # 'd' (100) = domove
    compare_eq(e, INPUT_BUF, 100, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, INPUT_BUF + 1, 111, tmp2, TEMP + 3)  # 'o' check
    e.move_to(tmp2)
    e.emit('[')
    apply_single_move(e)
    e.set_cell(handled, 1)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # 'q' (113) = quit
    compare_eq(e, INPUT_BUF, 113, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(running)
    e.set_cell(handled, 1)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    e.move_to(running)
    e.emit(']')
