"""
UCI protocol implementation for BF chess engine.
"""

from bf_memory import TEMP, INPUT_BUF, INPUT_LEN, PERFT_MODE, PERFT_COUNT, BETA_CUTOFF, D2_ALPHA
from bf_io import read_line
from bf_primitives import compare_eq
from bf_chess import parse_position_command, apply_single_move
from bf_movegen import generate_moves, generate_legal_move, generate_legal_move_depth2, generate_legal_move_depth3, output_bestmove, output_decimal

# GO_FLAG: set by 'go' or 'perft' commands, triggers shared movegen+output block.
# TEMP+4 is safe: not used by apply_single_move, and generate_legal_move
# (which reuses cell 4 as FOUND_LEGAL) only runs after GO_FLAG is consumed.
GO_FLAG = TEMP + 4


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
    e.clear(GO_FLAG)

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

    # 'p' (112) = position or perft
    compare_eq(e, INPUT_BUF, 112, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, handled, 0, tmp2, TEMP + 3)
    e.move_to(tmp2)
    e.emit('[')

    # Disambiguate: 'o' (111) = position, 'e' (101) = perft
    compare_eq(e, INPUT_BUF + 1, 111, TEMP + 3, TEMP + 4)  # check 'o'
    e.move_to(TEMP + 3)
    e.emit('[')
    parse_position_command(e)
    e.set_cell(handled, 1)
    e.clear(TEMP + 3)
    e.move_to(TEMP + 3)
    e.emit(']')

    compare_eq(e, INPUT_BUF + 1, 101, TEMP + 3, TEMP + 4)  # check 'e'
    e.move_to(TEMP + 3)
    e.emit('[')
    # --- Perft: set mode flag + trigger shared go block ---
    e.set_cell(PERFT_MODE, 1)
    e.clear(PERFT_COUNT)
    e.set_cell(GO_FLAG, 1)
    e.set_cell(handled, 1)
    e.clear(TEMP + 3)
    e.move_to(TEMP + 3)
    e.emit(']')

    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # 'g' (103) = go: just set GO_FLAG
    compare_eq(e, INPUT_BUF, 103, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, handled, 0, tmp2, TEMP + 3)
    e.move_to(tmp2)
    e.emit('[')
    e.set_cell(GO_FLAG, 1)
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

    # === Shared GO logic: if GO_FLAG, run search + output ===
    e.copy_to(GO_FLAG, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(GO_FLAG)

    # Dispatch: perft uses depth-1, normal go uses depth-2
    e.copy_to(PERFT_MODE, tmp2, TEMP + 3)
    e.set_cell(TEMP + 3, 1)  # else flag
    e.move_to(tmp2)
    e.emit('[')
    # --- Perft: depth-1 search (enumerate all legal moves) ---
    generate_legal_move(e)
    e.print_string("Nodes: ")
    output_decimal(e, PERFT_COUNT)
    e.print_char(10)
    e.clear(PERFT_MODE)
    e.clear(TEMP + 3)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.move_to(TEMP + 3)
    e.emit('[')
    # --- Normal go: depth-3 minimax search ---
    e.set_cell(BETA_CUTOFF, 255)  # no cutoff at top-level inner search
    e.clear(D2_ALPHA)              # no cutoff at top-level depth-2
    generate_legal_move_depth3(e)
    output_bestmove(e)
    e.clear(TEMP + 3)
    e.move_to(TEMP + 3)
    e.emit(']')

    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    e.move_to(running)
    e.emit(']')
