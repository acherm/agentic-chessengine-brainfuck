"""
Chess board operations for BF engine.
Board at BOARD_START with stride 1 (compact layout).
"""

from bf_memory import (
    BOARD_START, INITIAL_BOARD, SIDE_TO_MOVE, CASTLING,
    EP_FILE, WHITE_KING_POS, BLACK_KING_POS, HALFMOVE, FULLMOVE,
    TEMP, INPUT_BUF, INPUT_LEN,
    MG_T1, MG_T2, MG_T3, MG_T4, MG_T5, MG_T6,
    EMPTY, WHITE_KING, BLACK_KING,
)
from bf_primitives import compare_eq, if_nonzero, if_zero, if_else


def init_board(e):
    """Set up the board to the starting position."""
    for i, piece in enumerate(INITIAL_BOARD):
        e.set_cell(BOARD_START + i, piece)
    e.set_cell(SIDE_TO_MOVE, 0)
    e.set_cell(CASTLING, 15)
    e.set_cell(EP_FILE, 0)
    e.set_cell(WHITE_KING_POS, 4)
    e.set_cell(BLACK_KING_POS, 60)
    e.set_cell(HALFMOVE, 0)
    e.set_cell(FULLMOVE, 1)


def read_board_square(e, sq_index_cell, result_cell, tmp1, tmp2, tmp3):
    """Read board at dynamic square index into result_cell. 64-way switch."""
    e.clear(result_cell)
    for i in range(64):
        compare_eq(e, sq_index_cell, i, tmp1, tmp2)
        e.move_to(tmp1)
        e.emit('[')
        e.copy_to(BOARD_START + i, result_cell, tmp2)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')


def write_board_square(e, sq_index_cell, value_cell, tmp1, tmp2, tmp3):
    """Write value_cell to board at dynamic square index. 64-way switch."""
    for i in range(64):
        compare_eq(e, sq_index_cell, i, tmp1, tmp2)
        e.move_to(tmp1)
        e.emit('[')
        e.copy_to(value_cell, BOARD_START + i, tmp2)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')


def parse_and_apply_moves(e):
    """Parse move list from INPUT_BUF and apply each move.

    Key optimization: batch-read 5 chars per move in ONE 128-way pass
    instead of 5-6 separate passes. Result cells near INPUT_BUF (94-99)
    to minimize pointer travel.
    """
    pos = TEMP + 0       # 0 - position in buffer
    cont = TEMP + 1      # 1 - continue flag
    skip = TEMP + 2      # 2 - skip flag (set when space encountered)
    from_sq = TEMP + 5   # 5
    to_sq = TEMP + 6     # 6
    piece = TEMP + 7     # 7
    tmp1 = TEMP + 8      # 8
    tmp2 = TEMP + 9      # 9
    tmp3 = TEMP + 10     # 10

    # Batch read results near INPUT_BUF for cheap copies
    ff = MG_T3           # 96
    fr = MG_T4           # 97
    tf = MG_T5           # 98
    tr_cell = MG_T6      # 99
    promo = MG_T1        # 94
    batch_tmp = MG_T2    # 95 - tmp for copy_to inside batch

    e.set_cell(cont, 1)
    e.move_to(cont)
    e.emit('[')

    # Batch read: read 5 chars from buf[pos..pos+4] in ONE pass
    e.clear(ff)
    e.clear(fr)
    e.clear(tf)
    e.clear(tr_cell)
    e.clear(promo)
    for i in range(128):
        compare_eq(e, pos, i, tmp1, tmp2)
        e.move_to(tmp1)
        e.emit('[')
        e.copy_to(INPUT_BUF + i, ff, batch_tmp)
        e.copy_to(INPUT_BUF + i + 1, fr, batch_tmp)
        e.copy_to(INPUT_BUF + i + 2, tf, batch_tmp)
        e.copy_to(INPUT_BUF + i + 3, tr_cell, batch_tmp)
        e.copy_to(INPUT_BUF + i + 4, promo, batch_tmp)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')

    # Check if ff == 0 (end of input) -> stop
    e.copy_to(ff, tmp1, tmp2)
    def stop_if_zero(e):
        e.clear(cont)
    if_zero(e, tmp1, stop_if_zero, tmp2)

    # Check if ff == space (32) -> skip, advance pos
    e.clear(skip)
    e.copy_to(ff, tmp1, tmp2)
    e.dec(tmp1, 32)
    def handle_space(e):
        e.inc(pos)
        e.set_cell(skip, 1)
    if_zero(e, tmp1, handle_space, tmp2)

    # Process move if cont still set AND skip==0
    e.copy_to(cont, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, skip, 0, tmp2, tmp3)
    e.move_to(tmp2)
    e.emit('[')

    # Convert chars to coordinates
    e.dec(ff, 97)       # ff -= 'a'
    e.dec(fr, 49)       # fr -= '1'
    e.dec(tf, 97)       # tf -= 'a'
    e.dec(tr_cell, 49)  # tr -= '1'

    # from_sq = fr * 8 + ff
    e.clear(from_sq)
    e.copy_to(fr, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.inc(from_sq, 8)
    e.dec(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.copy_to(ff, tmp1, tmp2)
    e.add_to(tmp1, from_sq)

    # to_sq = tr * 8 + tf
    e.clear(to_sq)
    e.copy_to(tr_cell, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.inc(to_sq, 8)
    e.dec(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.copy_to(tf, tmp1, tmp2)
    e.add_to(tmp1, to_sq)

    read_board_square(e, from_sq, piece, tmp1, tmp2, tmp3)
    write_board_square(e, to_sq, piece, tmp1, tmp2, tmp3)
    e.clear(tmp1)
    write_board_square(e, from_sq, tmp1, tmp2, tmp3, TEMP + 12)

    # Update king positions
    compare_eq(e, piece, WHITE_KING, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.copy_to(to_sq, WHITE_KING_POS, tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, piece, BLACK_KING, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.copy_to(to_sq, BLACK_KING_POS, tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # Toggle side: if was 1 (black) -> set 0, if was 0 (white) -> set 1
    e.copy_to(SIDE_TO_MOVE, tmp1, tmp2)
    def was_black(e):
        e.set_cell(SIDE_TO_MOVE, 0)
    def was_white(e):
        e.set_cell(SIDE_TO_MOVE, 1)
    if_else(e, tmp1, was_black, was_white, tmp2)

    e.inc(pos, 4)

    # Check promotion: if promo char is a letter (not space/null), skip it
    # 'q'=113, 'r'=114, 'b'=98, 'n'=110 — all > 96
    # Space=32, null=0. Check if promo > 96 (is a promo char)
    # Simpler: check if promo == 'q' (113) — most common
    # Actually check several promo chars
    e.copy_to(promo, tmp1, tmp2)
    e.dec(tmp1, 113)  # 'q'
    def skip_promo_q(e):
        e.inc(pos)
    if_zero(e, tmp1, skip_promo_q, tmp2)

    e.copy_to(promo, tmp1, tmp2)
    e.dec(tmp1, 114)  # 'r'
    def skip_promo_r(e):
        e.inc(pos)
    if_zero(e, tmp1, skip_promo_r, tmp2)

    e.copy_to(promo, tmp1, tmp2)
    e.dec(tmp1, 98)   # 'b'
    def skip_promo_b(e):
        e.inc(pos)
    if_zero(e, tmp1, skip_promo_b, tmp2)

    e.copy_to(promo, tmp1, tmp2)
    e.dec(tmp1, 110)  # 'n'
    def skip_promo_n(e):
        e.inc(pos)
    if_zero(e, tmp1, skip_promo_n, tmp2)

    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')  # end skip==0 check

    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')  # end cont check

    e.move_to(cont)
    e.emit(']')  # end main loop


def parse_position_command(e):
    """Parse 'position startpos' or 'position startpos moves ...'"""
    tmp1 = TEMP + 5
    tmp2 = TEMP + 6
    init_board(e)
    e.copy_to(INPUT_BUF + 18, tmp1, tmp2)
    e.dec(tmp1, 109)
    def apply_moves(e):
        e.set_cell(TEMP + 0, 24)  # pos starts at char 24
        parse_and_apply_moves(e)
    if_zero(e, tmp1, apply_moves, tmp2)
