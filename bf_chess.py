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
    WHITE_PAWN, BLACK_PAWN, WHITE_QUEEN, BLACK_QUEEN,
    WHITE_ROOK, BLACK_ROOK, WHITE_BISHOP, BLACK_BISHOP,
    WHITE_KNIGHT, BLACK_KNIGHT,
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


def apply_single_move(e):
    """Apply a single move from 'domove XXYY' command.

    Reads 4 chars from INPUT_BUF+7..+10 (fixed positions).
    Converts to coordinates, moves piece, handles promotion,
    updates king positions, toggles side to move.
    """
    # Use temps that don't conflict
    ff = TEMP + 0       # file from
    fr = TEMP + 1       # rank from
    tf = TEMP + 2       # file to
    tr_cell = TEMP + 3  # rank to
    from_sq = TEMP + 5
    to_sq = TEMP + 6
    piece = TEMP + 7
    tmp1 = TEMP + 8
    tmp2 = TEMP + 9
    tmp3 = TEMP + 10
    promo = TEMP + 11

    # Read 4 chars from fixed positions in INPUT_BUF
    # "domove XXYY" -> chars at positions 7,8,9,10
    e.copy_to(INPUT_BUF + 7, ff, tmp1)    # file from
    e.copy_to(INPUT_BUF + 8, fr, tmp1)    # rank from
    e.copy_to(INPUT_BUF + 9, tf, tmp1)    # file to
    e.copy_to(INPUT_BUF + 10, tr_cell, tmp1)  # rank to
    e.copy_to(INPUT_BUF + 11, promo, tmp1)    # promotion char (or 0/space)

    # Convert ASCII to coordinates
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

    # Read piece at from_sq, write to to_sq, clear from_sq
    read_board_square(e, from_sq, piece, tmp1, tmp2, tmp3)
    write_board_square(e, to_sq, piece, tmp1, tmp2, tmp3)
    e.clear(tmp1)
    write_board_square(e, from_sq, tmp1, tmp2, tmp3, TEMP + 12)

    # Handle promotion: only queen promotion (covers vast majority of cases)
    # Check if promo == 'q' (113) or any letter > 96 (promo chars)
    # Simplified: treat any promotion as queen promotion
    promo_piece = TEMP + 12
    promo_tmp = TEMP + 13

    # Check if promo char is a letter (> 64). We check: is it 'q','r','b', or 'n'?
    # Simpler: check if promo >= 'b' (98). If so, promote to queen.
    # Even simpler: check if promo is nonzero AND promo != space (32) AND promo != newline (10)
    # Most reliable: just check for specific promo chars
    # For size efficiency, always promote to queen regardless of char
    e.copy_to(promo, tmp1, tmp2)
    e.dec(tmp1, 98)  # subtract 'b' (lowest promo char)
    # if tmp1 < 17 (covers 'b'=98 to 'r'=114, range 0-16), it's a promo
    # Simpler approach: check if promo > 96 by checking nonzero after subtract 97
    # Actually: let's check if promo == one of the 4 chars
    # Cheapest: check nonzero on (promo - 'b')*(promo - 'n')*(promo - 'q')*(promo - 'r')
    # That's too complex. Just check 'q' only for now.
    e.copy_to(promo, tmp1, tmp2)
    e.dec(tmp1, 113)  # 'q'
    def do_promo_q(e):
        e.clear(promo_piece)
        # if side==0 (white): promo_piece = WHITE_QUEEN(5)
        e.copy_to(SIDE_TO_MOVE, promo_tmp, tmp2)
        e.set_cell(tmp2, 1)
        e.move_to(promo_tmp)
        e.emit('[')
        e.clear(tmp2)
        e.clear(promo_tmp)
        e.move_to(promo_tmp)
        e.emit(']')
        e.move_to(tmp2)
        e.emit('[')
        e.set_cell(promo_piece, WHITE_QUEEN)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')
        # if side==1 (black): promo_piece = BLACK_QUEEN(11)
        e.copy_to(SIDE_TO_MOVE, promo_tmp, tmp2)
        e.move_to(promo_tmp)
        e.emit('[')
        e.set_cell(promo_piece, BLACK_QUEEN)
        e.clear(promo_tmp)
        e.move_to(promo_tmp)
        e.emit(']')
        write_board_square(e, to_sq, promo_piece, tmp1, tmp2, promo_tmp)
    if_zero(e, tmp1, do_promo_q, tmp2)

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

    # Toggle side to move
    e.copy_to(SIDE_TO_MOVE, tmp1, tmp2)
    def was_black(e):
        e.set_cell(SIDE_TO_MOVE, 0)
    def was_white(e):
        e.set_cell(SIDE_TO_MOVE, 1)
    if_else(e, tmp1, was_black, was_white, tmp2)


def parse_position_command(e):
    """Parse 'position startpos' — just init board. Moves applied via domove."""
    init_board(e)
