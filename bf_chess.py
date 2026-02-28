"""
Chess board operations for BF engine.
Board at BOARD_START with stride 1 (compact layout).
"""

from bf_memory import (
    BOARD_START, INITIAL_BOARD, SIDE_TO_MOVE,
    WK_CASTLE, WQ_CASTLE, BK_CASTLE, BQ_CASTLE,
    EP_FILE, WHITE_KING_POS, BLACK_KING_POS,
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
    e.set_cell(WK_CASTLE, 1)
    e.set_cell(WQ_CASTLE, 1)
    e.set_cell(BK_CASTLE, 1)
    e.set_cell(BQ_CASTLE, 1)
    e.set_cell(EP_FILE, 0)
    e.set_cell(WHITE_KING_POS, 4)
    e.set_cell(BLACK_KING_POS, 60)


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

    # Read piece at from_sq
    read_board_square(e, from_sq, piece, tmp1, tmp2, tmp3)

    # === EP capture (before we update EP_FILE) ===
    # Detect: piece is pawn, to-file matches EP_FILE, correct rank
    # EP detection below clears captured pawn directly; no flag needed.
    # NOTE: TEMP+4 = GO_FLAG in the UCI loop — must NOT set it here!

    # Check EP_FILE nonzero (early exit)
    e.copy_to(EP_FILE, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')

    # Runtime equality: tf+1 == EP_FILE?
    e.copy_to(tf, tmp2, tmp3)
    e.inc(tmp2)  # tmp2 = tf + 1
    e.copy_to(EP_FILE, tmp3, TEMP + 12)
    # Subtract: tmp2 -= tmp3 (loop decrements both until tmp3==0)
    e.move_to(tmp3)
    e.emit('[')
    e.dec(tmp2)
    e.dec(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    # tmp2 == 0 iff tf+1 == EP_FILE
    e.set_cell(tmp3, 1)
    e.move_to(tmp2)
    e.emit('[')
    e.clear(tmp3)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    # tmp3 = 1 if file matches EP
    e.move_to(tmp3)
    e.emit('[')

    # White EP: piece==WHITE_PAWN AND tr_cell==5
    compare_eq(e, piece, WHITE_PAWN, tmp2, TEMP + 12)
    e.move_to(tmp2)
    e.emit('[')
    compare_eq(e, tr_cell, 5, TEMP + 12, TEMP + 13)
    e.move_to(TEMP + 12)
    e.emit('[')
    # Clear captured pawn at rank 4, file tf: BOARD_START + 32 + tf
    for f in range(8):
        compare_eq(e, tf, f, TEMP + 13, TEMP + 0)
        e.move_to(TEMP + 13)
        e.emit('[')
        e.clear(BOARD_START + 32 + f)
        e.clear(TEMP + 13)
        e.move_to(TEMP + 13)
        e.emit(']')
    e.clear(TEMP + 12)
    e.move_to(TEMP + 12)
    e.emit(']')
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')

    # Black EP: piece==BLACK_PAWN AND tr_cell==2
    compare_eq(e, piece, BLACK_PAWN, tmp2, TEMP + 12)
    e.move_to(tmp2)
    e.emit('[')
    compare_eq(e, tr_cell, 2, TEMP + 12, TEMP + 13)
    e.move_to(TEMP + 12)
    e.emit('[')
    # Clear captured pawn at rank 3, file tf: BOARD_START + 24 + tf
    for f in range(8):
        compare_eq(e, tf, f, TEMP + 13, TEMP + 0)
        e.move_to(TEMP + 13)
        e.emit('[')
        e.clear(BOARD_START + 24 + f)
        e.clear(TEMP + 13)
        e.move_to(TEMP + 13)
        e.emit(']')
    e.clear(TEMP + 12)
    e.move_to(TEMP + 12)
    e.emit(']')
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')

    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')  # end file match

    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')  # end EP_FILE nonzero

    # === Move piece: write to to_sq, clear from_sq ===
    write_board_square(e, to_sq, piece, tmp1, tmp2, tmp3)
    e.clear(tmp1)
    write_board_square(e, from_sq, tmp1, tmp2, tmp3, TEMP + 12)

    # === Update EP_FILE ===
    e.clear(EP_FILE)
    # White double push: piece==WHITE_PAWN AND fr==1 AND tr_cell==3
    compare_eq(e, piece, WHITE_PAWN, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, fr, 1, tmp2, tmp3)
    e.move_to(tmp2)
    e.emit('[')
    compare_eq(e, tr_cell, 3, tmp3, TEMP + 12)
    e.move_to(tmp3)
    e.emit('[')
    e.copy_to(tf, EP_FILE, TEMP + 12)
    e.inc(EP_FILE)  # 1-indexed
    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    # Black double push: piece==BLACK_PAWN AND fr==6 AND tr_cell==4
    compare_eq(e, piece, BLACK_PAWN, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, fr, 6, tmp2, tmp3)
    e.move_to(tmp2)
    e.emit('[')
    compare_eq(e, tr_cell, 4, tmp3, TEMP + 12)
    e.move_to(tmp3)
    e.emit('[')
    e.copy_to(tf, EP_FILE, TEMP + 12)
    e.inc(EP_FILE)
    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # === Update castling rights ===
    # King moves: clear both rights for that side
    compare_eq(e, piece, WHITE_KING, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(WK_CASTLE)
    e.clear(WQ_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, piece, BLACK_KING, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(BK_CASTLE)
    e.clear(BQ_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # Rook leaves starting square
    compare_eq(e, from_sq, 0, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(WQ_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, from_sq, 7, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(WK_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, from_sq, 56, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(BQ_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, from_sq, 63, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(BK_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # Rook captured on starting square
    compare_eq(e, to_sq, 0, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(WQ_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, to_sq, 7, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(WK_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, to_sq, 56, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(BQ_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, to_sq, 63, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(BK_CASTLE)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # === Castling rook move (detect king moving 2 squares) ===
    # White castling
    compare_eq(e, piece, WHITE_KING, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, from_sq, 4, tmp2, tmp3)
    e.move_to(tmp2)
    e.emit('[')
    # Kingside: to_sq==6 -> rook h1(+7) to f1(+5)
    compare_eq(e, to_sq, 6, tmp3, TEMP + 12)
    e.move_to(tmp3)
    e.emit('[')
    e.copy_to(BOARD_START + 7, BOARD_START + 5, TEMP + 12)
    e.clear(BOARD_START + 7)
    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    # Queenside: to_sq==2 -> rook a1(+0) to d1(+3)
    compare_eq(e, to_sq, 2, tmp3, TEMP + 12)
    e.move_to(tmp3)
    e.emit('[')
    e.copy_to(BOARD_START + 0, BOARD_START + 3, TEMP + 12)
    e.clear(BOARD_START + 0)
    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # Black castling
    compare_eq(e, piece, BLACK_KING, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    compare_eq(e, from_sq, 60, tmp2, tmp3)
    e.move_to(tmp2)
    e.emit('[')
    # Kingside: to_sq==62 -> rook h8(+63) to f8(+61)
    compare_eq(e, to_sq, 62, tmp3, TEMP + 12)
    e.move_to(tmp3)
    e.emit('[')
    e.copy_to(BOARD_START + 63, BOARD_START + 61, TEMP + 12)
    e.clear(BOARD_START + 63)
    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    # Queenside: to_sq==58 -> rook a8(+56) to d8(+59)
    compare_eq(e, to_sq, 58, tmp3, TEMP + 12)
    e.move_to(tmp3)
    e.emit('[')
    e.copy_to(BOARD_START + 56, BOARD_START + 59, TEMP + 12)
    e.clear(BOARD_START + 56)
    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    # === Handle promotion (all types: q/r/b/n) ===
    promo_piece = TEMP + 12
    promo_tmp = TEMP + 13

    # For each promotion char, check if promo matches and set promo_piece
    # to the correct piece type (white or black based on SIDE_TO_MOVE).
    # promo_piece starts at 0; each matching compare_eq branch sets it.
    e.clear(promo_piece)

    def _set_promo_piece(e, white_val, black_val):
        """Set promo_piece based on SIDE_TO_MOVE. STM=0 -> white, STM=1 -> black."""
        e.copy_to(SIDE_TO_MOVE, promo_tmp, tmp2)
        e.set_cell(tmp2, 1)
        e.move_to(promo_tmp)
        e.emit('[')  # if STM != 0 (black)
        e.clear(tmp2)
        e.clear(promo_tmp)
        e.move_to(promo_tmp)
        e.emit(']')
        e.move_to(tmp2)
        e.emit('[')  # if STM == 0 (white)
        e.set_cell(promo_piece, white_val)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')
        e.copy_to(SIDE_TO_MOVE, promo_tmp, tmp2)
        e.move_to(promo_tmp)
        e.emit('[')  # if STM != 0 (black)
        e.set_cell(promo_piece, black_val)
        e.clear(promo_tmp)
        e.move_to(promo_tmp)
        e.emit(']')

    # Check 'q' (113)
    compare_eq(e, promo, 113, tmp1, tmp2)
    def do_promo_q(e):
        _set_promo_piece(e, WHITE_QUEEN, BLACK_QUEEN)
    if_nonzero(e, tmp1, do_promo_q)

    # Check 'r' (114)
    compare_eq(e, promo, 114, tmp1, tmp2)
    def do_promo_r(e):
        _set_promo_piece(e, WHITE_ROOK, BLACK_ROOK)
    if_nonzero(e, tmp1, do_promo_r)

    # Check 'b' (98)
    compare_eq(e, promo, 98, tmp1, tmp2)
    def do_promo_b(e):
        _set_promo_piece(e, WHITE_BISHOP, BLACK_BISHOP)
    if_nonzero(e, tmp1, do_promo_b)

    # Check 'n' (110)
    compare_eq(e, promo, 110, tmp1, tmp2)
    def do_promo_n(e):
        _set_promo_piece(e, WHITE_KNIGHT, BLACK_KNIGHT)
    if_nonzero(e, tmp1, do_promo_n)

    # Write promoted piece to board if promo_piece is nonzero
    def do_write_promo(e):
        write_board_square(e, to_sq, promo_piece, tmp1, tmp2, promo_tmp)
    if_nonzero(e, promo_piece, do_write_promo)

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
