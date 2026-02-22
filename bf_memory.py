"""
Memory layout constants for the BF chess engine.

COMPACT layout — all hot cells within 0-120 to minimize pointer movements.

Tape layout:
  Cells 0-15:     16 general-purpose temporaries
  Cells 16-22:    Game state
  Cells 23-28:    Movegen hot cells (BEST_FROM, BEST_TO, HAVE_LEGAL, etc.)
  Cells 30-93:    Chess board (64 squares, stride 1)
  Cells 94-99:    Extra temps for movegen
  Cells 100-227:  Input buffer (128 bytes)
  Cell 228:       INPUT_LEN
  Cells 230+:     Additional workspace (scratch, board copy, etc.)
"""

# === Temporaries (0-15) ===
TEMP = 0
TEMP_COUNT = 16

# === Game State (16-22) ===
SIDE_TO_MOVE = 16
CASTLING = 17
EP_FILE = 18
WHITE_KING_POS = 19
BLACK_KING_POS = 20
HALFMOVE = 21
FULLMOVE = 22

# === Movegen hot cells (23-28) ===
BEST_FROM = 23
BEST_TO = 24
HAVE_LEGAL = 25
MOVE_PROMO = 26
MG_PIECE = 27       # piece at current square during movegen
MG_TPIECE = 28      # piece at target square during movegen

# === Chess Board (30-93, stride 1) ===
BOARD_START = 30
BOARD_STRIDE = 1
BOARD_SIZE = 64

# === Extra temps for movegen (94-99) ===
MG_T1 = 94
MG_T2 = 95
MG_T3 = 96
MG_T4 = 97
MG_T5 = 98
MG_T6 = 99

# === Input Buffer (100-227) ===
INPUT_BUF = 100
INPUT_BUF_SIZE = 128
INPUT_LEN = 228

# === Scratch / workspace (230+) ===
SCRATCH = 230
SCRATCH2 = 231
SCRATCH3 = 232
SCRATCH4 = 233
MOVE_FROM = 234
MOVE_TO = 235
MOVE_PIECE = 236
MOVE_TARGET = 237

# For is_attacked / legality
KING_SQ = 240
ATTACKED = 241

# Board copy for make/unmake
BOARD_COPY = 250
BOARD_COPY_END = 314

# === Piece Encoding ===
EMPTY = 0
WHITE_PAWN = 1
WHITE_KNIGHT = 2
WHITE_BISHOP = 3
WHITE_ROOK = 4
WHITE_QUEEN = 5
WHITE_KING = 6
BLACK_PAWN = 7
BLACK_KNIGHT = 8
BLACK_BISHOP = 9
BLACK_ROOK = 10
BLACK_QUEEN = 11
BLACK_KING = 12

PIECE_NAMES = {
    0: '.',
    1: 'P', 2: 'N', 3: 'B', 4: 'R', 5: 'Q', 6: 'K',
    7: 'p', 8: 'n', 9: 'b', 10: 'r', 11: 'q', 12: 'k',
}

def square_index(rank, file):
    return rank * 8 + file

def board_cell(rank, file):
    return BOARD_START + square_index(rank, file)

def is_white_piece(piece_val):
    return 1 <= piece_val <= 6

def is_black_piece(piece_val):
    return 7 <= piece_val <= 12

INITIAL_BOARD = [
    WHITE_ROOK, WHITE_KNIGHT, WHITE_BISHOP, WHITE_QUEEN,
    WHITE_KING, WHITE_BISHOP, WHITE_KNIGHT, WHITE_ROOK,
    WHITE_PAWN, WHITE_PAWN, WHITE_PAWN, WHITE_PAWN,
    WHITE_PAWN, WHITE_PAWN, WHITE_PAWN, WHITE_PAWN,
    EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
    EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
    EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
    EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
    BLACK_PAWN, BLACK_PAWN, BLACK_PAWN, BLACK_PAWN,
    BLACK_PAWN, BLACK_PAWN, BLACK_PAWN, BLACK_PAWN,
    BLACK_ROOK, BLACK_KNIGHT, BLACK_BISHOP, BLACK_QUEEN,
    BLACK_KING, BLACK_BISHOP, BLACK_KNIGHT, BLACK_ROOK,
]
