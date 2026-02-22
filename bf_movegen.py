"""
Move generation — runtime loop with runtime offset loops.

Key optimizations:
1. Runtime 64-iteration outer loop (1 loop body for all squares)
2. Runtime offset loops for knight (8), king (8), sliding (8 dirs)
3. Workspace cells at 100-119 (close to MG area 94-99 and board end 93)
"""

from bf_memory import (
    BOARD_START, SIDE_TO_MOVE, TEMP,
    BEST_FROM, BEST_TO, HAVE_LEGAL, MOVE_PROMO,
    MG_PIECE, MG_T1, MG_T2, MG_T3, MG_T4, MG_T5, MG_T6,
    WHITE_PAWN, WHITE_KNIGHT, WHITE_BISHOP, WHITE_ROOK, WHITE_QUEEN, WHITE_KING,
    BLACK_PAWN, BLACK_KNIGHT, BLACK_BISHOP, BLACK_ROOK, BLACK_QUEEN, BLACK_KING,
    EMPTY,
)
from bf_primitives import compare_eq

# ---- Movegen workspace (overlaps INPUT_BUF, safe during movegen) ----
SQ = 100
RANK = 101
FILE = 102
COUNTER = 103
IS_WHITE = 104
TARGET_SQ = 105
TR = 106
TF = 107
VALID = 108
NOT_FRIENDLY = 109
OFF_IDX = 110
OFF_COUNTER = 111
DR_CELL = 112
DF_CELL = 113
INNER_CONT = 114
DIST_COUNTER = 115
TPIECE = 116
MINE = 117
IS_BLACK = 118
HANDLED = 119


def _fast_read_board(e, sq_cell, result_cell):
    """Read board[sq_cell] into result_cell. 64-way switch."""
    work = MG_T1
    backup = MG_T2
    flag = MG_T3

    e.clear(result_cell)
    e.copy_to(sq_cell, work, backup)

    for i in range(64):
        if i > 0:
            e.dec(work, 1)
        e.clear(backup)
        e.clear(flag)
        e.move_to(work)
        e.emit('[')
        e.inc(backup)
        e.inc(flag)
        e.dec(work)
        e.move_to(work)
        e.emit(']')
        e.set_cell(work, 1)
        e.move_to(backup)
        e.emit('[')
        e.clear(work)
        e.clear(backup)
        e.move_to(backup)
        e.emit(']')
        e.move_to(work)
        e.emit('[')
        e.copy_to(BOARD_START + i, result_cell, backup)
        e.clear(work)
        e.move_to(work)
        e.emit(']')
        e.move_cell(flag, work)


def _try_store(e):
    """If HAVE_LEGAL==0, store SQ->BEST_FROM, TARGET_SQ->BEST_TO."""
    compare_eq(e, HAVE_LEGAL, 0, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    e.copy_to(SQ, BEST_FROM, MG_T2)
    e.copy_to(TARGET_SQ, BEST_TO, MG_T2)
    e.set_cell(HAVE_LEGAL, 1)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')


def _check_not_friendly(e):
    """Set NOT_FRIENDLY=1 if TPIECE is empty or enemy (based on IS_WHITE)."""
    e.set_cell(NOT_FRIENDLY, 1)

    # White friendly check
    e.copy_to(IS_WHITE, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    for fv in range(1, 7):
        compare_eq(e, TPIECE, fv, MG_T5, MG_T6)
        e.move_to(MG_T5)
        e.emit('[')
        e.clear(NOT_FRIENDLY)
        e.clear(MG_T5)
        e.move_to(MG_T5)
        e.emit(']')
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')

    # Black friendly check
    e.copy_to(IS_WHITE, MG_T4, MG_T5)
    e.set_cell(MG_T5, 1)
    e.move_to(MG_T4)
    e.emit('[')
    e.clear(MG_T5)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    e.move_to(MG_T5)
    e.emit('[')
    for fv in range(7, 13):
        compare_eq(e, TPIECE, fv, MG_T4, MG_T6)
        e.move_to(MG_T4)
        e.emit('[')
        e.clear(NOT_FRIENDLY)
        e.clear(MG_T4)
        e.move_to(MG_T4)
        e.emit(']')
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')


def _compute_target_sq(e):
    """Compute TARGET_SQ = TR * 8 + TF."""
    e.clear(TARGET_SQ)
    e.copy_to(TR, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    e.inc(TARGET_SQ, 8)
    e.dec(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    e.copy_to(TF, MG_T4, MG_T5)
    e.add_to(MG_T4, TARGET_SQ)


def _check_bounds(e):
    """Set VALID=1 if TR in [0,7] and TF in [0,7]."""
    e.set_cell(VALID, 1)
    # Check TR
    e.clear(MG_T4)
    for v in range(8):
        compare_eq(e, TR, v, MG_T5, MG_T6)
        e.add_to(MG_T5, MG_T4)
    e.set_cell(MG_T5, 1)
    e.move_to(MG_T4)
    e.emit('[')
    e.clear(MG_T5)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    e.move_to(MG_T5)
    e.emit('[')
    e.clear(VALID)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')

    # Check TF
    e.clear(MG_T4)
    for v in range(8):
        compare_eq(e, TF, v, MG_T5, MG_T6)
        e.add_to(MG_T5, MG_T4)
    e.set_cell(MG_T5, 1)
    e.move_to(MG_T4)
    e.emit('[')
    e.clear(MG_T5)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    e.move_to(MG_T5)
    e.emit('[')
    e.clear(VALID)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')


def _try_target(e):
    """Full target check: bounds -> compute sq -> read board -> check friendly -> store."""
    _check_bounds(e)
    e.copy_to(VALID, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    _compute_target_sq(e)
    _fast_read_board(e, TARGET_SQ, TPIECE)
    _check_not_friendly(e)
    e.copy_to(NOT_FRIENDLY, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    _try_store(e)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')


def _try_target_must_be_empty(e):
    """Target must be empty (for pawn forward moves)."""
    _check_bounds(e)
    e.copy_to(VALID, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    _compute_target_sq(e)
    _fast_read_board(e, TARGET_SQ, TPIECE)
    compare_eq(e, TPIECE, EMPTY, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    _try_store(e)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')


def _try_target_must_be_enemy(e):
    """Target must have enemy piece (for pawn captures)."""
    _check_bounds(e)
    e.copy_to(VALID, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    _compute_target_sq(e)
    _fast_read_board(e, TARGET_SQ, TPIECE)
    # Check nonzero first
    e.copy_to(TPIECE, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    _check_not_friendly(e)
    e.copy_to(NOT_FRIENDLY, MG_T6, MG_T4)
    e.move_to(MG_T6)
    e.emit('[')
    _try_store(e)
    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')


def _set_dr_df(e, offsets):
    """Dispatch on OFF_IDX to set DR_CELL and DF_CELL."""
    for i, (dr, df) in enumerate(offsets):
        compare_eq(e, OFF_IDX, i, MG_T1, MG_T2)
        e.move_to(MG_T1)
        e.emit('[')
        e.clear(DR_CELL)
        if dr > 0:
            e.inc(DR_CELL, dr)
        elif dr < 0:
            e.dec(DR_CELL, -dr)
        e.clear(DF_CELL)
        if df > 0:
            e.inc(DF_CELL, df)
        elif df < 0:
            e.dec(DF_CELL, -df)
        e.clear(MG_T1)
        e.move_to(MG_T1)
        e.emit(']')


def _gen_knight(e):
    """Knight moves via runtime 8-iteration offset loop."""
    offsets = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
    e.set_cell(OFF_IDX, 0)
    e.set_cell(OFF_COUNTER, 8)

    e.move_to(OFF_COUNTER)
    e.emit('[')

    _set_dr_df(e, offsets)

    # TR = RANK + DR_CELL, TF = FILE + DF_CELL
    e.copy_to(RANK, TR, MG_T4)
    e.copy_to(DR_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TR)
    e.copy_to(FILE, TF, MG_T4)
    e.copy_to(DF_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TF)

    _try_target(e)

    e.inc(OFF_IDX)
    e.dec(OFF_COUNTER)
    e.move_to(OFF_COUNTER)
    e.emit(']')


def _gen_king(e):
    """King moves via runtime 8-iteration offset loop."""
    offsets = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    e.set_cell(OFF_IDX, 0)
    e.set_cell(OFF_COUNTER, 8)

    e.move_to(OFF_COUNTER)
    e.emit('[')

    _set_dr_df(e, offsets)

    e.copy_to(RANK, TR, MG_T4)
    e.copy_to(DR_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TR)
    e.copy_to(FILE, TF, MG_T4)
    e.copy_to(DF_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TF)

    _try_target(e)

    e.inc(OFF_IDX)
    e.dec(OFF_COUNTER)
    e.move_to(OFF_COUNTER)
    e.emit(']')


def _gen_pawn(e):
    """Pawn moves using runtime IS_WHITE for direction."""
    # Set DR_CELL to forward direction: +1 if white, -1 if black
    e.clear(DR_CELL)
    e.copy_to(IS_WHITE, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    e.inc(DR_CELL, 1)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    # if black (IS_WHITE==0)
    e.copy_to(IS_WHITE, MG_T4, MG_T5)
    e.set_cell(MG_T5, 1)
    e.move_to(MG_T4)
    e.emit('[')
    e.clear(MG_T5)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    e.move_to(MG_T5)
    e.emit('[')
    e.dec(DR_CELL, 1)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')

    # Forward one square (must be empty)
    e.copy_to(RANK, TR, MG_T4)
    e.copy_to(DR_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TR)
    e.copy_to(FILE, TF, MG_T4)
    _try_target_must_be_empty(e)

    # Double push: TR = RANK + 2*DR_CELL
    e.copy_to(RANK, TR, MG_T4)
    e.copy_to(DR_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TR)
    e.copy_to(DR_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TR)
    e.copy_to(FILE, TF, MG_T4)

    # Only if on starting rank: white rank==1, black rank==6
    e.clear(MG_T4)
    e.copy_to(IS_WHITE, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    compare_eq(e, RANK, 1, MG_T6, MG_T4)
    e.add_to(MG_T6, MG_T4)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')
    # if black
    e.copy_to(IS_WHITE, MG_T5, MG_T6)
    e.set_cell(MG_T6, 1)
    e.move_to(MG_T5)
    e.emit('[')
    e.clear(MG_T6)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')
    e.move_to(MG_T6)
    e.emit('[')
    compare_eq(e, RANK, 6, MG_T5, MG_T4)
    e.add_to(MG_T5, MG_T4)
    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')
    # MG_T4 = 1 if on starting rank
    e.move_to(MG_T4)
    e.emit('[')
    _try_target_must_be_empty(e)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')

    # Captures: diagonal forward
    for df in [-1, 1]:
        e.copy_to(RANK, TR, MG_T4)
        e.copy_to(DR_CELL, MG_T4, MG_T5)
        e.add_to(MG_T4, TR)
        e.copy_to(FILE, TF, MG_T4)
        if df > 0:
            e.inc(TF, df)
        else:
            e.dec(TF, -df)
        _try_target_must_be_enemy(e)


def _gen_sliding(e, directions):
    """Sliding piece moves with runtime direction loop + inner distance loop."""
    n = len(directions)
    e.set_cell(OFF_IDX, 0)
    e.set_cell(OFF_COUNTER, n)

    e.move_to(OFF_COUNTER)
    e.emit('[')

    _set_dr_df(e, directions)

    # Initialize TR/TF to rank+dr, file+df
    e.copy_to(RANK, TR, MG_T4)
    e.copy_to(DR_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TR)
    e.copy_to(FILE, TF, MG_T4)
    e.copy_to(DF_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TF)

    # Inner distance loop (up to 7 steps)
    e.set_cell(DIST_COUNTER, 7)
    e.set_cell(INNER_CONT, 1)

    e.move_to(INNER_CONT)
    e.emit('[')

    # Bounds check
    _check_bounds(e)
    # If invalid, stop
    e.copy_to(VALID, MG_T4, MG_T5)
    e.set_cell(MG_T5, 1)
    e.move_to(MG_T4)
    e.emit('[')
    e.clear(MG_T5)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    e.move_to(MG_T5)
    e.emit('[')
    e.clear(INNER_CONT)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')

    # If valid, check target
    e.copy_to(VALID, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    _compute_target_sq(e)
    _fast_read_board(e, TARGET_SQ, TPIECE)
    _check_not_friendly(e)
    e.copy_to(NOT_FRIENDLY, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    _try_store(e)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')

    # If target square occupied (TPIECE != 0), stop sliding
    e.copy_to(TPIECE, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    e.clear(INNER_CONT)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')

    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')

    # Advance TR/TF by direction
    e.copy_to(DR_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TR)
    e.copy_to(DF_CELL, MG_T4, MG_T5)
    e.add_to(MG_T4, TF)

    e.dec(DIST_COUNTER)
    # If dist_counter == 0, stop
    e.copy_to(DIST_COUNTER, MG_T4, MG_T5)
    e.set_cell(MG_T5, 1)
    e.move_to(MG_T4)
    e.emit('[')
    e.clear(MG_T5)
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')
    e.move_to(MG_T5)
    e.emit('[')
    e.clear(INNER_CONT)
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')

    e.move_to(INNER_CONT)
    e.emit(']')  # end inner distance loop

    e.inc(OFF_IDX)
    e.dec(OFF_COUNTER)
    e.move_to(OFF_COUNTER)
    e.emit(']')  # end direction loop


def generate_moves(e):
    """Generate all pseudo-legal moves using runtime loop."""
    e.clear(BEST_FROM)
    e.clear(BEST_TO)
    e.clear(HAVE_LEGAL)
    e.clear(MOVE_PROMO)

    # Initialize loop
    e.set_cell(SQ, 0)
    e.set_cell(RANK, 0)
    e.set_cell(FILE, 0)
    e.set_cell(COUNTER, 64)

    e.move_to(COUNTER)
    e.emit('[')

    # Read current piece
    _fast_read_board(e, SQ, MG_PIECE)

    # Determine IS_WHITE: piece in [1..6]
    e.clear(IS_WHITE)
    for wv in range(1, 7):
        compare_eq(e, MG_PIECE, wv, MG_T1, MG_T2)
        e.add_to(MG_T1, IS_WHITE)

    # Check if piece belongs to side to move
    e.clear(MINE)

    # Case 1: IS_WHITE==1 AND SIDE_TO_MOVE==0
    e.copy_to(IS_WHITE, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    compare_eq(e, SIDE_TO_MOVE, 0, MG_T2, MG_T3)
    e.add_to(MG_T2, MINE)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')

    # Case 2: piece is black (7-12) AND SIDE_TO_MOVE==1
    e.clear(IS_BLACK)
    for bv in range(7, 13):
        compare_eq(e, MG_PIECE, bv, MG_T1, MG_T2)
        e.add_to(MG_T1, IS_BLACK)

    e.copy_to(IS_BLACK, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    compare_eq(e, SIDE_TO_MOVE, 1, MG_T2, MG_T3)
    e.add_to(MG_T2, MINE)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')

    # If MINE, dispatch on piece type
    e.copy_to(MINE, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')

    e.clear(HANDLED)

    # Pawn
    compare_eq(e, MG_PIECE, WHITE_PAWN, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, BLACK_PAWN, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    e.copy_to(HANDLED, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    _gen_pawn(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    # Knight
    e.clear(HANDLED)
    compare_eq(e, MG_PIECE, WHITE_KNIGHT, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, BLACK_KNIGHT, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    e.copy_to(HANDLED, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    _gen_knight(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    # Bishop or Queen (diagonal)
    e.clear(HANDLED)
    compare_eq(e, MG_PIECE, WHITE_BISHOP, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, BLACK_BISHOP, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, WHITE_QUEEN, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, BLACK_QUEEN, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    e.copy_to(HANDLED, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    _gen_sliding(e, [(-1,-1),(-1,1),(1,-1),(1,1)])
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    # Rook or Queen (straight)
    e.clear(HANDLED)
    compare_eq(e, MG_PIECE, WHITE_ROOK, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, BLACK_ROOK, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, WHITE_QUEEN, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, BLACK_QUEEN, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    e.copy_to(HANDLED, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    _gen_sliding(e, [(-1,0),(1,0),(0,-1),(0,1)])
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    # King
    e.clear(HANDLED)
    compare_eq(e, MG_PIECE, WHITE_KING, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    compare_eq(e, MG_PIECE, BLACK_KING, MG_T2, MG_T3)
    e.add_to(MG_T2, HANDLED)
    e.copy_to(HANDLED, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    _gen_king(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')  # end MINE check

    # Advance: sq++, file++. If file==8: file=0, rank++
    e.inc(SQ)
    e.inc(FILE)
    compare_eq(e, FILE, 8, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    e.set_cell(FILE, 0)
    e.inc(RANK)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')

    e.dec(COUNTER)
    e.move_to(COUNTER)
    e.emit(']')


def _divmod8(e, val, quotient, remainder, tmp):
    """Runtime divmod: quotient = val / 8, remainder = val % 8. Destroys val."""
    # Use TEMP+12, TEMP+13 as compare work cells (safe: never overlap with params)
    cmp1 = TEMP + 12
    cmp2 = TEMP + 13
    e.clear(quotient)
    e.clear(remainder)
    e.move_cell(val, remainder)
    e.set_cell(tmp, 1)
    e.move_to(tmp)
    e.emit('[')
    e.clear(val)
    for v in range(8):
        compare_eq(e, remainder, v, cmp1, cmp2)
        e.add_to(cmp1, val)
    e.copy_to(val, cmp1, cmp2)
    e.move_to(cmp1)
    e.emit('[')
    e.clear(tmp)
    e.clear(cmp1)
    e.move_to(cmp1)
    e.emit(']')
    e.copy_to(tmp, cmp1, cmp2)
    e.move_to(cmp1)
    e.emit('[')
    e.dec(remainder, 8)
    e.inc(quotient)
    e.clear(cmp1)
    e.move_to(cmp1)
    e.emit(']')
    e.move_to(tmp)
    e.emit(']')


def output_bestmove(e):
    """Output 'bestmove XXYY\\n' or 'bestmove 0000\\n'."""
    tmp1 = MG_T1
    tmp2 = MG_T2
    e.print_string("bestmove ")

    compare_eq(e, HAVE_LEGAL, 0, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.print_string("0000")
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, HAVE_LEGAL, 1, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')

    work = MG_T4
    ff = MG_T5
    fr = MG_T6
    tf = TEMP + 10
    tr_cell = TEMP + 11

    # From square: divmod8 to get file and rank
    e.copy_to(BEST_FROM, work, tmp2)
    _divmod8(e, work, fr, ff, tmp2)
    e.copy_to(ff, work, tmp2)
    e.inc(work, 97)  # 'a'
    e.output(work)
    e.copy_to(fr, work, tmp2)
    e.inc(work, 49)  # '1'
    e.output(work)

    # To square: divmod8
    e.copy_to(BEST_TO, work, tmp2)
    _divmod8(e, work, tr_cell, tf, tmp2)
    e.copy_to(tf, work, tmp2)
    e.inc(work, 97)
    e.output(work)
    e.copy_to(tr_cell, work, tmp2)
    e.inc(work, 49)
    e.output(work)

    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    e.print_char(10)
