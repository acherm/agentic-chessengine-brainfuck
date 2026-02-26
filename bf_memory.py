"""
Memory layout constants for the BF chess engine.

COMPACT layout — all hot cells within 0-120 to minimize pointer movements.

Tape layout:
  Cells 0-15:     16 general-purpose temporaries
  Cells 16-22,29: Game state (castling rights, EP, king pos)
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

# === Game State (16-22, 29) ===
SIDE_TO_MOVE = 16
WK_CASTLE = 17    # white kingside castling right (1=allowed)
EP_FILE = 18      # 0=none, 1-8 for file a-h (1-indexed)
WHITE_KING_POS = 19
BLACK_KING_POS = 20
WQ_CASTLE = 21    # white queenside castling right
BK_CASTLE = 22    # black kingside castling right
BQ_CASTLE = 29    # black queenside castling right (free cell before BOARD_START)

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

# For move skip / legality loop
SKIP_COUNT = 3     # TEMP+3: how many pseudo-legal moves to skip
FOUND_LEGAL = 4    # TEMP+4: set when a legal move is found

# For perft (enumerate all legal moves)
PERFT_COUNT = 127   # number of legal moves found (single byte, max 255)
PERFT_MODE = 128    # 0 = normal (stop at first legal), 1 = perft (enumerate all)

# Evaluation workspace (inside INPUT_BUF range, safe during movegen)
BEST_SCORE = 130    # best score seen so far (0 = no legal move found)
CAND_FROM = 131     # candidate best move from-square
CAND_TO = 132       # candidate best move to-square
MOVE_SCORE = 133    # current move's computed score
PIECE_TYPE = 134    # normalized piece type (1-6) for scoring
E_TMP1 = 135        # eval temp
E_TMP2 = 136        # eval temp
E_TMP3 = 137        # eval temp
E_TMP4 = 138        # eval temp
E_TMP5 = 139        # eval temp

# Special-move flags for make/unmake in generate_legal_move
IS_CASTLE_MOVE = 140   # 1 if current move is castling
IS_EP_MOVE = 141       # 1 if current move is en passant capture
CASTLE_ROOK_FROM = 142 # rook's source square for castling make/unmake
CASTLE_ROOK_TO = 143   # rook's destination square
EP_CAPTURE_SQ = 144    # square of captured pawn for EP make/unmake
SAVED_EP_PAWN = 145    # saved piece value from EP capture square
SAVED_ROOK = 146       # saved rook piece for castling unmake

# Gate flags for castling through-check
GATE_WK = 147  # 1 = f1 safe for white kingside
GATE_WQ = 148  # 1 = d1 safe for white queenside
GATE_BK = 149  # 1 = f8 safe for black kingside
GATE_BQ = 150  # 1 = d8 safe for black queenside

# In-check flag for castling legality
IN_CHECK = 151  # 1 = king is in check (blocks castling)

# 2-pass attack check workspace (king legality + hanging piece detection)
ATTACK_CNT = 152     # loop counter (2 iterations)
ATTACK_PASS = 153    # pass dispatch (0=king check, 1=dest check)
ILLEGAL_FLAG = 154   # saves king-check result across passes
DEST_ATTACKED = 155  # saves destination-attacked result

# Exchange detection workspace
VICTIM_TYPE = 156     # normalized victim piece type (1-6) for exchange detection
ATTACKER_TYPE = 157   # normalized attacker piece type (1-6)

# Check detection (3rd attack pass)
GIVES_CHECK = 158     # 1 if current move gives check to opponent
SAVED_STM = 159       # saved SIDE_TO_MOVE for check detection flip

# Alpha-beta control (inside INPUT_BUF range, safe during go)
BETA_CUTOFF = 170      # Level 2 cutoff threshold (set by Level 1 caller)
D2_ALPHA = 171         # Level 1 cutoff threshold (set by Level 0 caller)
CAPTURE_PHASE = 172    # captures-first phase counter
AB_CUTOFF_FLAG = 183   # 1 if beta cutoff triggered in inner loop

# Depth-3 control
D3_BEST_SCORE = 173    # best depth-2 result (maximizer, starts at 0)
D3_CAND_FROM = 174
D3_CAND_TO = 175
D3_OPP_RESULT = 176    # captured D2_BEST_SCORE from Level 1
D3_TMP1 = 177
D3_TMP2 = 178
D3_TMP3 = 179
D3_HAVE_LEGAL = 180
D3_OUR_SCORE = 181     # tiebreaker: our move's depth-1 score
D3_BEST_OUR_SCORE = 182

# Anti-repetition (must be OUTSIDE input buffer range 100-227, which is cleared every UCI loop)
LAST_FROM = 238       # engine's last move from-square
LAST_TO = 239         # engine's last move to-square

# For is_attacked / legality
KING_SQ = 240
ATTACKED = 241

# Board copy for make/unmake
BOARD_COPY = 250
BOARD_COPY_END = 314

# === Depth-2 search workspace ===
# Control cells (inside INPUT_BUF range, safe during go handler)
D2_BEST_SCORE = 160     # best (lowest) opponent score seen
D2_CAND_FROM = 161      # depth-2 best move from
D2_CAND_TO = 162        # depth-2 best move to
D2_OPP_SCORE = 163      # opponent's score from inner search
D2_TMP1 = 164           # depth-2 temp
D2_TMP2 = 165           # depth-2 temp
D2_TMP3 = 166           # depth-2 temp
D2_HAVE_LEGAL = 167     # found at least one legal move at depth 2
D2_OUR_SCORE = 168      # our move's depth-1 score (tiebreaker)
D2_BEST_OUR_SCORE = 169 # best candidate's our-score

# Saved outer-loop state (must survive inner generate_legal_move)
D2_SAVED_SKIP = 315
D2_SAVED_RETRY = 316
D2_SAVED_PIECE = 317
D2_SAVED_CAPTURE = 318
D2_SAVED_KING = 319
D2_SAVED_BEST_FROM = 320
D2_SAVED_BEST_TO = 321
D2_SAVED_IS_CASTLE = 322
D2_SAVED_IS_EP = 323
D2_SAVED_EP_CAP_SQ = 324
D2_SAVED_EP_PAWN = 325
D2_SAVED_GATE_WK = 326
D2_SAVED_GATE_WQ = 327
D2_SAVED_GATE_BK = 328
D2_SAVED_GATE_BQ = 329
D2_SAVED_IN_CHECK = 330

# Depth-3 saved outer-loop state (331-351)
D3_SAVED_SKIP = 331
D3_SAVED_RETRY = 332
D3_SAVED_PIECE = 333
D3_SAVED_CAPTURE = 334
D3_SAVED_KING = 335
D3_SAVED_BEST_FROM = 336
D3_SAVED_BEST_TO = 337
D3_SAVED_IS_CASTLE = 338
D3_SAVED_IS_EP = 339
D3_SAVED_EP_CAP_SQ = 340
D3_SAVED_EP_PAWN = 341
D3_SAVED_GATE_WK = 342
D3_SAVED_GATE_WQ = 343
D3_SAVED_GATE_BK = 344
D3_SAVED_GATE_BQ = 345
D3_SAVED_IN_CHECK = 346
# Save D2 tracking cells (overwritten when depth-2 runs)
D3_SAVED_D2_BEST = 347
D3_SAVED_D2_CAND_FROM = 348
D3_SAVED_D2_CAND_TO = 349
D3_SAVED_D2_HAVE_LEGAL = 350
D3_SAVED_D2_BEST_OUR = 351

# Game state backup for depth-2 (board[64] + 8 state cells = 72 cells)
D2_STATE_BASE = 400     # cells 400-471
# +0..63:  board backup
# +64:     SIDE_TO_MOVE
# +65:     EP_FILE
# +66:     WHITE_KING_POS
# +67:     BLACK_KING_POS
# +68..71: WK/WQ/BK/BQ_CASTLE

# Game state backup for depth-3 (board[64] + 8 state cells = 72 cells)
D3_STATE_BASE = 600     # cells 600-671

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
