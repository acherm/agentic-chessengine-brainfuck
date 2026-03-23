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
    WK_CASTLE, WQ_CASTLE, BK_CASTLE, BQ_CASTLE, EP_FILE,
    KING_SQ, ATTACKED,
    SKIP_COUNT, FOUND_LEGAL,
    MG_TPIECE,
    SCRATCH, SCRATCH2, SCRATCH3, SCRATCH4,
    MOVE_FROM, MOVE_TO, MOVE_PIECE, MOVE_TARGET,
    BOARD_COPY,
    PERFT_MODE, PERFT_COUNT,
    BEST_SCORE, CAND_FROM, CAND_TO, MOVE_SCORE, PIECE_TYPE,
    E_TMP1, E_TMP2, E_TMP3, E_TMP4, E_TMP5,
    IS_CASTLE_MOVE, IS_EP_MOVE, EP_CAPTURE_SQ, SAVED_EP_PAWN,
    GATE_WK, GATE_WQ, GATE_BK, GATE_BQ,
    IN_CHECK,
    ATTACK_CNT, ATTACK_PASS, ILLEGAL_FLAG, DEST_ATTACKED,
    VICTIM_TYPE, ATTACKER_TYPE,
    GIVES_CHECK, SAVED_STM,
    LAST_FROM, LAST_TO,
    D2_BEST_SCORE, D2_CAND_FROM, D2_CAND_TO, D2_OPP_SCORE,
    D2_TMP1, D2_TMP2, D2_TMP3, D2_HAVE_LEGAL,
    D2_SAVED_SKIP, D2_SAVED_RETRY, D2_SAVED_PIECE, D2_SAVED_CAPTURE,
    D2_SAVED_KING, D2_SAVED_BEST_FROM, D2_SAVED_BEST_TO,
    D2_SAVED_IS_CASTLE, D2_SAVED_IS_EP, D2_SAVED_EP_CAP_SQ, D2_SAVED_EP_PAWN,
    D2_SAVED_GATE_WK, D2_SAVED_GATE_WQ, D2_SAVED_GATE_BK, D2_SAVED_GATE_BQ,
    D2_SAVED_IN_CHECK,
    D2_OUR_SCORE, D2_BEST_OUR_SCORE,
    D2_STATE_BASE,
    BETA_CUTOFF, D2_ALPHA, CAPTURE_PHASE, AB_CUTOFF_FLAG,
    D3_BEST_SCORE, D3_CAND_FROM, D3_CAND_TO, D3_OPP_RESULT,
    D3_TMP1, D3_TMP2, D3_TMP3, D3_HAVE_LEGAL,
    D3_OUR_SCORE, D3_BEST_OUR_SCORE,
    D3_SAVED_SKIP, D3_SAVED_RETRY, D3_SAVED_PIECE, D3_SAVED_CAPTURE,
    D3_SAVED_KING, D3_SAVED_BEST_FROM, D3_SAVED_BEST_TO,
    D3_SAVED_IS_CASTLE, D3_SAVED_IS_EP, D3_SAVED_EP_CAP_SQ, D3_SAVED_EP_PAWN,
    D3_SAVED_GATE_WK, D3_SAVED_GATE_WQ, D3_SAVED_GATE_BK, D3_SAVED_GATE_BQ,
    D3_SAVED_IN_CHECK,
    D3_SAVED_D2_BEST, D3_SAVED_D2_CAND_FROM, D3_SAVED_D2_CAND_TO,
    D3_SAVED_D2_HAVE_LEGAL, D3_SAVED_D2_BEST_OUR,
    D3_STATE_BASE,
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


def _gen_castling(e):
    """Castling moves using direct cell access for fixed squares.
    Called inside the king dispatch block (we know piece is a king).
    Generates pseudo-legal castling moves (legality checked later via gate flags).
    """
    # White castling: SQ==4 (king on e1), IS_WHITE
    compare_eq(e, SQ, 4, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    e.copy_to(IS_WHITE, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')

    # White kingside: WK_CASTLE, f1(+5) empty, g1(+6) empty -> target 6
    e.copy_to(WK_CASTLE, MG_T6, MG_T1)
    e.move_to(MG_T6)
    e.emit('[')
    compare_eq(e, BOARD_START + 5, EMPTY, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    compare_eq(e, BOARD_START + 6, EMPTY, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    e.set_cell(TARGET_SQ, 6)
    _try_store(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')

    # White queenside: WQ_CASTLE, d1(+3) empty, c1(+2) empty, b1(+1) empty -> target 2
    e.copy_to(WQ_CASTLE, MG_T6, MG_T1)
    e.move_to(MG_T6)
    e.emit('[')
    compare_eq(e, BOARD_START + 3, EMPTY, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    compare_eq(e, BOARD_START + 2, EMPTY, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    compare_eq(e, BOARD_START + 1, EMPTY, MG_T3, MG_T1)
    e.move_to(MG_T3)
    e.emit('[')
    e.set_cell(TARGET_SQ, 2)
    _try_store(e)
    e.clear(MG_T3)
    e.move_to(MG_T3)
    e.emit(']')
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')

    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')  # end IS_WHITE
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')  # end SQ==4

    # Black castling: SQ==60 (king on e8), IS_BLACK
    compare_eq(e, SQ, 60, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')
    e.copy_to(IS_BLACK, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')

    # Black kingside: BK_CASTLE, f8(+61) empty, g8(+62) empty -> target 62
    e.copy_to(BK_CASTLE, MG_T6, MG_T1)
    e.move_to(MG_T6)
    e.emit('[')
    compare_eq(e, BOARD_START + 61, EMPTY, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    compare_eq(e, BOARD_START + 62, EMPTY, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    e.set_cell(TARGET_SQ, 62)
    _try_store(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')

    # Black queenside: BQ_CASTLE, d8(+59) empty, c8(+58) empty, b8(+57) empty -> target 58
    e.copy_to(BQ_CASTLE, MG_T6, MG_T1)
    e.move_to(MG_T6)
    e.emit('[')
    compare_eq(e, BOARD_START + 59, EMPTY, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    compare_eq(e, BOARD_START + 58, EMPTY, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    compare_eq(e, BOARD_START + 57, EMPTY, MG_T3, MG_T1)
    e.move_to(MG_T3)
    e.emit('[')
    e.set_cell(TARGET_SQ, 58)
    _try_store(e)
    e.clear(MG_T3)
    e.move_to(MG_T3)
    e.emit(']')
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')

    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')  # end IS_BLACK
    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')  # end SQ==60


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

    # Check intermediate square (rank+DR_CELL, file) is empty before double push
    e.copy_to(RANK, MG_T5, MG_T6)
    e.copy_to(DR_CELL, MG_T6, MG_T1)
    e.add_to(MG_T6, MG_T5)          # MG_T5 = rank + DR_CELL (intermediate rank)
    e.clear(MG_T6)
    e.copy_to(MG_T5, MG_T1, MG_T2)
    e.move_to(MG_T1)
    e.emit('[')
    e.inc(MG_T6, 8)
    e.dec(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.copy_to(FILE, MG_T1, MG_T2)
    e.add_to(MG_T1, MG_T6)          # MG_T6 = intermediate_sq
    _fast_read_board(e, MG_T6, MG_T5)   # MG_T5 = piece at intermediate sq
    compare_eq(e, MG_T5, EMPTY, MG_T1, MG_T2)  # MG_T1 = 1 if empty
    e.move_to(MG_T1)
    e.emit('[')
    _try_target_must_be_empty(e)     # check the actual double-push target (TR, TF)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')

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

    # En passant captures
    e.copy_to(EP_FILE, MG_T4, MG_T5)
    e.move_to(MG_T4)
    e.emit('[')  # EP_FILE nonzero

    # White EP: IS_WHITE AND RANK==4 -> target rank 5
    e.copy_to(IS_WHITE, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    compare_eq(e, RANK, 4, MG_T6, MG_T1)
    e.move_to(MG_T6)
    e.emit('[')

    # Left capture: FILE == EP_FILE - 2 (pawn is left of EP target file)
    e.copy_to(FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 2)  # MG_T1 = FILE + 2
    e.copy_to(EP_FILE, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    e.dec(MG_T1)
    e.dec(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    # MG_T1 == 0 iff FILE + 2 == EP_FILE
    e.set_cell(MG_T2, 1)
    e.move_to(MG_T1)
    e.emit('[')
    e.clear(MG_T2)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.move_to(MG_T2)
    e.emit('[')
    e.set_cell(TR, 5)
    e.copy_to(EP_FILE, TF, MG_T3)
    e.dec(TF)  # TF = EP_FILE - 1 (0-indexed)
    _compute_target_sq(e)
    _try_store(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    # Right capture: FILE == EP_FILE (pawn is right of EP target file)
    e.copy_to(FILE, MG_T1, MG_T2)
    e.copy_to(EP_FILE, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    e.dec(MG_T1)
    e.dec(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    e.set_cell(MG_T2, 1)
    e.move_to(MG_T1)
    e.emit('[')
    e.clear(MG_T2)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.move_to(MG_T2)
    e.emit('[')
    e.set_cell(TR, 5)
    e.copy_to(EP_FILE, TF, MG_T3)
    e.dec(TF)
    _compute_target_sq(e)
    _try_store(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')  # end RANK==4
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')  # end IS_WHITE

    # Black EP: IS_BLACK AND RANK==3 -> target rank 2
    e.copy_to(IS_BLACK, MG_T5, MG_T6)
    e.move_to(MG_T5)
    e.emit('[')
    compare_eq(e, RANK, 3, MG_T6, MG_T1)
    e.move_to(MG_T6)
    e.emit('[')

    # Left capture: FILE == EP_FILE - 2
    e.copy_to(FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 2)
    e.copy_to(EP_FILE, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    e.dec(MG_T1)
    e.dec(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    e.set_cell(MG_T2, 1)
    e.move_to(MG_T1)
    e.emit('[')
    e.clear(MG_T2)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.move_to(MG_T2)
    e.emit('[')
    e.set_cell(TR, 2)
    e.copy_to(EP_FILE, TF, MG_T3)
    e.dec(TF)
    _compute_target_sq(e)
    _try_store(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    # Right capture: FILE == EP_FILE
    e.copy_to(FILE, MG_T1, MG_T2)
    e.copy_to(EP_FILE, MG_T2, MG_T3)
    e.move_to(MG_T2)
    e.emit('[')
    e.dec(MG_T1)
    e.dec(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')
    e.set_cell(MG_T2, 1)
    e.move_to(MG_T1)
    e.emit('[')
    e.clear(MG_T2)
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.move_to(MG_T2)
    e.emit('[')
    e.set_cell(TR, 2)
    e.copy_to(EP_FILE, TF, MG_T3)
    e.dec(TF)
    _compute_target_sq(e)
    _try_store(e)
    e.clear(MG_T2)
    e.move_to(MG_T2)
    e.emit(']')

    e.clear(MG_T6)
    e.move_to(MG_T6)
    e.emit(']')  # end RANK==3
    e.clear(MG_T5)
    e.move_to(MG_T5)
    e.emit(']')  # end IS_BLACK

    e.clear(MG_T4)
    e.move_to(MG_T4)
    e.emit(']')  # end EP_FILE nonzero


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
    _gen_castling(e)
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


# ---- Legality workspace (120-129, inside INPUT_BUF, safe during movegen) ----
SAVED_PIECE = 120
SAVED_CAPTURE = 121
SAVED_KING = 122
RETRY_CONT = 123
L_TMP1 = 124
L_TMP2 = 125
L_TMP3 = 126
SAVED_SKIP = 129


def _score_move(e):
    """Score the current legal move. Sets MOVE_SCORE.

    Scoring components:
      - Base: +1
      - MVV capture: P=20, N=64, B=66, R=100, Q=180
      - LVA capture: P=+5, N/B=+3, R=+1, Q/K=+0
      - EP capture: +20
      - Castling: +15
      - Non-king activity: +3
      - Inner center (d4,e4,d5,e5): +3
      - Knight inner center bonus: +3 extra (total +6)
      - Extended center (12 squares): +1
      - Development (leave back rank): +1
      - Pawn center push (pawn to inner center): +2
      - Pawn advancement (rank 7/2): +20, (rank 6/3): +10
      - Rook on 7th rank: +5
      - Check bonus: +15 (applied after dest_attacked penalty)
      - Check+capture synergy: +10 extra
    Also saves VICTIM_TYPE and ATTACKER_TYPE for exchange detection.
    Max possible: ~234 (under 255 8-bit limit).
    """
    e.clear(MOVE_SCORE)
    e.inc(MOVE_SCORE, 1)  # base score
    e.clear(VICTIM_TYPE)
    e.clear(ATTACKER_TYPE)

    # === Capture scoring: MVV + LVA ===
    e.copy_to(SAVED_CAPTURE, PIECE_TYPE, E_TMP1)
    e.move_to(PIECE_TYPE)
    e.emit('[')  # nonzero = capture exists
    # Normalize black pieces (7-12) to (1-6)
    for bv in range(7, 13):
        compare_eq(e, PIECE_TYPE, bv, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.set_cell(PIECE_TYPE, bv - 6)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # MVV: map victim piece type -> value
    for pt, val in [(1, 20), (2, 64), (3, 66), (4, 100), (5, 180)]:
        compare_eq(e, PIECE_TYPE, pt, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.inc(MOVE_SCORE, val)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # LVA: normalize attacker (SAVED_PIECE) to 1-6 in E_TMP3
    e.copy_to(SAVED_PIECE, E_TMP3, E_TMP1)
    for bv in range(7, 13):
        compare_eq(e, E_TMP3, bv, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.set_cell(E_TMP3, bv - 6)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # Map attacker: P(1)=+5, N(2)=+3, B(3)=+3, R(4)=+1
    for pt, val in [(1, 5), (2, 3), (3, 3), (4, 1)]:
        compare_eq(e, E_TMP3, pt, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.inc(MOVE_SCORE, val)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # Save normalized types for exchange detection
    e.copy_to(PIECE_TYPE, VICTIM_TYPE, E_TMP1)
    e.copy_to(E_TMP3, ATTACKER_TYPE, E_TMP1)
    e.clear(E_TMP3)
    e.clear(PIECE_TYPE)
    e.move_to(PIECE_TYPE); e.emit(']')

    # === EP capture: +20 ===
    e.copy_to(IS_EP_MOVE, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    e.inc(MOVE_SCORE, 20)
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    # === Castling bonus: +15 ===
    e.copy_to(IS_CASTLE_MOVE, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    e.inc(MOVE_SCORE, 15)
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    # === Non-king activity bonus: +3 ===
    # E_TMP3=1 if piece is a king, then +3 if E_TMP3==0
    e.clear(E_TMP3)
    compare_eq(e, SAVED_PIECE, WHITE_KING, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    e.inc(E_TMP3)
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_KING, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    e.inc(E_TMP3)
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # if_zero on E_TMP3: not a king -> +3
    e.set_cell(E_TMP4, 1)
    e.move_to(E_TMP3); e.emit('[')
    e.clear(E_TMP4)
    e.clear(E_TMP3); e.move_to(E_TMP3); e.emit(']')
    e.move_to(E_TMP4); e.emit('[')
    e.inc(MOVE_SCORE, 3)
    e.clear(E_TMP4); e.move_to(E_TMP4); e.emit(']')

    # === Center bonus (enhanced) ===
    # Inner center (d4=27, e4=28, d5=35, e5=36): +3
    for sq in [27, 28, 35, 36]:
        compare_eq(e, BEST_TO, sq, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.inc(MOVE_SCORE, 3)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # Extra knight centralization for inner center (+3 more, total +6)
    e.clear(E_TMP4)
    compare_eq(e, SAVED_PIECE, WHITE_KNIGHT, E_TMP1, E_TMP2)
    e.add_to(E_TMP1, E_TMP4)
    compare_eq(e, SAVED_PIECE, BLACK_KNIGHT, E_TMP1, E_TMP2)
    e.add_to(E_TMP1, E_TMP4)
    e.move_to(E_TMP4); e.emit('[')
    for sq in [27, 28, 35, 36]:
        compare_eq(e, BEST_TO, sq, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.inc(MOVE_SCORE, 3)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    e.clear(E_TMP4); e.move_to(E_TMP4); e.emit(']')
    # Extended center (c3-f3, c4, f4, c5, f5, c6-f6): +1
    for sq in [18, 19, 20, 21, 26, 29, 34, 37, 42, 43, 44, 45]:
        compare_eq(e, BEST_TO, sq, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.inc(MOVE_SCORE, 1)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    # === Development bonus: +1 for leaving back rank ===
    # Knight/bishop starting squares: b1,c1,f1,g1,b8,c8,f8,g8
    for sq in [1, 2, 5, 6, 57, 58, 61, 62]:
        compare_eq(e, BEST_FROM, sq, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        e.inc(MOVE_SCORE, 1)
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    # === Pawn center push bonus: +2 for pawn to inner center ===
    for pawn_val in [WHITE_PAWN, BLACK_PAWN]:
        compare_eq(e, SAVED_PIECE, pawn_val, E_TMP1, E_TMP2)
        e.move_to(E_TMP1); e.emit('[')
        for sq in [27, 28, 35, 36]:
            compare_eq(e, BEST_TO, sq, E_TMP2, E_TMP3)
            e.move_to(E_TMP2); e.emit('[')
            e.inc(MOVE_SCORE, 2)
            e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
        e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    # === Pawn advancement bonus ===
    # White pawns: rank 7 (sq 48-55) +20, rank 6 (sq 40-47) +10
    compare_eq(e, SAVED_PIECE, WHITE_PAWN, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    for sq in range(48, 56):
        compare_eq(e, BEST_TO, sq, E_TMP2, E_TMP3)
        e.move_to(E_TMP2); e.emit('[')
        e.inc(MOVE_SCORE, 20)
        e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    for sq in range(40, 48):
        compare_eq(e, BEST_TO, sq, E_TMP2, E_TMP3)
        e.move_to(E_TMP2); e.emit('[')
        e.inc(MOVE_SCORE, 10)
        e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # Black pawns: rank 2 (sq 8-15) +20, rank 3 (sq 16-23) +10
    compare_eq(e, SAVED_PIECE, BLACK_PAWN, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    for sq in range(8, 16):
        compare_eq(e, BEST_TO, sq, E_TMP2, E_TMP3)
        e.move_to(E_TMP2); e.emit('[')
        e.inc(MOVE_SCORE, 20)
        e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    for sq in range(16, 24):
        compare_eq(e, BEST_TO, sq, E_TMP2, E_TMP3)
        e.move_to(E_TMP2); e.emit('[')
        e.inc(MOVE_SCORE, 10)
        e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    # === Rook on 7th rank bonus: +5 ===
    compare_eq(e, SAVED_PIECE, WHITE_ROOK, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    for sq in range(48, 56):
        compare_eq(e, BEST_TO, sq, E_TMP2, E_TMP3)
        e.move_to(E_TMP2); e.emit('[')
        e.inc(MOVE_SCORE, 5)
        e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_ROOK, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    for sq in range(8, 16):
        compare_eq(e, BEST_TO, sq, E_TMP2, E_TMP3)
        e.move_to(E_TMP2); e.emit('[')
        e.inc(MOVE_SCORE, 5)
        e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    # === Anti-repetition: penalize non-capture reverse of last move ===
    # Runtime equality: BEST_FROM==LAST_TO AND BEST_TO==LAST_FROM
    # (can't use compare_eq since LAST_FROM/LAST_TO are cell addresses, not constants)
    compare_eq(e, SAVED_CAPTURE, 0, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    # Check BEST_FROM == LAST_TO via subtraction
    e.copy_to(BEST_FROM, E_TMP2, E_TMP4)
    e.copy_to(LAST_TO, E_TMP3, E_TMP4)
    e.move_to(E_TMP3); e.emit('[')
    e.dec(E_TMP2); e.dec(E_TMP3)
    e.move_to(E_TMP3); e.emit(']')
    # E_TMP2 = BEST_FROM - LAST_TO (mod 256), 0 iff equal
    e.set_cell(E_TMP3, 1)
    e.move_to(E_TMP2); e.emit('[')
    e.clear(E_TMP3); e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.move_to(E_TMP3); e.emit('[')
    # BEST_FROM == LAST_TO: now check BEST_TO == LAST_FROM
    e.copy_to(BEST_TO, E_TMP2, E_TMP4)
    e.copy_to(LAST_FROM, E_TMP4, E_TMP5)
    e.move_to(E_TMP4); e.emit('[')
    e.dec(E_TMP2); e.dec(E_TMP4)
    e.move_to(E_TMP4); e.emit(']')
    # E_TMP2 = BEST_TO - LAST_FROM (mod 256), 0 iff equal
    e.set_cell(E_TMP4, 1)
    e.move_to(E_TMP2); e.emit('[')
    e.clear(E_TMP4); e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.move_to(E_TMP4); e.emit('[')
    # Both match: penalize to minimum score
    e.clear(MOVE_SCORE)
    e.inc(MOVE_SCORE, 1)
    e.clear(E_TMP4); e.move_to(E_TMP4); e.emit(']')
    e.clear(E_TMP3); e.move_to(E_TMP3); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')


def _is_score_better(e, result):
    """Set result=1 if MOVE_SCORE > BEST_SCORE. Runtime loop."""
    tmp_a = MG_T2   # copy of MOVE_SCORE
    tmp_b = MG_T3   # copy of BEST_SCORE
    cont = MG_T4    # loop control
    flag = MG_T5    # temp
    t1 = E_TMP1
    t2 = E_TMP2

    e.copy_to(MOVE_SCORE, tmp_a, t1)
    e.copy_to(BEST_SCORE, tmp_b, t1)
    e.clear(result)
    e.set_cell(cont, 1)
    e.move_to(cont)
    e.emit('[')
    # If tmp_a == 0: A exhausted -> A <= B, stop
    compare_eq(e, tmp_a, 0, flag, t1)
    e.move_to(flag); e.emit('[')
    e.clear(cont)
    e.clear(flag); e.move_to(flag); e.emit(']')
    # If still going, check if tmp_b == 0
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, tmp_b, 0, t1, t2)
    e.move_to(t1); e.emit('[')
    e.set_cell(result, 1)  # A > B
    e.clear(cont)
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(flag); e.move_to(flag); e.emit(']')
    # Decrement both (if still going)
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    e.dec(tmp_a); e.dec(tmp_b)
    e.clear(flag); e.move_to(flag); e.emit(']')
    e.move_to(cont); e.emit(']')


def _scan_sliding_ray(e, ray_squares, enemy_pieces, pt, sc, bk, occ, er, et):
    """Scan a sliding ray using direct cell reads. Sets ATTACKED if enemy found.

    ray_squares: list of board square indices (ordered outward from king)
    enemy_pieces: list of enemy piece values to check (e.g. R/Q or B/Q)
    pt/sc/bk/occ/er/et: workspace cells
    """
    e.set_cell(sc, 1)
    for sq in ray_squares:
        e.copy_to(sc, bk, et)
        e.move_to(bk); e.emit('[')
        e.copy_to(BOARD_START + sq, pt, et)
        # If occupied (pt != 0), stop scanning and check piece type
        e.copy_to(pt, occ, et)
        e.move_to(occ); e.emit('[')
        e.clear(sc)
        for ep in enemy_pieces:
            compare_eq(e, pt, ep, er, et)
            e.move_to(er); e.emit('[')
            e.set_cell(ATTACKED, 1)
            e.clear(er); e.move_to(er); e.emit(']')
        e.clear(occ)
        e.move_to(occ); e.emit(']')
        e.clear(bk)
        e.move_to(bk); e.emit(']')
    e.clear(sc)


def _check_direct_pieces(e, squares, enemy_piece, pt, er, et):
    """Check if any of the given squares has a specific enemy piece."""
    for sq in squares:
        e.copy_to(BOARD_START + sq, pt, et)
        compare_eq(e, pt, enemy_piece, er, et)
        e.move_to(er); e.emit('[')
        e.set_cell(ATTACKED, 1)
        e.clear(er); e.move_to(er); e.emit(']')


def _check_in_check_direct(e):
    """Check if the current side's king is in check, store in IN_CHECK.

    Uses direct board reads for e1 (sq 4) and e8 (sq 60).
    Much smaller than full is_attacked() since no _fast_read_board needed.
    """
    PT = MG_T1
    SC = MG_T2
    BK = MG_T3
    OCC = MG_T4
    ER = MG_T5
    ET = MG_T6

    e.clear(ATTACKED)

    # White (SIDE_TO_MOVE==0): check e1 (sq 4) for black attackers
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(L_TMP3); e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')
    # Straight rays (BLACK_ROOK=10, BLACK_QUEEN=11)
    _scan_sliding_ray(e, [12, 20, 28, 36, 44, 52, 60], [BLACK_ROOK, BLACK_QUEEN], PT, SC, BK, OCC, ER, ET)  # N
    _scan_sliding_ray(e, [3, 2, 1, 0], [BLACK_ROOK, BLACK_QUEEN], PT, SC, BK, OCC, ER, ET)  # W
    _scan_sliding_ray(e, [5, 6, 7], [BLACK_ROOK, BLACK_QUEEN], PT, SC, BK, OCC, ER, ET)  # E
    # Diagonal rays (BLACK_BISHOP=9, BLACK_QUEEN=11)
    _scan_sliding_ray(e, [11, 18, 25, 32], [BLACK_BISHOP, BLACK_QUEEN], PT, SC, BK, OCC, ER, ET)  # NW
    _scan_sliding_ray(e, [13, 22, 31], [BLACK_BISHOP, BLACK_QUEEN], PT, SC, BK, OCC, ER, ET)  # NE
    # Knight (BLACK_KNIGHT=8)
    _check_direct_pieces(e, [10, 14, 19, 21], BLACK_KNIGHT, PT, ER, ET)
    # Pawn (BLACK_PAWN=7, attacks from rank 1)
    _check_direct_pieces(e, [11, 13], BLACK_PAWN, PT, ER, ET)
    # King adjacency (BLACK_KING=12)
    _check_direct_pieces(e, [3, 5, 11, 12, 13], BLACK_KING, PT, ER, ET)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')

    # Black (SIDE_TO_MOVE==1): check e8 (sq 60) for white attackers
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    # Straight rays (WHITE_ROOK=4, WHITE_QUEEN=5)
    _scan_sliding_ray(e, [52, 44, 36, 28, 20, 12, 4], [WHITE_ROOK, WHITE_QUEEN], PT, SC, BK, OCC, ER, ET)  # S
    _scan_sliding_ray(e, [59, 58, 57, 56], [WHITE_ROOK, WHITE_QUEEN], PT, SC, BK, OCC, ER, ET)  # W
    _scan_sliding_ray(e, [61, 62, 63], [WHITE_ROOK, WHITE_QUEEN], PT, SC, BK, OCC, ER, ET)  # E
    # Diagonal rays (WHITE_BISHOP=3, WHITE_QUEEN=5)
    _scan_sliding_ray(e, [51, 42, 33, 24], [WHITE_BISHOP, WHITE_QUEEN], PT, SC, BK, OCC, ER, ET)  # SW
    _scan_sliding_ray(e, [53, 46, 39], [WHITE_BISHOP, WHITE_QUEEN], PT, SC, BK, OCC, ER, ET)  # SE
    # Knight (WHITE_KNIGHT=2)
    _check_direct_pieces(e, [43, 45, 50, 54], WHITE_KNIGHT, PT, ER, ET)
    # Pawn (WHITE_PAWN=1, attacks from rank 6)
    _check_direct_pieces(e, [51, 53], WHITE_PAWN, PT, ER, ET)
    # King adjacency (WHITE_KING=6)
    _check_direct_pieces(e, [59, 61, 51, 52, 53], WHITE_KING, PT, ER, ET)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    e.copy_to(ATTACKED, IN_CHECK, L_TMP1)
    e.clear(ATTACKED)


def generate_legal_move(e):
    """Generate the best legal move using retry loop with legality checking.

    Enumerates all pseudo-legal moves via SKIP_COUNT. For each legal one,
    scores it (MVV-LVA + center bonus) and keeps the best candidate.

    Sets HAVE_LEGAL=1 and BEST_FROM/BEST_TO if a legal move is found.
    Sets HAVE_LEGAL=0 if no legal moves (checkmate/stalemate).
    """

    e.clear(SKIP_COUNT)
    e.clear(FOUND_LEGAL)
    e.clear(BEST_SCORE)
    e.clear(CAND_FROM)
    e.clear(CAND_TO)
    e.set_cell(GATE_WK, 1)
    e.set_cell(GATE_WQ, 1)
    e.set_cell(GATE_BK, 1)
    e.set_cell(GATE_BQ, 1)

    # --- Check if king is currently in check (for castling legality) ---
    # Uses direct board cell reads for e1/e8 (much smaller than full is_attacked)
    _check_in_check_direct(e)

    # === Captures-first phase loop ===
    # CAPTURE_PHASE: 2 = two passes (captures then all), 1 = single pass (perft)
    e.copy_to(PERFT_MODE, L_TMP1, L_TMP2)
    e.set_cell(L_TMP2, 1)  # else flag
    e.move_to(L_TMP1); e.emit('[')
    e.clear(L_TMP2)
    e.set_cell(CAPTURE_PHASE, 1)  # perft: single pass (all moves)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.move_to(L_TMP2); e.emit('[')
    e.set_cell(CAPTURE_PHASE, 2)  # normal: two passes
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    e.move_to(CAPTURE_PHASE)
    e.emit('[')  # phase loop
    e.dec(CAPTURE_PHASE)  # 2→1 (captures only) or 1→0 (all moves)

    e.clear(SKIP_COUNT)
    e.clear(AB_CUTOFF_FLAG)
    # Re-init gate flags for each phase (needed since gate gets cleared during move enumeration)
    e.set_cell(GATE_WK, 1)
    e.set_cell(GATE_WQ, 1)
    e.set_cell(GATE_BK, 1)
    e.set_cell(GATE_BQ, 1)
    _check_in_check_direct(e)

    e.set_cell(RETRY_CONT, 1)

    e.move_to(RETRY_CONT)
    e.emit('[')

    # Save SKIP_COUNT (generate_moves consumes it via decrement)
    e.copy_to(SKIP_COUNT, SAVED_SKIP, L_TMP1)

    # Generate moves — finds the (SKIP_COUNT+1)-th pseudo-legal move
    generate_moves(e)

    # Restore SKIP_COUNT to its pre-generate_moves value
    e.copy_to(SAVED_SKIP, SKIP_COUNT, L_TMP1)

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

    # === CAPTURE FILTER: skip non-captures in captures-only phase ===
    # E_TMP5 = PROCESS_FLAG: 1 = process this move, 0 = skip
    e.set_cell(E_TMP5, 1)
    e.copy_to(CAPTURE_PHASE, E_TMP1, E_TMP2)  # E_TMP1 = phase value
    e.move_to(E_TMP1); e.emit('[')  # if CAPTURE_PHASE > 0
    # Check if SAVED_CAPTURE == 0 (non-capture)
    compare_eq(e, SAVED_CAPTURE, 0, E_TMP2, E_TMP3)
    e.move_to(E_TMP2); e.emit('[')  # if non-capture
    # Skip: non-capture during captures-only phase
    e.clear(E_TMP5)  # don't process
    e.inc(SKIP_COUNT)  # move to next
    e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')

    e.move_to(E_TMP5); e.emit('[')  # if PROCESS_FLAG == 1
    e.clear(E_TMP5)

    # Save moving piece from BEST_FROM
    _fast_read_board(e, BEST_FROM, SAVED_PIECE)

    # --- Detect special moves ---
    e.clear(IS_CASTLE_MOVE)
    e.clear(IS_EP_MOVE)
    e.clear(EP_CAPTURE_SQ)
    e.clear(SAVED_EP_PAWN)

    # Castling detection: king moving to castling target squares
    # White: SAVED_PIECE==WHITE_KING and BEST_FROM==4 and (BEST_TO==6 or BEST_TO==2)
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 4, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Black: SAVED_PIECE==BLACK_KING and BEST_FROM==60 and (BEST_TO==62 or BEST_TO==58)
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 60, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 62, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # EP detection: pawn capturing to empty EP target square
    # White EP: SAVED_PIECE==WHITE_PAWN, SAVED_CAPTURE==EMPTY,
    #           BEST_TO == 39 + EP_FILE (EP target on rank 5)
    compare_eq(e, SAVED_PIECE, WHITE_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, SAVED_CAPTURE, EMPTY, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    # Check EP_FILE != 0
    e.copy_to(EP_FILE, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    # Compute expected EP target: EP_FILE + 39
    e.copy_to(EP_FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 39)
    # Runtime equality: BEST_TO == MG_T1?
    e.copy_to(BEST_TO, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.dec(MG_T1); e.dec(MG_T2)
    e.move_to(MG_T2); e.emit(']')
    # If MG_T1 == 0, they were equal
    compare_eq(e, MG_T1, 0, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.set_cell(IS_EP_MOVE, 1)
    # EP_CAPTURE_SQ = 31 + EP_FILE (one rank below target)
    e.copy_to(EP_FILE, EP_CAPTURE_SQ, MG_T3)
    e.inc(EP_CAPTURE_SQ, 31)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.clear(MG_T1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Black EP: SAVED_PIECE==BLACK_PAWN, SAVED_CAPTURE==EMPTY,
    #           BEST_TO == 15 + EP_FILE (EP target on rank 2)
    compare_eq(e, SAVED_PIECE, BLACK_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, SAVED_CAPTURE, EMPTY, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(EP_FILE, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.copy_to(EP_FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 15)
    e.copy_to(BEST_TO, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.dec(MG_T1); e.dec(MG_T2)
    e.move_to(MG_T2); e.emit(']')
    compare_eq(e, MG_T1, 0, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.set_cell(IS_EP_MOVE, 1)
    # EP_CAPTURE_SQ = 23 + EP_FILE (one rank above target)
    e.copy_to(EP_FILE, EP_CAPTURE_SQ, MG_T3)
    e.inc(EP_CAPTURE_SQ, 23)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.clear(MG_T1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Write piece to BEST_TO
    _fast_write_board(e, BEST_TO, SAVED_PIECE)
    # Clear BEST_FROM
    e.clear(L_TMP2)
    _fast_write_board(e, BEST_FROM, L_TMP2)

    # --- Castling rook make (direct cell ops on fixed squares) ---
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    # White kingside: BEST_TO==6, rook h1(+7) to f1(+5)
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 7, BOARD_START + 5, L_TMP1)
    e.clear(BOARD_START + 7)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # White queenside: BEST_TO==2, rook a1(+0) to d1(+3)
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 0, BOARD_START + 3, L_TMP1)
    e.clear(BOARD_START + 0)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # Black kingside: BEST_TO==62, rook h8(+63) to f8(+61)
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 63, BOARD_START + 61, L_TMP1)
    e.clear(BOARD_START + 63)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # Black queenside: BEST_TO==58, rook a8(+56) to d8(+59)
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 56, BOARD_START + 59, L_TMP1)
    e.clear(BOARD_START + 56)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # --- EP capture make (save + clear captured pawn) ---
    e.copy_to(IS_EP_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    # 16-way switch on EP_CAPTURE_SQ (8 white + 8 black files)
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, EP_CAPTURE_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.copy_to(BOARD_START + capture_sq, SAVED_EP_PAWN, L_TMP1)
            e.clear(BOARD_START + capture_sq)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

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
    # Gate check for castling: if intermediate square was attacked, block castling
    e.clear(ATTACKED)
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    # White kingside (BEST_TO==6): check GATE_WK
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_WK, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # White queenside (BEST_TO==2): check GATE_WQ
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_WQ, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # Black kingside (BEST_TO==62): check GATE_BK
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_BK, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # Black queenside (BEST_TO==58): check GATE_BQ
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_BQ, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Block castling if king is currently in check
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(IN_CHECK, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === 3-PASS ATTACK CHECK (king legality + hanging piece + check detection) ===
    e.clear(DEST_ATTACKED)
    e.clear(ILLEGAL_FLAG)
    e.clear(ATTACK_PASS)
    e.clear(GIVES_CHECK)

    compare_eq(e, ATTACKED, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')

    e.set_cell(ATTACK_CNT, 3)
    e.move_to(ATTACK_CNT)
    e.emit('[')

    # Run is_attacked (ONE inline, executes 1-3 times via loop)
    e.clear(ATTACKED)
    is_attacked(e)

    # Dispatch on pass number: 0, 1, or 2
    compare_eq(e, ATTACK_PASS, 0, L_TMP3, MG_T1)
    e.set_cell(MG_T4, 1)  # else flag
    e.move_to(L_TMP3); e.emit('[')
    e.clear(MG_T4)

    # === PASS 0: king legality check ===
    e.copy_to(ATTACKED, ILLEGAL_FLAG, MG_T1)
    e.inc(ATTACK_PASS)

    # If king in check: exit loop early (skip passes 1 & 2)
    e.copy_to(ATTACKED, MG_T1, MG_T2)
    e.move_to(MG_T1); e.emit('[')
    e.clear(ATTACK_CNT)
    e.inc(ATTACK_CNT, 1)  # dec to 0 → exit
    e.clear(MG_T1); e.move_to(MG_T1); e.emit(']')

    # If king safe: set KING_SQ = BEST_TO for pass 1 (dest safety)
    e.set_cell(MG_T1, 1)  # else flag
    e.copy_to(ATTACKED, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.clear(MG_T1)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.move_to(MG_T1); e.emit('[')
    e.copy_to(BEST_TO, KING_SQ, MG_T2)
    e.clear(MG_T1); e.move_to(MG_T1); e.emit(']')

    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')

    e.move_to(MG_T4); e.emit('[')
    # === PASS 1 or 2 (ATTACK_PASS >= 1) ===
    compare_eq(e, ATTACK_PASS, 1, L_TMP3, MG_T1)
    e.set_cell(MG_T5, 1)  # else flag for pass 2
    e.move_to(L_TMP3); e.emit('[')
    e.clear(MG_T5)

    # === PASS 1: destination safety + setup for check detection ===
    e.copy_to(ATTACKED, DEST_ATTACKED, MG_T1)
    e.inc(ATTACK_PASS)

    # Setup for pass 2: save STM, flip it, set KING_SQ to opponent king
    e.copy_to(SIDE_TO_MOVE, SAVED_STM, MG_T1)
    # Use SAVED_STM (not STM) for branching to avoid read-after-write issue
    # If SAVED_STM==0 (white): set STM=1, KING_SQ=BLACK_KING_POS
    # If SAVED_STM==1 (black): set STM=0, KING_SQ=WHITE_KING_POS
    compare_eq(e, SAVED_STM, 0, MG_T1, MG_T2)
    e.set_cell(MG_T2, 1)  # else flag
    e.move_to(MG_T1); e.emit('[')
    e.clear(MG_T2)
    e.set_cell(SIDE_TO_MOVE, 1)
    e.copy_to(BLACK_KING_POS, KING_SQ, MG_T3)
    e.clear(MG_T1); e.move_to(MG_T1); e.emit(']')
    e.move_to(MG_T2); e.emit('[')
    e.clear(SIDE_TO_MOVE)
    e.copy_to(WHITE_KING_POS, KING_SQ, MG_T3)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')

    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')

    e.move_to(MG_T5); e.emit('[')
    # === PASS 2: check detection ===
    e.copy_to(ATTACKED, GIVES_CHECK, MG_T1)
    # Restore SIDE_TO_MOVE from SAVED_STM
    e.copy_to(SAVED_STM, SIDE_TO_MOVE, MG_T1)
    e.clear(MG_T5); e.move_to(MG_T5); e.emit(']')

    e.clear(MG_T4); e.move_to(MG_T4); e.emit(']')

    e.dec(ATTACK_CNT)
    e.move_to(ATTACK_CNT)
    e.emit(']')

    # Restore ATTACKED from king check result
    e.copy_to(ILLEGAL_FLAG, ATTACKED, MG_T1)

    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === UNMAKE MOVE ===
    # Restore BEST_FROM with SAVED_PIECE
    _fast_write_board(e, BEST_FROM, SAVED_PIECE)
    # Restore BEST_TO with SAVED_CAPTURE
    _fast_write_board(e, BEST_TO, SAVED_CAPTURE)

    # --- Castling rook unmake (reverse of make) ---
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    # White kingside: rook f1(+5) back to h1(+7)
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 5, BOARD_START + 7, L_TMP1)
    e.clear(BOARD_START + 5)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # White queenside: rook d1(+3) back to a1(+0)
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 3, BOARD_START + 0, L_TMP1)
    e.clear(BOARD_START + 3)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # Black kingside: rook f8(+61) back to h8(+63)
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 61, BOARD_START + 63, L_TMP1)
    e.clear(BOARD_START + 61)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    # Black queenside: rook d8(+59) back to a8(+56)
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 59, BOARD_START + 56, L_TMP1)
    e.clear(BOARD_START + 59)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # --- EP capture unmake (restore captured pawn) ---
    e.copy_to(IS_EP_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, EP_CAPTURE_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.copy_to(SAVED_EP_PAWN, BOARD_START + capture_sq, L_TMP1)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

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
    # Branch on PERFT_MODE: perft mode outputs move and continues,
    # normal mode stops at first legal move.
    e.copy_to(PERFT_MODE, L_TMP2, MG_T1)
    e.set_cell(MG_T1, 1)  # else flag
    e.move_to(L_TMP2)
    e.emit('[')
    # --- Perft mode: output move, count it, continue searching ---
    _output_move_algebraic(e)
    e.inc(PERFT_COUNT)
    e.inc(SKIP_COUNT)
    e.clear(MG_T1)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')
    e.move_to(MG_T1)
    e.emit('[')
    # --- Normal mode: score move, keep best, continue ---
    _score_move(e)
    # Penalize moves to attacked squares
    e.copy_to(DEST_ATTACKED, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    # Case 1: Non-capture to attacked square -> score = 1
    compare_eq(e, SAVED_CAPTURE, 0, E_TMP2, E_TMP3)
    e.move_to(E_TMP2); e.emit('[')
    e.clear(MOVE_SCORE)
    e.inc(MOVE_SCORE, 1)
    e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    # Case 2: Capture on attacked square -> check losing exchange
    e.copy_to(SAVED_CAPTURE, E_TMP2, E_TMP3)  # nonzero if capture
    e.move_to(E_TMP2); e.emit('[')
    # Compare ATTACKER_TYPE > VICTIM_TYPE via decrement loop
    e.copy_to(ATTACKER_TYPE, E_TMP4, E_TMP3)
    e.copy_to(VICTIM_TYPE, E_TMP5, E_TMP3)
    e.set_cell(E_TMP3, 1)  # loop control
    e.move_to(E_TMP3); e.emit('[')
    # If attacker copy == 0: exhausted, attacker <= victim, stop
    compare_eq(e, E_TMP4, 0, MG_T1, MG_T2)
    e.move_to(MG_T1); e.emit('[')
    e.clear(E_TMP3)
    e.clear(MG_T1); e.move_to(MG_T1); e.emit(']')
    # If still going, check if victim copy == 0: attacker > victim
    e.copy_to(E_TMP3, MG_T1, MG_T2)
    e.move_to(MG_T1); e.emit('[')
    compare_eq(e, E_TMP5, 0, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    # Losing exchange! Cap score to 2
    e.clear(MOVE_SCORE)
    e.inc(MOVE_SCORE, 2)
    e.clear(E_TMP3)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.clear(MG_T1); e.move_to(MG_T1); e.emit(']')
    # Decrement both (if still going)
    e.copy_to(E_TMP3, MG_T1, MG_T2)
    e.move_to(MG_T1); e.emit('[')
    e.dec(E_TMP4); e.dec(E_TMP5)
    e.clear(MG_T1); e.move_to(MG_T1); e.emit(']')
    e.move_to(E_TMP3); e.emit(']')
    e.clear(E_TMP4); e.clear(E_TMP5)
    e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    # === Check bonus: +15 for giving check, +10 extra if also a capture ===
    e.copy_to(GIVES_CHECK, E_TMP1, E_TMP2)
    e.move_to(E_TMP1); e.emit('[')
    e.inc(MOVE_SCORE, 15)
    e.copy_to(SAVED_CAPTURE, E_TMP2, E_TMP3)
    e.move_to(E_TMP2); e.emit('[')
    e.inc(MOVE_SCORE, 10)
    e.clear(E_TMP2); e.move_to(E_TMP2); e.emit(']')
    e.clear(E_TMP1); e.move_to(E_TMP1); e.emit(']')
    _is_score_better(e, L_TMP2)
    e.move_to(L_TMP2)
    e.emit('[')
    # Update best candidate
    e.copy_to(BEST_FROM, CAND_FROM, E_TMP1)
    e.copy_to(BEST_TO, CAND_TO, E_TMP1)
    e.clear(BEST_SCORE)
    e.copy_to(MOVE_SCORE, BEST_SCORE, E_TMP1)
    # Beta cutoff: if BEST_SCORE >= BETA_CUTOFF, stop searching
    _is_ge(e, BEST_SCORE, BETA_CUTOFF, E_TMP4)
    e.move_to(E_TMP4); e.emit('[')
    e.clear(RETRY_CONT)    # stop retry loop
    e.set_cell(AB_CUTOFF_FLAG, 1)
    e.clear(E_TMP4); e.move_to(E_TMP4); e.emit(']')
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')
    e.inc(SKIP_COUNT)  # continue to next move
    e.clear(MG_T1)
    e.move_to(MG_T1)
    e.emit(']')
    e.clear(L_TMP3)
    e.move_to(L_TMP3)
    e.emit(']')

    # If attacked: update gate flags and try next pseudo-legal move
    e.copy_to(ATTACKED, L_TMP2, L_TMP3)
    e.move_to(L_TMP2)
    e.emit('[')
    # Gate updates: if king move to castling intermediate square was attacked
    compare_eq(e, BEST_FROM, 4, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 5, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_WK)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 3, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_WQ)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_FROM, 60, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 61, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_BK)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 59, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_BQ)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.inc(SKIP_COUNT)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    # end PROCESS_FLAG (capture filter gate)
    e.move_to(E_TMP5)
    e.emit(']')  # E_TMP5 was cleared at top, so this falls through

    e.clear(L_TMP1)
    e.move_to(L_TMP1)
    e.emit(']')  # end HAVE_LEGAL check

    e.move_to(RETRY_CONT)
    e.emit(']')  # end retry loop

    # If beta cutoff happened, skip phase 2
    e.copy_to(AB_CUTOFF_FLAG, L_TMP1, L_TMP2)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(CAPTURE_PHASE)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')

    e.move_to(CAPTURE_PHASE)
    e.emit(']')  # end phase loop

    # --- Finalization: in normal mode, if BEST_SCORE > 0, use best candidate ---
    e.copy_to(PERFT_MODE, L_TMP1, L_TMP2)
    e.set_cell(L_TMP2, 1)  # else flag
    e.move_to(L_TMP1)
    e.emit('[')
    e.clear(L_TMP2)
    e.clear(L_TMP1)
    e.move_to(L_TMP1)
    e.emit(']')
    e.move_to(L_TMP2)
    e.emit('[')
    # Normal mode: finalize best candidate
    e.copy_to(BEST_SCORE, L_TMP1, L_TMP3)
    e.move_to(L_TMP1)
    e.emit('[')
    e.copy_to(CAND_FROM, BEST_FROM, L_TMP3)
    e.copy_to(CAND_TO, BEST_TO, L_TMP3)
    # Save last move for anti-repetition
    e.copy_to(CAND_FROM, LAST_FROM, L_TMP3)
    e.copy_to(CAND_TO, LAST_TO, L_TMP3)
    e.set_cell(FOUND_LEGAL, 1)
    e.clear(L_TMP1)
    e.move_to(L_TMP1)
    e.emit(']')
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

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


def _output_move_algebraic(e):
    """Output BEST_FROM and BEST_TO as algebraic notation (e.g. e2e4) + newline.

    Uses: MG_T2, MG_T4, MG_T5, MG_T6, TEMP+10, TEMP+11, TEMP+12, TEMP+13.
    Does NOT touch MG_T1 or MG_T3.
    """
    work = MG_T4
    ff = MG_T5
    fr = MG_T6
    tf = TEMP + 10
    tr_cell = TEMP + 11
    tmp = MG_T2

    # From square: divmod8 to get file and rank
    e.copy_to(BEST_FROM, work, tmp)
    _divmod8(e, work, fr, ff, tmp)
    e.copy_to(ff, work, tmp)
    e.inc(work, 97)  # 'a'
    e.output(work)
    e.copy_to(fr, work, tmp)
    e.inc(work, 49)  # '1'
    e.output(work)

    # To square: divmod8
    e.copy_to(BEST_TO, work, tmp)
    _divmod8(e, work, tr_cell, tf, tmp)
    e.copy_to(tf, work, tmp)
    e.inc(work, 97)  # 'a'
    e.output(work)
    e.copy_to(tr_cell, work, tmp)
    e.inc(work, 49)  # '1'
    e.output(work)

    # Newline
    e.print_char(10)


def _divmod10(e, val, quotient, remainder, tmp):
    """Runtime divmod by 10: quotient = val / 10, remainder = val % 10. Destroys val."""
    cmp1 = TEMP + 12
    cmp2 = TEMP + 13
    e.clear(quotient)
    e.clear(remainder)
    e.move_cell(val, remainder)
    e.set_cell(tmp, 1)
    e.move_to(tmp)
    e.emit('[')
    e.clear(val)
    for v in range(10):
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
    e.dec(remainder, 10)
    e.inc(quotient)
    e.clear(cmp1)
    e.move_to(cmp1)
    e.emit(']')
    e.move_to(tmp)
    e.emit(']')


def output_decimal(e, val_cell):
    """Output val_cell (0-255) as decimal ASCII string, suppressing leading zeros.

    Uses: MG_T2, MG_T4, MG_T5, MG_T6, TEMP+8..13.
    """
    W = MG_T4
    Q = MG_T5
    R = MG_T6
    TMP = MG_T2
    ONES = TEMP + 8
    TENS = TEMP + 9
    HUND = TEMP + 10
    DONE = TEMP + 11

    # Step 1: extract ones digit: val / 10 -> Q, val % 10 -> R
    e.copy_to(val_cell, W, TMP)
    _divmod10(e, W, Q, R, TMP)
    e.clear(ONES)
    e.move_cell(R, ONES)

    # Step 2: extract tens and hundreds: Q / 10 -> hundreds, Q % 10 -> tens
    e.copy_to(Q, W, TMP)
    _divmod10(e, W, Q, R, TMP)
    e.clear(TENS)
    e.move_cell(R, TENS)
    e.clear(HUND)
    e.move_cell(Q, HUND)

    # Output with leading zero suppression
    e.clear(DONE)

    # Hundreds: output if != 0
    e.copy_to(HUND, W, TMP)
    e.move_to(W)
    e.emit('[')
    e.copy_to(HUND, TMP, R)
    e.inc(TMP, 48)  # '0'
    e.output(TMP)
    e.set_cell(DONE, 1)
    e.clear(W)
    e.move_to(W)
    e.emit(']')

    # Tens: output if DONE==1 (hundreds was output) OR TENS != 0
    e.copy_to(DONE, W, TMP)       # W = DONE (0 or 1)
    e.copy_to(TENS, TMP, R)       # TMP = TENS
    e.move_to(TMP)
    e.emit('[')                    # if TENS != 0
    e.set_cell(W, 1)              #   ensure W = 1
    e.clear(TMP)
    e.move_to(TMP)
    e.emit(']')
    # W = 1 if (DONE or TENS != 0), 0 otherwise
    e.move_to(W)
    e.emit('[')
    e.copy_to(TENS, TMP, R)
    e.inc(TMP, 48)
    e.output(TMP)
    e.clear(W)
    e.move_to(W)
    e.emit(']')

    # Always output ones
    e.copy_to(ONES, W, TMP)
    e.inc(W, 48)
    e.output(W)


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


# ===========================================================================
# Depth-2 minimax search
# ===========================================================================

def _d2_save_state(e, tmp):
    """Save full game state (board + state cells) to D2_STATE_BASE."""
    for i in range(64):
        e.copy_to(BOARD_START + i, D2_STATE_BASE + i, tmp)
    e.copy_to(SIDE_TO_MOVE, D2_STATE_BASE + 64, tmp)
    e.copy_to(EP_FILE, D2_STATE_BASE + 65, tmp)
    e.copy_to(WHITE_KING_POS, D2_STATE_BASE + 66, tmp)
    e.copy_to(BLACK_KING_POS, D2_STATE_BASE + 67, tmp)
    e.copy_to(WK_CASTLE, D2_STATE_BASE + 68, tmp)
    e.copy_to(WQ_CASTLE, D2_STATE_BASE + 69, tmp)
    e.copy_to(BK_CASTLE, D2_STATE_BASE + 70, tmp)
    e.copy_to(BQ_CASTLE, D2_STATE_BASE + 71, tmp)


def _d2_restore_state(e, tmp):
    """Restore full game state from D2_STATE_BASE."""
    for i in range(64):
        e.copy_to(D2_STATE_BASE + i, BOARD_START + i, tmp)
    e.copy_to(D2_STATE_BASE + 64, SIDE_TO_MOVE, tmp)
    e.copy_to(D2_STATE_BASE + 65, EP_FILE, tmp)
    e.copy_to(D2_STATE_BASE + 66, WHITE_KING_POS, tmp)
    e.copy_to(D2_STATE_BASE + 67, BLACK_KING_POS, tmp)
    e.copy_to(D2_STATE_BASE + 68, WK_CASTLE, tmp)
    e.copy_to(D2_STATE_BASE + 69, WQ_CASTLE, tmp)
    e.copy_to(D2_STATE_BASE + 70, BK_CASTLE, tmp)
    e.copy_to(D2_STATE_BASE + 71, BQ_CASTLE, tmp)


def _is_d2_move_better(e, result):
    """Set result=1 if this depth-2 move is better than current best.

    Better means:
    1. D2_OPP_SCORE < D2_BEST_SCORE (minimax: lower opponent score wins), OR
    2. D2_OPP_SCORE == D2_BEST_SCORE AND D2_OUR_SCORE > D2_BEST_OUR_SCORE (tiebreak)

    Uses D2_TMP1-3, E_TMP1-4 as workspace.
    """
    opp_copy = D2_TMP1
    best_copy = D2_TMP2
    cont = D2_TMP3
    tied = E_TMP1
    flag = E_TMP2
    t1 = E_TMP3
    t2 = E_TMP4

    e.clear(result)
    e.clear(tied)

    # Phase 1: compare opponent scores via simultaneous decrement
    e.copy_to(D2_OPP_SCORE, opp_copy, t1)
    e.copy_to(D2_BEST_SCORE, best_copy, t1)
    e.set_cell(cont, 1)
    e.move_to(cont); e.emit('[')

    # Check if best_copy == 0
    compare_eq(e, best_copy, 0, flag, t1)
    e.move_to(flag); e.emit('[')
    # BEST exhausted: check if opp also 0 (tied) or not (OPP > BEST)
    compare_eq(e, opp_copy, 0, t1, t2)
    e.move_to(t1); e.emit('[')
    e.set_cell(tied, 1)  # both zero: tied
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(cont)
    e.clear(flag); e.move_to(flag); e.emit(']')

    # If still going, check if opp_copy == 0
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, opp_copy, 0, t1, t2)
    e.move_to(t1); e.emit('[')
    e.set_cell(result, 1)  # OPP < BEST: strictly better
    e.clear(cont)
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(flag); e.move_to(flag); e.emit(']')

    # Decrement both (if still going)
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    e.dec(opp_copy); e.dec(best_copy)
    e.clear(flag); e.move_to(flag); e.emit(']')

    e.move_to(cont); e.emit(']')

    # Phase 2: if tied on opp_score, use our_score as tiebreaker
    e.move_to(tied); e.emit('[')
    e.copy_to(D2_OUR_SCORE, opp_copy, t1)       # reuse as our_score copy
    e.copy_to(D2_BEST_OUR_SCORE, best_copy, t1)  # reuse as best_our copy
    e.set_cell(cont, 1)
    e.move_to(cont); e.emit('[')
    # If our_copy == 0: exhausted → OUR <= BEST_OUR, stop
    compare_eq(e, opp_copy, 0, flag, t1)
    e.move_to(flag); e.emit('[')
    e.clear(cont)
    e.clear(flag); e.move_to(flag); e.emit(']')
    # If still going, check if best_copy == 0: OUR > BEST_OUR
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, best_copy, 0, t1, t2)
    e.move_to(t1); e.emit('[')
    e.set_cell(result, 1)  # OUR > BEST_OUR: tiebreak winner
    e.clear(cont)
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(flag); e.move_to(flag); e.emit(']')
    # Decrement both
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    e.dec(opp_copy); e.dec(best_copy)
    e.clear(flag); e.move_to(flag); e.emit(']')
    e.move_to(cont); e.emit(']')

    e.clear(tied); e.move_to(tied); e.emit(']')


def _is_ge(e, a_cell, b_cell, result):
    """Set result=1 if a_cell >= b_cell. Uses simultaneous decrement.

    Uses E_TMP1-E_TMP3 as workspace. Destroys nothing except result and workspace.
    """
    tmp_a = E_TMP1
    tmp_b = E_TMP2
    cont = E_TMP3
    flag = MG_T5
    t1 = MG_T6

    e.copy_to(a_cell, tmp_a, t1)
    e.copy_to(b_cell, tmp_b, t1)
    e.clear(result)
    e.set_cell(result, 1)  # assume a >= b, clear if a < b
    e.set_cell(cont, 1)
    e.move_to(cont); e.emit('[')
    # If tmp_b == 0: b exhausted, a >= b (result already 1), stop
    compare_eq(e, tmp_b, 0, flag, t1)
    e.move_to(flag); e.emit('[')
    e.clear(cont)
    e.clear(flag); e.move_to(flag); e.emit(']')
    # If still going, check if tmp_a == 0: a exhausted first, a < b
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, tmp_a, 0, t1, MG_T4)
    e.move_to(t1); e.emit('[')
    e.clear(result)  # a < b
    e.clear(cont)
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(flag); e.move_to(flag); e.emit(']')
    # Decrement both (if still going)
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    e.dec(tmp_a); e.dec(tmp_b)
    e.clear(flag); e.move_to(flag); e.emit(']')
    e.move_to(cont); e.emit(']')


def _is_le(e, a_cell, b_cell, result):
    """Set result=1 if a_cell <= b_cell. Uses simultaneous decrement.

    Uses E_TMP1-E_TMP3 as workspace.
    """
    tmp_a = E_TMP1
    tmp_b = E_TMP2
    cont = E_TMP3
    flag = MG_T5
    t1 = MG_T6

    e.copy_to(a_cell, tmp_a, t1)
    e.copy_to(b_cell, tmp_b, t1)
    e.clear(result)
    e.set_cell(result, 1)  # assume a <= b, clear if a > b
    e.set_cell(cont, 1)
    e.move_to(cont); e.emit('[')
    # If tmp_a == 0: a exhausted, a <= b (result already 1), stop
    compare_eq(e, tmp_a, 0, flag, t1)
    e.move_to(flag); e.emit('[')
    e.clear(cont)
    e.clear(flag); e.move_to(flag); e.emit(']')
    # If still going, check if tmp_b == 0: b exhausted first, a > b
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, tmp_b, 0, t1, MG_T4)
    e.move_to(t1); e.emit('[')
    e.clear(result)  # a > b
    e.clear(cont)
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(flag); e.move_to(flag); e.emit(']')
    # Decrement both (if still going)
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    e.dec(tmp_a); e.dec(tmp_b)
    e.clear(flag); e.move_to(flag); e.emit(']')
    e.move_to(cont); e.emit(']')


# ===========================================================================
# Depth-3 helpers
# ===========================================================================

def _d3_save_state(e, tmp):
    """Save full game state (board + state cells) to D3_STATE_BASE."""
    for i in range(64):
        e.copy_to(BOARD_START + i, D3_STATE_BASE + i, tmp)
    e.copy_to(SIDE_TO_MOVE, D3_STATE_BASE + 64, tmp)
    e.copy_to(EP_FILE, D3_STATE_BASE + 65, tmp)
    e.copy_to(WHITE_KING_POS, D3_STATE_BASE + 66, tmp)
    e.copy_to(BLACK_KING_POS, D3_STATE_BASE + 67, tmp)
    e.copy_to(WK_CASTLE, D3_STATE_BASE + 68, tmp)
    e.copy_to(WQ_CASTLE, D3_STATE_BASE + 69, tmp)
    e.copy_to(BK_CASTLE, D3_STATE_BASE + 70, tmp)
    e.copy_to(BQ_CASTLE, D3_STATE_BASE + 71, tmp)


def _d3_restore_state(e, tmp):
    """Restore full game state from D3_STATE_BASE."""
    for i in range(64):
        e.copy_to(D3_STATE_BASE + i, BOARD_START + i, tmp)
    e.copy_to(D3_STATE_BASE + 64, SIDE_TO_MOVE, tmp)
    e.copy_to(D3_STATE_BASE + 65, EP_FILE, tmp)
    e.copy_to(D3_STATE_BASE + 66, WHITE_KING_POS, tmp)
    e.copy_to(D3_STATE_BASE + 67, BLACK_KING_POS, tmp)
    e.copy_to(D3_STATE_BASE + 68, WK_CASTLE, tmp)
    e.copy_to(D3_STATE_BASE + 69, WQ_CASTLE, tmp)
    e.copy_to(D3_STATE_BASE + 70, BK_CASTLE, tmp)
    e.copy_to(D3_STATE_BASE + 71, BQ_CASTLE, tmp)


def _is_d3_move_better(e, result):
    """Set result=1 if this depth-3 move is better than current best.

    Better means (MAXIMIZER):
    1. D3_OPP_RESULT > D3_BEST_SCORE (higher is better for us), OR
    2. D3_OPP_RESULT == D3_BEST_SCORE AND D3_OUR_SCORE > D3_BEST_OUR_SCORE (tiebreak)

    Uses D3_TMP1-3, E_TMP1-4 as workspace.
    """
    opp_copy = D3_TMP1
    best_copy = D3_TMP2
    cont = D3_TMP3
    tied = E_TMP1
    flag = E_TMP2
    t1 = E_TMP3
    t2 = E_TMP4

    e.clear(result)
    e.clear(tied)

    # Phase 1: compare D3_OPP_RESULT > D3_BEST_SCORE (maximizer: higher wins)
    e.copy_to(D3_OPP_RESULT, opp_copy, t1)
    e.copy_to(D3_BEST_SCORE, best_copy, t1)
    e.set_cell(cont, 1)
    e.move_to(cont); e.emit('[')

    # If opp_copy == 0: OPP exhausted → OPP <= BEST, check tie
    compare_eq(e, opp_copy, 0, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, best_copy, 0, t1, t2)
    e.move_to(t1); e.emit('[')
    e.set_cell(tied, 1)  # both zero: tied
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(cont)
    e.clear(flag); e.move_to(flag); e.emit(']')

    # If still going, check if best_copy == 0: BEST exhausted → OPP > BEST
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, best_copy, 0, t1, t2)
    e.move_to(t1); e.emit('[')
    e.set_cell(result, 1)  # OPP > BEST: strictly better
    e.clear(cont)
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(flag); e.move_to(flag); e.emit(']')

    # Decrement both (if still going)
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    e.dec(opp_copy); e.dec(best_copy)
    e.clear(flag); e.move_to(flag); e.emit(']')

    e.move_to(cont); e.emit(']')

    # Phase 2: if tied on opp_score, use our_score as tiebreaker (higher wins)
    e.move_to(tied); e.emit('[')
    e.copy_to(D3_OUR_SCORE, opp_copy, t1)       # reuse as our_score copy
    e.copy_to(D3_BEST_OUR_SCORE, best_copy, t1)  # reuse as best_our copy
    e.set_cell(cont, 1)
    e.move_to(cont); e.emit('[')
    # If our_copy == 0: exhausted → OUR <= BEST_OUR, stop
    compare_eq(e, opp_copy, 0, flag, t1)
    e.move_to(flag); e.emit('[')
    e.clear(cont)
    e.clear(flag); e.move_to(flag); e.emit(']')
    # If still going, check if best_copy == 0: OUR > BEST_OUR
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    compare_eq(e, best_copy, 0, t1, t2)
    e.move_to(t1); e.emit('[')
    e.set_cell(result, 1)  # OUR > BEST_OUR: tiebreak winner
    e.clear(cont)
    e.clear(t1); e.move_to(t1); e.emit(']')
    e.clear(flag); e.move_to(flag); e.emit(']')
    # Decrement both
    e.copy_to(cont, flag, t1)
    e.move_to(flag); e.emit('[')
    e.dec(opp_copy); e.dec(best_copy)
    e.clear(flag); e.move_to(flag); e.emit(']')
    e.move_to(cont); e.emit(']')

    e.clear(tied); e.move_to(tied); e.emit(']')


def generate_legal_move_depth2(e):
    """Depth-2 minimax search.

    For each legal move at depth 1:
      - Saves full state, applies move with all state updates
      - Runs inner generate_legal_move (opponent's best reply)
      - Picks the outer move where opponent scores LOWEST (minimax)

    Sets HAVE_LEGAL=1 and BEST_FROM/BEST_TO with the best depth-2 move.
    """

    # === Save pristine game state ===
    _d2_save_state(e, L_TMP1)

    # === Initialize depth-2 tracking ===
    e.set_cell(D2_BEST_SCORE, 255)  # worst: opponent has max score
    e.clear(D2_BEST_OUR_SCORE)
    e.clear(D2_CAND_FROM)
    e.clear(D2_CAND_TO)
    e.clear(D2_HAVE_LEGAL)

    # === Initialize outer loop (same as generate_legal_move) ===
    e.clear(SKIP_COUNT)
    e.clear(FOUND_LEGAL)
    e.set_cell(GATE_WK, 1)
    e.set_cell(GATE_WQ, 1)
    e.set_cell(GATE_BK, 1)
    e.set_cell(GATE_BQ, 1)

    _check_in_check_direct(e)

    e.set_cell(RETRY_CONT, 1)
    e.move_to(RETRY_CONT)
    e.emit('[')

    # Save SKIP_COUNT (generate_moves consumes it)
    e.copy_to(SKIP_COUNT, SAVED_SKIP, L_TMP1)

    # Generate the (SKIP_COUNT+1)-th pseudo-legal move
    generate_moves(e)

    # Restore SKIP_COUNT
    e.copy_to(SAVED_SKIP, SKIP_COUNT, L_TMP1)

    # If no pseudo-legal move found, stop
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
    e.clear(RETRY_CONT)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    # If HAVE_LEGAL==1, test legality
    e.copy_to(HAVE_LEGAL, L_TMP1, L_TMP2)
    e.move_to(L_TMP1)
    e.emit('[')

    # === MAKE MOVE (same as generate_legal_move) ===
    _fast_read_board(e, BEST_TO, SAVED_CAPTURE)
    _fast_read_board(e, BEST_FROM, SAVED_PIECE)

    # Detect special moves (castling + EP)
    e.clear(IS_CASTLE_MOVE)
    e.clear(IS_EP_MOVE)
    e.clear(EP_CAPTURE_SQ)
    e.clear(SAVED_EP_PAWN)

    # White castling
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 4, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Black castling
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 60, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 62, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # White EP
    compare_eq(e, SAVED_PIECE, WHITE_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, SAVED_CAPTURE, EMPTY, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(EP_FILE, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.copy_to(EP_FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 39)
    e.copy_to(BEST_TO, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.dec(MG_T1); e.dec(MG_T2)
    e.move_to(MG_T2); e.emit(']')
    compare_eq(e, MG_T1, 0, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.set_cell(IS_EP_MOVE, 1)
    e.copy_to(EP_FILE, EP_CAPTURE_SQ, MG_T3)
    e.inc(EP_CAPTURE_SQ, 31)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.clear(MG_T1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Black EP
    compare_eq(e, SAVED_PIECE, BLACK_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, SAVED_CAPTURE, EMPTY, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(EP_FILE, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.copy_to(EP_FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 15)
    e.copy_to(BEST_TO, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.dec(MG_T1); e.dec(MG_T2)
    e.move_to(MG_T2); e.emit(']')
    compare_eq(e, MG_T1, 0, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.set_cell(IS_EP_MOVE, 1)
    e.copy_to(EP_FILE, EP_CAPTURE_SQ, MG_T3)
    e.inc(EP_CAPTURE_SQ, 23)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.clear(MG_T1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Write piece to BEST_TO, clear BEST_FROM
    _fast_write_board(e, BEST_TO, SAVED_PIECE)
    e.clear(L_TMP2)
    _fast_write_board(e, BEST_FROM, L_TMP2)

    # Castling rook make
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 7, BOARD_START + 5, L_TMP1)
    e.clear(BOARD_START + 7)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 0, BOARD_START + 3, L_TMP1)
    e.clear(BOARD_START + 0)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 63, BOARD_START + 61, L_TMP1)
    e.clear(BOARD_START + 63)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 56, BOARD_START + 59, L_TMP1)
    e.clear(BOARD_START + 56)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # EP capture make
    e.copy_to(IS_EP_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, EP_CAPTURE_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.copy_to(BOARD_START + capture_sq, SAVED_EP_PAWN, L_TMP1)
            e.clear(BOARD_START + capture_sq)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # King position update
    e.clear(SAVED_KING)
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(WHITE_KING_POS, SAVED_KING, L_TMP3)
    e.copy_to(BEST_TO, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(BLACK_KING_POS, SAVED_KING, L_TMP3)
    e.copy_to(BEST_TO, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Set KING_SQ for our king
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(L_TMP3); e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(WHITE_KING_POS, KING_SQ, L_TMP2)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(BLACK_KING_POS, KING_SQ, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === CASTLE GATE CHECK (same as generate_legal_move) ===
    e.clear(ATTACKED)
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_WK, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_WQ, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_BK, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_BQ, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Block castling if in check
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(IN_CHECK, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === 1-PASS ATTACK CHECK (king legality only) ===
    compare_eq(e, ATTACKED, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(ATTACKED)
    is_attacked(e)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === UNMAKE MOVE ===
    _fast_write_board(e, BEST_FROM, SAVED_PIECE)
    _fast_write_board(e, BEST_TO, SAVED_CAPTURE)

    # Castling rook unmake
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 5, BOARD_START + 7, L_TMP1)
    e.clear(BOARD_START + 5)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 3, BOARD_START + 0, L_TMP1)
    e.clear(BOARD_START + 3)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 61, BOARD_START + 63, L_TMP1)
    e.clear(BOARD_START + 61)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 59, BOARD_START + 56, L_TMP1)
    e.clear(BOARD_START + 59)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # EP capture unmake
    e.copy_to(IS_EP_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, EP_CAPTURE_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.copy_to(SAVED_EP_PAWN, BOARD_START + capture_sq, L_TMP1)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Restore king pos
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(SAVED_KING, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(SAVED_KING, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === CHECK RESULT ===
    e.copy_to(ATTACKED, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(L_TMP3); e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')
    # === LEGAL MOVE FOUND — DEPTH-2 EVALUATION ===

    # 0. Score our move (depth-1 evaluation for tiebreaking)
    _score_move(e)
    e.copy_to(MOVE_SCORE, D2_OUR_SCORE, L_TMP2)

    # 1. Save outer-loop cells to D2_SAVED_*
    e.copy_to(SKIP_COUNT, D2_SAVED_SKIP, L_TMP2)
    e.copy_to(RETRY_CONT, D2_SAVED_RETRY, L_TMP2)
    e.copy_to(BEST_FROM, D2_SAVED_BEST_FROM, L_TMP2)
    e.copy_to(BEST_TO, D2_SAVED_BEST_TO, L_TMP2)
    e.copy_to(SAVED_PIECE, D2_SAVED_PIECE, L_TMP2)
    e.copy_to(SAVED_CAPTURE, D2_SAVED_CAPTURE, L_TMP2)
    e.copy_to(SAVED_KING, D2_SAVED_KING, L_TMP2)
    e.copy_to(IS_CASTLE_MOVE, D2_SAVED_IS_CASTLE, L_TMP2)
    e.copy_to(IS_EP_MOVE, D2_SAVED_IS_EP, L_TMP2)
    e.copy_to(EP_CAPTURE_SQ, D2_SAVED_EP_CAP_SQ, L_TMP2)
    e.copy_to(SAVED_EP_PAWN, D2_SAVED_EP_PAWN, L_TMP2)
    e.copy_to(GATE_WK, D2_SAVED_GATE_WK, L_TMP2)
    e.copy_to(GATE_WQ, D2_SAVED_GATE_WQ, L_TMP2)
    e.copy_to(GATE_BK, D2_SAVED_GATE_BK, L_TMP2)
    e.copy_to(GATE_BQ, D2_SAVED_GATE_BQ, L_TMP2)
    e.copy_to(IN_CHECK, D2_SAVED_IN_CHECK, L_TMP2)

    # 2. Restore pristine state from D2_STATE_BASE
    _d2_restore_state(e, L_TMP2)

    # 3. Apply move WITH full state updates
    # Write piece to destination
    _fast_write_board(e, D2_SAVED_BEST_TO, D2_SAVED_PIECE)
    # Clear source square
    e.clear(L_TMP2)
    _fast_write_board(e, D2_SAVED_BEST_FROM, L_TMP2)

    # Castling rook move (4-way switch on dest square)
    e.copy_to(D2_SAVED_IS_CASTLE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, D2_SAVED_BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 7, BOARD_START + 5, L_TMP1)
    e.clear(BOARD_START + 7)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 0, BOARD_START + 3, L_TMP1)
    e.clear(BOARD_START + 0)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 63, BOARD_START + 61, L_TMP1)
    e.clear(BOARD_START + 63)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 56, BOARD_START + 59, L_TMP1)
    e.clear(BOARD_START + 56)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # EP capture (clear captured pawn)
    e.copy_to(D2_SAVED_IS_EP, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, D2_SAVED_EP_CAP_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.clear(BOARD_START + capture_sq)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # King position update
    compare_eq(e, D2_SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(D2_SAVED_BEST_TO, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(D2_SAVED_BEST_TO, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Promotion: pawn on last rank → queen
    compare_eq(e, D2_SAVED_PIECE, WHITE_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for sq in range(56, 64):
        compare_eq(e, D2_SAVED_BEST_TO, sq, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        e.set_cell(BOARD_START + sq, WHITE_QUEEN)
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_PIECE, BLACK_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for sq in range(0, 8):
        compare_eq(e, D2_SAVED_BEST_TO, sq, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        e.set_cell(BOARD_START + sq, BLACK_QUEEN)
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Flip SIDE_TO_MOVE
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)  # else flag
    e.move_to(L_TMP2); e.emit('[')  # if STM != 0 (black)
    e.clear(L_TMP3)
    e.clear(SIDE_TO_MOVE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')  # else: STM was 0 (white)
    e.set_cell(SIDE_TO_MOVE, 1)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')

    # Update EP_FILE
    e.clear(EP_FILE)
    # White pawn double push: from=8+f, to=24+f → EP_FILE=f+1
    compare_eq(e, D2_SAVED_PIECE, WHITE_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        compare_eq(e, D2_SAVED_BEST_FROM, 8 + f, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        compare_eq(e, D2_SAVED_BEST_TO, 24 + f, L_TMP1, MG_T1)
        e.move_to(L_TMP1); e.emit('[')
        e.set_cell(EP_FILE, f + 1)
        e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    # Black pawn double push: from=48+f, to=32+f → EP_FILE=f+1
    compare_eq(e, D2_SAVED_PIECE, BLACK_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        compare_eq(e, D2_SAVED_BEST_FROM, 48 + f, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        compare_eq(e, D2_SAVED_BEST_TO, 32 + f, L_TMP1, MG_T1)
        e.move_to(L_TMP1); e.emit('[')
        e.set_cell(EP_FILE, f + 1)
        e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Update castling rights based on FROM square
    compare_eq(e, D2_SAVED_BEST_FROM, 4, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WK_CASTLE); e.clear(WQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_FROM, 60, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BK_CASTLE); e.clear(BQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_FROM, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_FROM, 7, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_FROM, 56, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_FROM, 63, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    # Castling rights based on TO square (rook captures)
    compare_eq(e, D2_SAVED_BEST_TO, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_TO, 7, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_TO, 56, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D2_SAVED_BEST_TO, 63, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # 4. Run inner search (opponent's best move)
    # Propagate beta bound: tell inner search to stop if score >= D2_BEST_SCORE
    e.copy_to(D2_BEST_SCORE, BETA_CUTOFF, L_TMP2)
    generate_legal_move(e)

    # 5. Capture opponent's score
    # BEST_SCORE=0 means no legal moves (checkmate/stalemate)
    e.copy_to(BEST_SCORE, D2_OPP_SCORE, L_TMP2)

    # 5a. Stalemate detection: HAVE_LEGAL==0 AND IN_CHECK==0 → stalemate (draw)
    # IN_CHECK was set by inner search's _check_in_check_direct()
    # Checkmate (IN_CHECK==1): keep D2_OPP_SCORE=0 (best for us)
    # Stalemate (IN_CHECK==0): set D2_OPP_SCORE=128 (draw/neutral)
    compare_eq(e, HAVE_LEGAL, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, IN_CHECK, 0, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.clear(D2_OPP_SCORE)
    e.set_cell(D2_OPP_SCORE, 128)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # 6. Restore pristine state
    _d2_restore_state(e, L_TMP2)

    # 7. Restore outer-loop cells
    e.copy_to(D2_SAVED_SKIP, SKIP_COUNT, L_TMP2)
    e.copy_to(D2_SAVED_RETRY, RETRY_CONT, L_TMP2)
    e.copy_to(D2_SAVED_BEST_FROM, BEST_FROM, L_TMP2)
    e.copy_to(D2_SAVED_BEST_TO, BEST_TO, L_TMP2)
    e.copy_to(D2_SAVED_PIECE, SAVED_PIECE, L_TMP2)
    e.copy_to(D2_SAVED_CAPTURE, SAVED_CAPTURE, L_TMP2)
    e.copy_to(D2_SAVED_KING, SAVED_KING, L_TMP2)
    e.copy_to(D2_SAVED_IS_CASTLE, IS_CASTLE_MOVE, L_TMP2)
    e.copy_to(D2_SAVED_IS_EP, IS_EP_MOVE, L_TMP2)
    e.copy_to(D2_SAVED_EP_CAP_SQ, EP_CAPTURE_SQ, L_TMP2)
    e.copy_to(D2_SAVED_EP_PAWN, SAVED_EP_PAWN, L_TMP2)
    e.copy_to(D2_SAVED_GATE_WK, GATE_WK, L_TMP2)
    e.copy_to(D2_SAVED_GATE_WQ, GATE_WQ, L_TMP2)
    e.copy_to(D2_SAVED_GATE_BK, GATE_BK, L_TMP2)
    e.copy_to(D2_SAVED_GATE_BQ, GATE_BQ, L_TMP2)
    e.copy_to(D2_SAVED_IN_CHECK, IN_CHECK, L_TMP2)

    # 8. Minimax compare: lower opp score wins, ties broken by our score
    # First legal move: always accept
    compare_eq(e, D2_HAVE_LEGAL, 0, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)  # else flag
    e.move_to(L_TMP2); e.emit('[')
    e.clear(L_TMP3)
    # First legal move: update D2 best
    e.copy_to(D2_OPP_SCORE, D2_BEST_SCORE, L_TMP1)
    e.copy_to(D2_OUR_SCORE, D2_BEST_OUR_SCORE, L_TMP1)
    e.copy_to(BEST_FROM, D2_CAND_FROM, L_TMP1)
    e.copy_to(BEST_TO, D2_CAND_TO, L_TMP1)
    e.set_cell(D2_HAVE_LEGAL, 1)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')
    # Not first: compare (opp_score, our_score) vs (best_opp, best_our)
    _is_d2_move_better(e, L_TMP2)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(D2_OPP_SCORE, D2_BEST_SCORE, L_TMP1)
    e.copy_to(D2_OUR_SCORE, D2_BEST_OUR_SCORE, L_TMP1)
    e.copy_to(BEST_FROM, D2_CAND_FROM, L_TMP1)
    e.copy_to(BEST_TO, D2_CAND_TO, L_TMP1)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')

    # Alpha cutoff: if D2_BEST_SCORE <= D2_ALPHA, prune remaining moves
    _is_le(e, D2_BEST_SCORE, D2_ALPHA, D2_TMP3)
    e.move_to(D2_TMP3); e.emit('[')
    e.clear(RETRY_CONT)
    e.clear(D2_TMP3); e.move_to(D2_TMP3); e.emit(']')

    # 9. Next move
    e.inc(SKIP_COUNT)

    e.clear(L_TMP3)
    e.move_to(L_TMP3)
    e.emit(']')  # end "not attacked" (legal) branch

    # If attacked: update gate flags and try next
    e.copy_to(ATTACKED, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 4, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 5, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_WK)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 3, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_WQ)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_FROM, 60, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 61, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_BK)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 59, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_BQ)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.inc(SKIP_COUNT)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    e.clear(L_TMP1)
    e.move_to(L_TMP1)
    e.emit(']')  # end HAVE_LEGAL check

    e.move_to(RETRY_CONT)
    e.emit(']')  # end retry loop

    # === Finalize: output best depth-2 move ===
    e.clear(HAVE_LEGAL)
    e.copy_to(D2_HAVE_LEGAL, L_TMP1, L_TMP2)
    e.move_to(L_TMP1); e.emit('[')
    e.copy_to(D2_CAND_FROM, BEST_FROM, L_TMP2)
    e.copy_to(D2_CAND_TO, BEST_TO, L_TMP2)
    # Save last move for anti-repetition
    e.copy_to(D2_CAND_FROM, LAST_FROM, L_TMP2)
    e.copy_to(D2_CAND_TO, LAST_TO, L_TMP2)
    e.set_cell(HAVE_LEGAL, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')


# ===========================================================================
# Depth-3 minimax search (maximizer)
# ===========================================================================

def generate_legal_move_depth3(e):
    """Depth-3 minimax search (maximizer).

    For each legal move at depth 1 (our move):
      - Saves full state, applies move with all state updates
      - Runs generate_legal_move_depth2 (opponent's best reply = minimizer)
      - Picks the outer move where D2_BEST_SCORE is HIGHEST (best for us)

    Sets HAVE_LEGAL=1 and BEST_FROM/BEST_TO with the best depth-3 move.
    """

    # === Save pristine game state ===
    _d3_save_state(e, L_TMP1)

    # === Initialize depth-3 tracking ===
    e.clear(D3_BEST_SCORE)           # worst: 0 (maximize: higher is better)
    e.clear(D3_BEST_OUR_SCORE)
    e.clear(D3_CAND_FROM)
    e.clear(D3_CAND_TO)
    e.clear(D3_HAVE_LEGAL)

    # === Initialize outer loop (same as generate_legal_move) ===
    e.clear(SKIP_COUNT)
    e.clear(FOUND_LEGAL)
    e.set_cell(GATE_WK, 1)
    e.set_cell(GATE_WQ, 1)
    e.set_cell(GATE_BK, 1)
    e.set_cell(GATE_BQ, 1)

    _check_in_check_direct(e)

    e.set_cell(RETRY_CONT, 1)
    e.move_to(RETRY_CONT)
    e.emit('[')

    # Save SKIP_COUNT (generate_moves consumes it)
    e.copy_to(SKIP_COUNT, SAVED_SKIP, L_TMP1)

    # Generate the (SKIP_COUNT+1)-th pseudo-legal move
    generate_moves(e)

    # Restore SKIP_COUNT
    e.copy_to(SAVED_SKIP, SKIP_COUNT, L_TMP1)

    # If no pseudo-legal move found, stop
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
    e.clear(RETRY_CONT)
    e.clear(L_TMP2)
    e.move_to(L_TMP2)
    e.emit(']')

    # If HAVE_LEGAL==1, test legality
    e.copy_to(HAVE_LEGAL, L_TMP1, L_TMP2)
    e.move_to(L_TMP1)
    e.emit('[')

    # === MAKE MOVE (same as depth-2 outer) ===
    _fast_read_board(e, BEST_TO, SAVED_CAPTURE)
    _fast_read_board(e, BEST_FROM, SAVED_PIECE)

    # Detect special moves (castling + EP)
    e.clear(IS_CASTLE_MOVE)
    e.clear(IS_EP_MOVE)
    e.clear(EP_CAPTURE_SQ)
    e.clear(SAVED_EP_PAWN)

    # White castling
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 4, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Black castling
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 60, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 62, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(IS_CASTLE_MOVE, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # White EP
    compare_eq(e, SAVED_PIECE, WHITE_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, SAVED_CAPTURE, EMPTY, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(EP_FILE, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.copy_to(EP_FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 39)
    e.copy_to(BEST_TO, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.dec(MG_T1); e.dec(MG_T2)
    e.move_to(MG_T2); e.emit(']')
    compare_eq(e, MG_T1, 0, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.set_cell(IS_EP_MOVE, 1)
    e.copy_to(EP_FILE, EP_CAPTURE_SQ, MG_T3)
    e.inc(EP_CAPTURE_SQ, 31)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.clear(MG_T1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Black EP
    compare_eq(e, SAVED_PIECE, BLACK_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, SAVED_CAPTURE, EMPTY, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(EP_FILE, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.copy_to(EP_FILE, MG_T1, MG_T2)
    e.inc(MG_T1, 15)
    e.copy_to(BEST_TO, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.dec(MG_T1); e.dec(MG_T2)
    e.move_to(MG_T2); e.emit(']')
    compare_eq(e, MG_T1, 0, MG_T2, MG_T3)
    e.move_to(MG_T2); e.emit('[')
    e.set_cell(IS_EP_MOVE, 1)
    e.copy_to(EP_FILE, EP_CAPTURE_SQ, MG_T3)
    e.inc(EP_CAPTURE_SQ, 23)
    e.clear(MG_T2); e.move_to(MG_T2); e.emit(']')
    e.clear(MG_T1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Write piece to BEST_TO, clear BEST_FROM
    _fast_write_board(e, BEST_TO, SAVED_PIECE)
    e.clear(L_TMP2)
    _fast_write_board(e, BEST_FROM, L_TMP2)

    # Castling rook make
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 7, BOARD_START + 5, L_TMP1)
    e.clear(BOARD_START + 7)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 0, BOARD_START + 3, L_TMP1)
    e.clear(BOARD_START + 0)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 63, BOARD_START + 61, L_TMP1)
    e.clear(BOARD_START + 63)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 56, BOARD_START + 59, L_TMP1)
    e.clear(BOARD_START + 56)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # EP capture make
    e.copy_to(IS_EP_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, EP_CAPTURE_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.copy_to(BOARD_START + capture_sq, SAVED_EP_PAWN, L_TMP1)
            e.clear(BOARD_START + capture_sq)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # King position update
    e.clear(SAVED_KING)
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(WHITE_KING_POS, SAVED_KING, L_TMP3)
    e.copy_to(BEST_TO, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(BLACK_KING_POS, SAVED_KING, L_TMP3)
    e.copy_to(BEST_TO, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Set KING_SQ for our king
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(L_TMP3); e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(WHITE_KING_POS, KING_SQ, L_TMP2)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(BLACK_KING_POS, KING_SQ, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === CASTLE GATE CHECK ===
    e.clear(ATTACKED)
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_WK, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_WQ, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_BK, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, GATE_BQ, 0, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Block castling if in check
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(IN_CHECK, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.set_cell(ATTACKED, 1)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === 1-PASS ATTACK CHECK (king legality only) ===
    compare_eq(e, ATTACKED, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(ATTACKED)
    is_attacked(e)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === UNMAKE MOVE ===
    _fast_write_board(e, BEST_FROM, SAVED_PIECE)
    _fast_write_board(e, BEST_TO, SAVED_CAPTURE)

    # Castling rook unmake
    e.copy_to(IS_CASTLE_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 5, BOARD_START + 7, L_TMP1)
    e.clear(BOARD_START + 5)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 3, BOARD_START + 0, L_TMP1)
    e.clear(BOARD_START + 3)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 61, BOARD_START + 63, L_TMP1)
    e.clear(BOARD_START + 61)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 59, BOARD_START + 56, L_TMP1)
    e.clear(BOARD_START + 59)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # EP capture unmake
    e.copy_to(IS_EP_MOVE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, EP_CAPTURE_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.copy_to(SAVED_EP_PAWN, BOARD_START + capture_sq, L_TMP1)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Restore king pos
    compare_eq(e, SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(SAVED_KING, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(SAVED_KING, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # === CHECK RESULT ===
    e.copy_to(ATTACKED, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(L_TMP3); e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')
    # === LEGAL MOVE FOUND — DEPTH-3 EVALUATION ===

    # 0. Score our move (depth-1 evaluation for tiebreaking)
    _score_move(e)
    e.copy_to(MOVE_SCORE, D3_OUR_SCORE, L_TMP2)

    # 1. Save outer-loop cells to D3_SAVED_*
    e.copy_to(SKIP_COUNT, D3_SAVED_SKIP, L_TMP2)
    e.copy_to(RETRY_CONT, D3_SAVED_RETRY, L_TMP2)
    e.copy_to(BEST_FROM, D3_SAVED_BEST_FROM, L_TMP2)
    e.copy_to(BEST_TO, D3_SAVED_BEST_TO, L_TMP2)
    e.copy_to(SAVED_PIECE, D3_SAVED_PIECE, L_TMP2)
    e.copy_to(SAVED_CAPTURE, D3_SAVED_CAPTURE, L_TMP2)
    e.copy_to(SAVED_KING, D3_SAVED_KING, L_TMP2)
    e.copy_to(IS_CASTLE_MOVE, D3_SAVED_IS_CASTLE, L_TMP2)
    e.copy_to(IS_EP_MOVE, D3_SAVED_IS_EP, L_TMP2)
    e.copy_to(EP_CAPTURE_SQ, D3_SAVED_EP_CAP_SQ, L_TMP2)
    e.copy_to(SAVED_EP_PAWN, D3_SAVED_EP_PAWN, L_TMP2)
    e.copy_to(GATE_WK, D3_SAVED_GATE_WK, L_TMP2)
    e.copy_to(GATE_WQ, D3_SAVED_GATE_WQ, L_TMP2)
    e.copy_to(GATE_BK, D3_SAVED_GATE_BK, L_TMP2)
    e.copy_to(GATE_BQ, D3_SAVED_GATE_BQ, L_TMP2)
    e.copy_to(IN_CHECK, D3_SAVED_IN_CHECK, L_TMP2)

    # Save D2 tracking cells (overwritten when depth-2 runs)
    e.copy_to(D2_BEST_SCORE, D3_SAVED_D2_BEST, L_TMP2)
    e.copy_to(D2_CAND_FROM, D3_SAVED_D2_CAND_FROM, L_TMP2)
    e.copy_to(D2_CAND_TO, D3_SAVED_D2_CAND_TO, L_TMP2)
    e.copy_to(D2_HAVE_LEGAL, D3_SAVED_D2_HAVE_LEGAL, L_TMP2)
    e.copy_to(D2_BEST_OUR_SCORE, D3_SAVED_D2_BEST_OUR, L_TMP2)

    # 2. Restore pristine state from D3_STATE_BASE
    _d3_restore_state(e, L_TMP2)

    # 3. Apply move WITH full state updates (same as depth-2)
    # Write piece to destination
    _fast_write_board(e, D3_SAVED_BEST_TO, D3_SAVED_PIECE)
    # Clear source square
    e.clear(L_TMP2)
    _fast_write_board(e, D3_SAVED_BEST_FROM, L_TMP2)

    # Castling rook move
    e.copy_to(D3_SAVED_IS_CASTLE, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, D3_SAVED_BEST_TO, 6, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 7, BOARD_START + 5, L_TMP1)
    e.clear(BOARD_START + 7)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_TO, 2, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 0, BOARD_START + 3, L_TMP1)
    e.clear(BOARD_START + 0)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_TO, 62, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 63, BOARD_START + 61, L_TMP1)
    e.clear(BOARD_START + 63)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_TO, 58, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.copy_to(BOARD_START + 56, BOARD_START + 59, L_TMP1)
    e.clear(BOARD_START + 56)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # EP capture (clear captured pawn)
    e.copy_to(D3_SAVED_IS_EP, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        for capture_sq in [32 + f, 24 + f]:
            compare_eq(e, D3_SAVED_EP_CAP_SQ, capture_sq, L_TMP3, L_TMP1)
            e.move_to(L_TMP3); e.emit('[')
            e.clear(BOARD_START + capture_sq)
            e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # King position update
    compare_eq(e, D3_SAVED_PIECE, WHITE_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(D3_SAVED_BEST_TO, WHITE_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_PIECE, BLACK_KING, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(D3_SAVED_BEST_TO, BLACK_KING_POS, L_TMP3)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Promotion: pawn on last rank → queen
    compare_eq(e, D3_SAVED_PIECE, WHITE_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for sq in range(56, 64):
        compare_eq(e, D3_SAVED_BEST_TO, sq, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        e.set_cell(BOARD_START + sq, WHITE_QUEEN)
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_PIECE, BLACK_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for sq in range(0, 8):
        compare_eq(e, D3_SAVED_BEST_TO, sq, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        e.set_cell(BOARD_START + sq, BLACK_QUEEN)
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Flip SIDE_TO_MOVE
    e.copy_to(SIDE_TO_MOVE, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)  # else flag
    e.move_to(L_TMP2); e.emit('[')  # if STM != 0 (black)
    e.clear(L_TMP3)
    e.clear(SIDE_TO_MOVE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')  # else: STM was 0 (white)
    e.set_cell(SIDE_TO_MOVE, 1)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')

    # Update EP_FILE
    e.clear(EP_FILE)
    # White pawn double push: from=8+f, to=24+f → EP_FILE=f+1
    compare_eq(e, D3_SAVED_PIECE, WHITE_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        compare_eq(e, D3_SAVED_BEST_FROM, 8 + f, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        compare_eq(e, D3_SAVED_BEST_TO, 24 + f, L_TMP1, MG_T1)
        e.move_to(L_TMP1); e.emit('[')
        e.set_cell(EP_FILE, f + 1)
        e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    # Black pawn double push: from=48+f, to=32+f → EP_FILE=f+1
    compare_eq(e, D3_SAVED_PIECE, BLACK_PAWN, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    for f in range(8):
        compare_eq(e, D3_SAVED_BEST_FROM, 48 + f, L_TMP3, L_TMP1)
        e.move_to(L_TMP3); e.emit('[')
        compare_eq(e, D3_SAVED_BEST_TO, 32 + f, L_TMP1, MG_T1)
        e.move_to(L_TMP1); e.emit('[')
        e.set_cell(EP_FILE, f + 1)
        e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
        e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # Update castling rights based on FROM square
    compare_eq(e, D3_SAVED_BEST_FROM, 4, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WK_CASTLE); e.clear(WQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_FROM, 60, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BK_CASTLE); e.clear(BQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_FROM, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_FROM, 7, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_FROM, 56, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_FROM, 63, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    # Castling rights based on TO square (rook captures)
    compare_eq(e, D3_SAVED_BEST_TO, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_TO, 7, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(WK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_TO, 56, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BQ_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    compare_eq(e, D3_SAVED_BEST_TO, 63, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    e.clear(BK_CASTLE)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # 4. Run depth-2 search (opponent's best reply)
    # Set alpha bound: don't bother if opponent can already force worse than our best
    e.copy_to(D3_BEST_SCORE, D2_ALPHA, L_TMP2)
    # Set beta cutoff high so depth-2's own internal beta starts at 255
    e.set_cell(BETA_CUTOFF, 255)
    generate_legal_move_depth2(e)

    # 5. Capture result: D2_BEST_SCORE = opponent's minimax score
    # If D2_HAVE_LEGAL==0, opponent has no legal moves → D2_BEST_SCORE stays at 255
    e.copy_to(D2_BEST_SCORE, D3_OPP_RESULT, L_TMP2)

    # 5a. Stalemate detection at depth-2: D2_HAVE_LEGAL==0 AND IN_CHECK==0
    # IN_CHECK still reflects the depth-2 position (set by depth-2's _check_in_check_direct)
    # Checkmate (IN_CHECK==1): keep D3_OPP_RESULT=255 (best for us)
    # Stalemate (IN_CHECK==0): set D3_OPP_RESULT=128 (draw/neutral)
    compare_eq(e, D2_HAVE_LEGAL, 0, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, IN_CHECK, 0, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    e.clear(D3_OPP_RESULT)
    e.set_cell(D3_OPP_RESULT, 128)
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    # 6. Restore pristine state
    _d3_restore_state(e, L_TMP2)

    # 7. Restore outer-loop cells
    e.copy_to(D3_SAVED_SKIP, SKIP_COUNT, L_TMP2)
    e.copy_to(D3_SAVED_RETRY, RETRY_CONT, L_TMP2)
    e.copy_to(D3_SAVED_BEST_FROM, BEST_FROM, L_TMP2)
    e.copy_to(D3_SAVED_BEST_TO, BEST_TO, L_TMP2)
    e.copy_to(D3_SAVED_PIECE, SAVED_PIECE, L_TMP2)
    e.copy_to(D3_SAVED_CAPTURE, SAVED_CAPTURE, L_TMP2)
    e.copy_to(D3_SAVED_KING, SAVED_KING, L_TMP2)
    e.copy_to(D3_SAVED_IS_CASTLE, IS_CASTLE_MOVE, L_TMP2)
    e.copy_to(D3_SAVED_IS_EP, IS_EP_MOVE, L_TMP2)
    e.copy_to(D3_SAVED_EP_CAP_SQ, EP_CAPTURE_SQ, L_TMP2)
    e.copy_to(D3_SAVED_EP_PAWN, SAVED_EP_PAWN, L_TMP2)
    e.copy_to(D3_SAVED_GATE_WK, GATE_WK, L_TMP2)
    e.copy_to(D3_SAVED_GATE_WQ, GATE_WQ, L_TMP2)
    e.copy_to(D3_SAVED_GATE_BK, GATE_BK, L_TMP2)
    e.copy_to(D3_SAVED_GATE_BQ, GATE_BQ, L_TMP2)
    e.copy_to(D3_SAVED_IN_CHECK, IN_CHECK, L_TMP2)

    # Restore D2 tracking cells
    e.copy_to(D3_SAVED_D2_BEST, D2_BEST_SCORE, L_TMP2)
    e.copy_to(D3_SAVED_D2_CAND_FROM, D2_CAND_FROM, L_TMP2)
    e.copy_to(D3_SAVED_D2_CAND_TO, D2_CAND_TO, L_TMP2)
    e.copy_to(D3_SAVED_D2_HAVE_LEGAL, D2_HAVE_LEGAL, L_TMP2)
    e.copy_to(D3_SAVED_D2_BEST_OUR, D2_BEST_OUR_SCORE, L_TMP2)

    # 8. Maximizer compare: higher D3_OPP_RESULT is better for us
    # First legal move: always accept
    compare_eq(e, D3_HAVE_LEGAL, 0, L_TMP2, L_TMP3)
    e.set_cell(L_TMP3, 1)  # else flag
    e.move_to(L_TMP2); e.emit('[')
    e.clear(L_TMP3)
    # First legal move: update D3 best
    e.copy_to(D3_OPP_RESULT, D3_BEST_SCORE, L_TMP1)
    e.copy_to(D3_OUR_SCORE, D3_BEST_OUR_SCORE, L_TMP1)
    e.copy_to(BEST_FROM, D3_CAND_FROM, L_TMP1)
    e.copy_to(BEST_TO, D3_CAND_TO, L_TMP1)
    e.set_cell(D3_HAVE_LEGAL, 1)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.move_to(L_TMP3); e.emit('[')
    # Not first: compare (maximizer)
    _is_d3_move_better(e, L_TMP2)
    e.move_to(L_TMP2); e.emit('[')
    e.copy_to(D3_OPP_RESULT, D3_BEST_SCORE, L_TMP1)
    e.copy_to(D3_OUR_SCORE, D3_BEST_OUR_SCORE, L_TMP1)
    e.copy_to(BEST_FROM, D3_CAND_FROM, L_TMP1)
    e.copy_to(BEST_TO, D3_CAND_TO, L_TMP1)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')

    # 9. Next move
    e.inc(SKIP_COUNT)

    e.clear(L_TMP3)
    e.move_to(L_TMP3)
    e.emit(']')  # end "not attacked" (legal) branch

    # If attacked: update gate flags and try next
    e.copy_to(ATTACKED, L_TMP2, L_TMP3)
    e.move_to(L_TMP2); e.emit('[')
    compare_eq(e, BEST_FROM, 4, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 5, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_WK)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 3, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_WQ)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    compare_eq(e, BEST_FROM, 60, L_TMP3, L_TMP1)
    e.move_to(L_TMP3); e.emit('[')
    compare_eq(e, BEST_TO, 61, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_BK)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    compare_eq(e, BEST_TO, 59, L_TMP1, MG_T1)
    e.move_to(L_TMP1); e.emit('[')
    e.clear(GATE_BQ)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
    e.clear(L_TMP3); e.move_to(L_TMP3); e.emit(']')
    e.inc(SKIP_COUNT)
    e.clear(L_TMP2); e.move_to(L_TMP2); e.emit(']')

    e.clear(L_TMP1)
    e.move_to(L_TMP1)
    e.emit(']')  # end HAVE_LEGAL check

    e.move_to(RETRY_CONT)
    e.emit(']')  # end retry loop

    # === Finalize: output best depth-3 move ===
    e.clear(HAVE_LEGAL)
    e.copy_to(D3_HAVE_LEGAL, L_TMP1, L_TMP2)
    e.move_to(L_TMP1); e.emit('[')
    e.copy_to(D3_CAND_FROM, BEST_FROM, L_TMP2)
    e.copy_to(D3_CAND_TO, BEST_TO, L_TMP2)
    # Save last move for anti-repetition
    e.copy_to(D3_CAND_FROM, LAST_FROM, L_TMP2)
    e.copy_to(D3_CAND_TO, LAST_TO, L_TMP2)
    e.set_cell(HAVE_LEGAL, 1)
    e.clear(L_TMP1); e.move_to(L_TMP1); e.emit(']')
