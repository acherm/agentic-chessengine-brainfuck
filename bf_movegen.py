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
    WHITE_KING_POS, BLACK_KING_POS,
    KING_SQ, ATTACKED,
    SKIP_COUNT, FOUND_LEGAL,
    MG_TPIECE,
    SCRATCH, SCRATCH2, SCRATCH3, SCRATCH4,
    MOVE_FROM, MOVE_TO, MOVE_PIECE, MOVE_TARGET,
    BOARD_COPY,
)
from bf_primitives import compare_eq, if_zero, if_else

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


def _fast_write_board(e, sq_cell, value_cell):
    """Write value_cell to board[sq_cell]. 64-way switch.
    Mirror of _fast_read_board."""
    work = MG_T1
    backup = MG_T2
    flag = MG_T3

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
        e.clear(BOARD_START + i)
        e.copy_to(value_cell, BOARD_START + i, backup)
        e.clear(work)
        e.move_to(work)
        e.emit(']')
        e.move_cell(flag, work)


def _try_store(e):
    """If HAVE_LEGAL==0: if SKIP_COUNT==0, store move; else decrement SKIP_COUNT."""
    compare_eq(e, HAVE_LEGAL, 0, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')

    # Check SKIP_COUNT
    compare_eq(e, SKIP_COUNT, 0, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    # SKIP_COUNT == 0: store this move
    e.copy_to(SQ, BEST_FROM, MG_T3)
    e.copy_to(TARGET_SQ, BEST_TO, MG_T3)
    e.set_cell(HAVE_LEGAL, 1)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    # If SKIP_COUNT != 0: decrement it
    # Check: if HAVE_LEGAL is still 0 (we didn't store), then SKIP_COUNT > 0
    compare_eq(e, HAVE_LEGAL, 0, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    e.dec(SKIP_COUNT)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

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


def is_attacked(e):
    """Check if the current side's king square (KING_SQ) is attacked.

    Sets ATTACKED=1 if attacked, 0 otherwise.
    Uses workspace cells at SCRATCH area (230+) to avoid conflicts.

    Checks: sliding rays, knight, pawn, king adjacency.
    """
    # Workspace cells (high area, no conflicts)
    A_RANK = SCRATCH        # 230 - king rank
    A_FILE = SCRATCH2       # 231 - king file
    A_TR = SCRATCH3         # 232 - target rank
    A_TF = SCRATCH4         # 233 - target file
    A_TSQ = MOVE_FROM       # 234 - target square
    A_TPIECE = MOVE_TO      # 235 - piece at target
    A_TMP1 = MOVE_PIECE     # 236
    A_TMP2 = MOVE_TARGET    # 237
    A_TMP3 = KING_SQ + 2    # 242
    A_VALID = KING_SQ + 3   # 243
    A_DIR_IDX = KING_SQ + 4 # 244
    A_DIR_CNT = KING_SQ + 5 # 245
    A_DR = KING_SQ + 6      # 246
    A_DF = KING_SQ + 7      # 247
    A_DIST = KING_SQ + 8    # 248
    A_INNER = KING_SQ + 9   # 249
    A_FOUND = BOARD_COPY     # 250 - found attacker flag
    A_IS_W = BOARD_COPY + 1  # 251 - is white side (the side whose king we check)

    e.clear(ATTACKED)

    # Compute king rank and file from KING_SQ via divmod8
    # KING_SQ / 8 = rank, KING_SQ % 8 = file
    e.clear(A_RANK)
    e.clear(A_FILE)
    e.copy_to(KING_SQ, A_FILE, A_TMP1)
    # Manual divmod8 loop
    e.set_cell(A_TMP1, 1)
    e.move_to(A_TMP1)
    e.emit('[')
    # Check if A_FILE >= 8
    e.clear(A_TMP2)
    for v in range(8):
        compare_eq(e, A_FILE, v, A_TMP3, A_DR)
        e.add_to(A_TMP3, A_TMP2)
    # A_TMP2 = 1 if A_FILE in [0..7], else 0
    e.copy_to(A_TMP2, A_TMP3, A_DR)
    e.move_to(A_TMP3)
    e.emit('[')
    e.clear(A_TMP1)  # stop loop
    e.clear(A_TMP3)
    e.move_to(A_TMP3)
    e.emit(']')
    # If A_TMP2 was 0 (A_FILE >= 8), subtract 8 and inc rank
    e.copy_to(A_TMP1, A_TMP3, A_DR)
    e.move_to(A_TMP3)
    e.emit('[')
    e.dec(A_FILE, 8)
    e.inc(A_RANK)
    e.clear(A_TMP3)
    e.move_to(A_TMP3)
    e.emit(']')
    e.move_to(A_TMP1)
    e.emit(']')

    # Determine which side's king we're checking
    # A_IS_W = 1 if checking white king (SIDE_TO_MOVE==0 means we just moved as white,
    # but we check the MOVING side's king)
    # Actually: after generate_moves finds a pseudo-legal move for SIDE_TO_MOVE,
    # we make the move and check if OUR king is in check.
    # SIDE_TO_MOVE at that point is still the current player.
    # So if SIDE_TO_MOVE==0 (white), we check white king -> enemy is black (7-12)
    # If SIDE_TO_MOVE==1 (black), we check black king -> enemy is white (1-6)
    e.copy_to(SIDE_TO_MOVE, A_IS_W, A_TMP1)
    # A_IS_W = 0 if white (checking white king), 1 if black

    # === Knight checks (8 positions) ===
    _is_attacked_knight(e, A_RANK, A_FILE, A_TR, A_TF, A_TSQ, A_TPIECE,
                        A_TMP1, A_TMP2, A_TMP3, A_VALID, A_IS_W,
                        A_DIR_IDX, A_DIR_CNT, A_DR, A_DF)

    # === Pawn checks (2 positions) ===
    _is_attacked_pawn(e, A_RANK, A_FILE, A_TR, A_TF, A_TSQ, A_TPIECE,
                      A_TMP1, A_TMP2, A_TMP3, A_VALID, A_IS_W,
                      A_DIR_IDX, A_DIR_CNT, A_DR, A_DF)

    # === King adjacency (8 positions) ===
    _is_attacked_king(e, A_RANK, A_FILE, A_TR, A_TF, A_TSQ, A_TPIECE,
                      A_TMP1, A_TMP2, A_TMP3, A_VALID, A_IS_W,
                      A_DIR_IDX, A_DIR_CNT, A_DR, A_DF)

    # === Sliding rays (8 directions) ===
    _is_attacked_sliding(e, A_RANK, A_FILE, A_TR, A_TF, A_TSQ, A_TPIECE,
                         A_TMP1, A_TMP2, A_TMP3, A_VALID, A_IS_W,
                         A_DIR_IDX, A_DIR_CNT, A_DR, A_DF, A_DIST, A_INNER)


def _is_attacked_bounds(e, tr, tf, valid, tmp1, tmp2, tmp3):
    """Set valid=1 if tr in [0,7] and tf in [0,7]."""
    e.set_cell(valid, 1)
    # Check TR
    e.clear(tmp1)
    for v in range(8):
        compare_eq(e, tr, v, tmp2, tmp3)
        e.add_to(tmp2, tmp1)
    e.set_cell(tmp2, 1)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.move_to(tmp2)
    e.emit('[')
    e.clear(valid)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    # Check TF
    e.clear(tmp1)
    for v in range(8):
        compare_eq(e, tf, v, tmp2, tmp3)
        e.add_to(tmp2, tmp1)
    e.set_cell(tmp2, 1)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.move_to(tmp2)
    e.emit('[')
    e.clear(valid)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')


def _is_attacked_compute_sq(e, tr, tf, tsq, tmp1, tmp2):
    """Compute tsq = tr * 8 + tf."""
    e.clear(tsq)
    e.copy_to(tr, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.inc(tsq, 8)
    e.dec(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.copy_to(tf, tmp1, tmp2)
    e.add_to(tmp1, tsq)



def _is_attacked_check_piece(e, a_tpiece, white_piece, is_w, tmp1, tmp2, tmp3):
    """Check if a_tpiece is the enemy version of white_piece. Sets ATTACKED if so.

    white_piece: the white piece constant (e.g. WHITE_KNIGHT=2)
    If is_w==0 (white king): enemy is black, check white_piece+6
    If is_w==1 (black king): enemy is white, check white_piece
    """
    black_piece = white_piece + 6
    # Check both in one pass to save code
    compare_eq(e, a_tpiece, white_piece, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    # white_piece found — it's an enemy if is_w==1 (black king)
    e.copy_to(is_w, tmp2, tmp3)
    e.move_to(tmp2)
    e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    compare_eq(e, a_tpiece, black_piece, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    # black_piece found — it's an enemy if is_w==0 (white king)
    e.copy_to(is_w, tmp2, tmp3)
    e.set_cell(tmp3, 1)
    e.move_to(tmp2)
    e.emit('[')
    e.clear(tmp3)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    e.move_to(tmp3)
    e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(tmp3)
    e.move_to(tmp3)
    e.emit(']')
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')


def _is_attacked_try_sq(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                         tmp1, tmp2, tmp3, valid, is_w, white_piece):
    """Bounds check, read board, check for enemy piece at (a_tr, a_tf)."""
    _is_attacked_bounds(e, a_tr, a_tf, valid, tmp1, tmp2, tmp3)
    e.copy_to(valid, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    _is_attacked_compute_sq(e, a_tr, a_tf, a_tsq, tmp2, tmp3)
    _fast_read_board(e, a_tsq, a_tpiece)
    _is_attacked_check_piece(e, a_tpiece, white_piece, is_w, tmp1, tmp2, tmp3)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')


def _is_attacked_knight(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                         tmp1, tmp2, tmp3, valid, is_w,
                         dir_idx, dir_cnt, a_dr, a_df):
    """Check 8 knight positions via runtime loop."""
    offsets = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]

    e.set_cell(dir_idx, 0)
    e.set_cell(dir_cnt, 8)
    e.move_to(dir_cnt)
    e.emit('[')

    # Set dr/df from offset table
    for i, (dr, df) in enumerate(offsets):
        compare_eq(e, dir_idx, i, tmp1, tmp2)
        e.move_to(tmp1)
        e.emit('[')
        e.clear(a_dr)
        if dr > 0: e.inc(a_dr, dr)
        elif dr < 0: e.dec(a_dr, -dr)
        e.clear(a_df)
        if df > 0: e.inc(a_df, df)
        elif df < 0: e.dec(a_df, -df)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')

    e.copy_to(a_rank, a_tr, tmp1)
    e.copy_to(a_dr, tmp1, tmp2)
    e.add_to(tmp1, a_tr)
    e.copy_to(a_file, a_tf, tmp1)
    e.copy_to(a_df, tmp1, tmp2)
    e.add_to(tmp1, a_tf)

    _is_attacked_try_sq(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                        tmp1, tmp2, tmp3, valid, is_w, WHITE_KNIGHT)

    e.inc(dir_idx)
    e.dec(dir_cnt)
    e.move_to(dir_cnt)
    e.emit(']')


def _is_attacked_pawn(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                       tmp1, tmp2, tmp3, valid, is_w,
                       dir_idx, dir_cnt, a_dr, a_df):
    """Check 2 pawn attack positions via runtime 2-iteration loop."""
    # Offsets: (-1) and (+1) for file, rank depends on side
    pawn_offsets = [(0, -1), (0, 1)]  # dr is computed dynamically

    e.set_cell(dir_idx, 0)
    e.set_cell(dir_cnt, 2)
    e.move_to(dir_cnt)
    e.emit('[')

    # Set df from offset table (only 2 entries)
    for i, (_, df) in enumerate(pawn_offsets):
        compare_eq(e, dir_idx, i, tmp1, tmp2)
        e.move_to(tmp1)
        e.emit('[')
        e.clear(a_df)
        if df > 0: e.inc(a_df, df)
        elif df < 0: e.dec(a_df, -df)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')

    # Compute target rank based on side
    e.copy_to(a_rank, a_tr, tmp1)
    # if is_w==0 (white king): enemy pawns from rank+1
    e.copy_to(is_w, tmp1, tmp2)
    e.set_cell(tmp2, 1)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.move_to(tmp2)
    e.emit('[')
    e.inc(a_tr, 1)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')
    # if is_w==1 (black king): enemy pawns from rank-1
    e.copy_to(is_w, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    e.dec(a_tr, 1)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')

    e.copy_to(a_file, a_tf, tmp1)
    e.copy_to(a_df, tmp1, tmp2)
    e.add_to(tmp1, a_tf)

    _is_attacked_try_sq(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                        tmp1, tmp2, tmp3, valid, is_w, WHITE_PAWN)

    e.inc(dir_idx)
    e.dec(dir_cnt)
    e.move_to(dir_cnt)
    e.emit(']')


def _is_attacked_king(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                       tmp1, tmp2, tmp3, valid, is_w,
                       dir_idx, dir_cnt, a_dr, a_df):
    """Check 8 king adjacency positions via runtime loop."""
    offsets = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

    e.set_cell(dir_idx, 0)
    e.set_cell(dir_cnt, 8)
    e.move_to(dir_cnt)
    e.emit('[')

    for i, (dr, df) in enumerate(offsets):
        compare_eq(e, dir_idx, i, tmp1, tmp2)
        e.move_to(tmp1)
        e.emit('[')
        e.clear(a_dr)
        if dr > 0: e.inc(a_dr, dr)
        elif dr < 0: e.dec(a_dr, -dr)
        e.clear(a_df)
        if df > 0: e.inc(a_df, df)
        elif df < 0: e.dec(a_df, -df)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')

    e.copy_to(a_rank, a_tr, tmp1)
    e.copy_to(a_dr, tmp1, tmp2)
    e.add_to(tmp1, a_tr)
    e.copy_to(a_file, a_tf, tmp1)
    e.copy_to(a_df, tmp1, tmp2)
    e.add_to(tmp1, a_tf)

    _is_attacked_try_sq(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                        tmp1, tmp2, tmp3, valid, is_w, WHITE_KING)

    e.inc(dir_idx)
    e.dec(dir_cnt)
    e.move_to(dir_cnt)
    e.emit(']')


def _is_attacked_sliding(e, a_rank, a_file, a_tr, a_tf, a_tsq, a_tpiece,
                          tmp1, tmp2, tmp3, valid, is_w,
                          dir_idx, dir_cnt, a_dr, a_df, dist, inner):
    """Check 8 sliding directions for enemy bishop/rook/queen."""
    all_dirs = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

    e.set_cell(dir_idx, 0)
    e.set_cell(dir_cnt, 8)

    e.move_to(dir_cnt)
    e.emit('[')

    # Set dr/df based on dir_idx
    for i, (dr, df) in enumerate(all_dirs):
        compare_eq(e, dir_idx, i, tmp1, tmp2)
        e.move_to(tmp1)
        e.emit('[')
        e.clear(a_dr)
        if dr > 0: e.inc(a_dr, dr)
        elif dr < 0: e.dec(a_dr, -dr)
        e.clear(a_df)
        if df > 0: e.inc(a_df, df)
        elif df < 0: e.dec(a_df, -df)
        e.clear(tmp1)
        e.move_to(tmp1)
        e.emit(']')

    # Initialize TR/TF
    e.copy_to(a_rank, a_tr, tmp1)
    e.copy_to(a_dr, tmp1, tmp2)
    e.add_to(tmp1, a_tr)
    e.copy_to(a_file, a_tf, tmp1)
    e.copy_to(a_df, tmp1, tmp2)
    e.add_to(tmp1, a_tf)

    # Inner distance loop (up to 7 steps)
    e.set_cell(dist, 7)
    e.set_cell(inner, 1)

    e.move_to(inner)
    e.emit('[')

    # Bounds check
    _is_attacked_bounds(e, a_tr, a_tf, valid, tmp1, tmp2, tmp3)
    # If invalid, stop
    e.copy_to(valid, tmp1, tmp2)
    e.set_cell(tmp2, 1)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.move_to(tmp2)
    e.emit('[')
    e.clear(inner)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')

    # If valid, read board and check attackers
    e.copy_to(valid, tmp1, tmp2)
    e.move_to(tmp1)
    e.emit('[')
    _is_attacked_compute_sq(e, a_tr, a_tf, a_tsq, tmp2, tmp3)
    _fast_read_board(e, a_tsq, a_tpiece)

    # Always check queen (attacks on both diagonals and straights)
    _is_attacked_check_piece(e, a_tpiece, WHITE_QUEEN, is_w, tmp2, tmp3, valid)

    # Check bishop for diagonal dirs (0,2,5,7)
    for d_i in [0, 2, 5, 7]:
        compare_eq(e, dir_idx, d_i, tmp2, tmp3)
        e.move_to(tmp2)
        e.emit('[')
        _is_attacked_check_piece(e, a_tpiece, WHITE_BISHOP, is_w, tmp3, valid, a_tsq)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')

    # Check rook for straight dirs (1,3,4,6)
    for d_i in [1, 3, 4, 6]:
        compare_eq(e, dir_idx, d_i, tmp2, tmp3)
        e.move_to(tmp2)
        e.emit('[')
        _is_attacked_check_piece(e, a_tpiece, WHITE_ROOK, is_w, tmp3, valid, a_tsq)
        e.clear(tmp2)
        e.move_to(tmp2)
        e.emit(']')

    # If square occupied, stop sliding
    e.copy_to(a_tpiece, tmp2, tmp3)
    e.move_to(tmp2)
    e.emit('[')
    e.clear(inner)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')

    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')  # end valid check

    # Advance TR/TF by direction
    e.copy_to(a_dr, tmp1, tmp2)
    e.add_to(tmp1, a_tr)
    e.copy_to(a_df, tmp1, tmp2)
    e.add_to(tmp1, a_tf)

    e.dec(dist)
    e.copy_to(dist, tmp1, tmp2)
    e.set_cell(tmp2, 1)
    e.move_to(tmp1)
    e.emit('[')
    e.clear(tmp2)
    e.clear(tmp1)
    e.move_to(tmp1)
    e.emit(']')
    e.move_to(tmp2)
    e.emit('[')
    e.clear(inner)
    e.clear(tmp2)
    e.move_to(tmp2)
    e.emit(']')

    e.move_to(inner)
    e.emit(']')  # end inner distance loop

    e.inc(dir_idx)
    e.dec(dir_cnt)
    e.move_to(dir_cnt)
    e.emit(']')  # end direction loop


def generate_legal_move(e):
    """Generate a legal move using retry loop with legality checking.

    Iterates through pseudo-legal moves via SKIP_COUNT. For each,
    makes the move on the board, checks if own king is attacked,
    unmakes, and accepts if king is safe.

    Sets HAVE_LEGAL=1 and BEST_FROM/BEST_TO if a legal move is found.
    Sets HAVE_LEGAL=0 if no legal moves (checkmate/stalemate).
    """
    # Workspace cells NEAR board/MG area to minimize pointer travel.
    # During legality checking, the movegen workspace (100-119) is used by
    # generate_moves, but cells after that are free.
    # We use cells 120-127 (inside INPUT_BUF but safe during movegen).
    SAVED_PIECE = 120             # near board end (93) and MG_T (94-99)
    SAVED_CAPTURE = 121
    SAVED_KING = 122
    RETRY_CONT = 123
    L_TMP1 = 124
    L_TMP2 = 125
    L_TMP3 = 126

    e.clear(SKIP_COUNT)
    e.clear(FOUND_LEGAL)
    e.set_cell(RETRY_CONT, 1)

    e.move_to(RETRY_CONT)
    e.emit('[')

    # Generate moves — finds the (SKIP_COUNT+1)-th pseudo-legal move
    generate_moves(e)

    # If no pseudo-legal move found (HAVE_LEGAL==0), stop
    e.copy_to(HAVE_LEGAL, L_TMP1, L_TMP2)
    e.set_cell(L_TMP2, 1)
    e.move_to(L_TMP1)
    e.emit('[')
    e.clear(L_TMP2)
    e.clear(L_TMP1)
    e.move_to(L_TMP1)
    e.emit(']')
    e.move_to(L_TMP2)
    e.emit('[')
    # No more pseudo-legal moves — checkmate/stalemate
    e.clear(RETRY_CONT)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    # If HAVE_LEGAL==1, test legality
    e.copy_to(HAVE_LEGAL, L_TMP1, L_TMP2)
    e.move_to(L_TMP1)
    e.emit('[')

    # === MAKE MOVE ===
    # Save captured piece from BEST_TO
    _fast_read_board(e, BEST_TO, SAVED_CAPTURE)
    # Save moving piece from BEST_FROM
    _fast_read_board(e, BEST_FROM, SAVED_PIECE)

    # Write piece to BEST_TO
    _fast_write_board(e, BEST_TO, SAVED_PIECE)
    # Clear BEST_FROM
    e.clear(L_TMP2)
    _fast_write_board(e, BEST_FROM, L_TMP2)

    # Update king position if king moved
    # Save current king pos
    # If SIDE_TO_MOVE==0 (white): check if SAVED_PIECE==WHITE_KING
    # If SIDE_TO_MOVE==1 (black): check if SAVED_PIECE==BLACK_KING
    e.clear(SAVED_KING)
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2)
    e.emit('[')
    e.copy_to(WHITE_KING_POS, SAVED_KING, L_TMP3)
    e.copy_to(BEST_TO, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2)
    e.emit('[')
    e.copy_to(BLACK_KING_POS, SAVED_KING, L_TMP3)
    e.copy_to(BEST_TO, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    # Set KING_SQ to current side's king position
    # SIDE_TO_MOVE==0: KING_SQ = WHITE_KING_POS
    # SIDE_TO_MOVE==1: KING_SQ = BLACK_KING_POS
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)
    e.move_to(L_TMP2)
    e.emit('[')
    e.clear(L_TMP3)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')
    e.move_to(L_TMP3)
    e.emit('[')
    # White: KING_SQ = WHITE_KING_POS
    e.copy_to(WHITE_KING_POS, KING_SQ, L_TMP2)
    e.clear(L_TMP3)
    e.move_to(L_TMP3)
    e.emit(']')
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2)
    e.emit('[')
    # Black: KING_SQ = BLACK_KING_POS
    e.copy_to(BLACK_KING_POS, KING_SQ, L_TMP3)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    # === CHECK IF ATTACKED ===
    is_attacked(e)

    # === UNMAKE MOVE ===
    # Restore BEST_FROM with SAVED_PIECE
    _fast_write_board(e, BEST_FROM, SAVED_PIECE)
    # Restore BEST_TO with SAVED_CAPTURE
    _fast_write_board(e, BEST_TO, SAVED_CAPTURE)

    # Restore king pos if king moved
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2)
    e.emit('[')
    e.copy_to(SAVED_KING, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2)
    e.emit('[')
    e.copy_to(SAVED_KING, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    # === CHECK RESULT ===
    # If not attacked: legal move found!
    e.copy_to(ATTACKED, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)
    e.move_to(L_TMP2)
    e.emit('[')
    e.clear(L_TMP3)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')
    e.move_to(L_TMP3)
    e.emit('[')
    # Not attacked — legal!
    e.set_cell(FOUND_LEGAL, 1)
    e.clear(RETRY_CONT)
    e.clear(L_TMP3)
    e.move_to(L_TMP3)
    e.emit(']')

    # If attacked: try next pseudo-legal move
    e.copy_to(ATTACKED, L_TMP2, L_TMP3)
    e.move_to(L_TMP2)
    e.emit('[')
    e.inc(SKIP_COUNT)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    e.clear(L_TMP1)
    e.move_to(L_TMP1)
    e.emit(']')  # end HAVE_LEGAL check

    e.move_to(RETRY_CONT)
    e.emit(']')  # end retry loop

    # Copy FOUND_LEGAL -> HAVE_LEGAL for output_bestmove
    e.copy_to(FOUND_LEGAL, HAVE_LEGAL, L_TMP1)


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
