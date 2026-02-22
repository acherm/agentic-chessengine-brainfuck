#!/usr/bin/env python3
"""
Play a full automated game against BFChess.

White moves are pre-scripted (a simple opening + responses).
Black moves come from the BF engine.
"""

import subprocess
import sys
import time

INITIAL_BOARD = [
    ['R','N','B','Q','K','B','N','R'],
    ['P','P','P','P','P','P','P','P'],
    ['.','.','.','.','.','.','.','.'],
    ['.','.','.','.','.','.','.','.'],
    ['.','.','.','.','.','.','.','.'],
    ['.','.','.','.','.','.','.','.'],
    ['p','p','p','p','p','p','p','p'],
    ['r','n','b','q','k','b','n','r'],
]

PIECE_MAP = {
    'P': '\u2659', 'N': '\u2658', 'B': '\u2657', 'R': '\u2656', 'Q': '\u2655', 'K': '\u2654',
    'p': '\u265F', 'n': '\u265E', 'b': '\u265D', 'r': '\u265C', 'q': '\u265B', 'k': '\u265A',
    '.': '.'
}

def parse_square(s):
    return ord(s[0]) - ord('a'), int(s[1]) - 1

def apply_move(board, move_str):
    ff, fr = parse_square(move_str[0:2])
    tf, tr = parse_square(move_str[2:4])
    piece = board[fr][ff]
    board[fr][ff] = '.'
    if len(move_str) > 4 and move_str[4] in 'qrbn':
        promo = move_str[4]
        piece = promo.upper() if piece.isupper() else promo
    board[tr][tf] = piece

def print_board(board):
    print("    a  b  c  d  e  f  g  h")
    print("  +------------------------+")
    for rank in range(7, -1, -1):
        row = f"{rank+1} |"
        for file in range(8):
            p = board[rank][file]
            row += f" {PIECE_MAP[p]} "
        row += f"| {rank+1}"
        print(row)
    print("  +------------------------+")
    print("    a  b  c  d  e  f  g  h")

def get_white_move(board, moves, move_num):
    """Pick a white move. Simple strategy: try a scripted opening, then scan for any legal-looking move."""
    scripted = [
        'e2e4', 'd2d4', 'g1f3', 'f1c4', 'b1c3',
        'c1e3', 'd1d2', 'e1c1',  # attempt queenside castle (just a move)
        'f3e5', 'c4f7', 'e5g6',
    ]
    if move_num - 1 < len(scripted):
        m = scripted[move_num - 1]
        ff, fr = parse_square(m[0:2])
        tf, tr = parse_square(m[2:4])
        # Check if from-square has our piece and to-square isn't our piece
        piece = board[fr][ff]
        if piece != '.' and piece.isupper():
            target = board[tr][tf]
            if not target.isupper():
                return m

    # Fallback: scan board for any white piece that can move somewhere
    for fr in range(8):
        for ff in range(8):
            p = board[fr][ff]
            if not p.isupper():
                continue
            # Try simple moves
            targets = []
            if p == 'P':
                if fr < 7 and board[fr+1][ff] == '.':
                    targets.append((ff, fr+1))
                if fr == 1 and board[fr+1][ff] == '.' and board[fr+2][ff] == '.':
                    targets.append((ff, fr+2))
                for df in [-1, 1]:
                    nf = ff + df
                    if 0 <= nf < 8 and fr+1 < 8 and board[fr+1][nf].islower():
                        targets.append((nf, fr+1))
            elif p == 'N':
                for dr, df in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
                    nr, nf = fr+dr, ff+df
                    if 0 <= nr < 8 and 0 <= nf < 8 and not board[nr][nf].isupper():
                        targets.append((nf, nr))
            elif p == 'K':
                for dr in [-1,0,1]:
                    for df in [-1,0,1]:
                        if dr == 0 and df == 0: continue
                        nr, nf = fr+dr, ff+df
                        if 0 <= nr < 8 and 0 <= nf < 8 and not board[nr][nf].isupper():
                            targets.append((nf, nr))
            elif p in 'RQ':
                for dr, df in [(-1,0),(1,0),(0,-1),(0,1)]:
                    for dist in range(1, 8):
                        nr, nf = fr+dr*dist, ff+df*dist
                        if not (0 <= nr < 8 and 0 <= nf < 8): break
                        if board[nr][nf].isupper(): break
                        targets.append((nf, nr))
                        if board[nr][nf] != '.': break
            if p in 'BQ':
                for dr, df in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                    for dist in range(1, 8):
                        nr, nf = fr+dr*dist, ff+df*dist
                        if not (0 <= nr < 8 and 0 <= nf < 8): break
                        if board[nr][nf].isupper(): break
                        targets.append((nf, nr))
                        if board[nr][nf] != '.': break

            for tf, tr in targets:
                return f"{chr(ff+97)}{fr+1}{chr(tf+97)}{tr+1}"

    return None  # no moves found


def main():
    max_moves = 10  # 128-byte buffer supports ~10 full moves

    proc = subprocess.Popen(
        ['./bfi', 'chess.bf'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def send(cmd):
        proc.stdin.write(cmd + '\n')
        proc.stdin.flush()

    def read_until(prefix, timeout=120):
        lines = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.rstrip('\n')
            lines.append(line)
            if line.startswith(prefix):
                return lines
        return lines

    # UCI handshake
    send('uci')
    read_until('uciok')
    send('isready')
    read_until('readyok')
    print("Engine ready.\n")

    board = [row[:] for row in INITIAL_BOARD]
    moves = []
    move_num = 1
    total_engine_time = 0

    print("=== Automated Game: White (scripted) vs Black (BFChess) ===\n")
    print_board(board)
    print()

    for move_num in range(1, max_moves + 1):
        # White move
        white_move = get_white_move(board, moves, move_num)
        if not white_move:
            print(f"\n--- White has no moves. Black wins! ---")
            break

        moves.append(white_move)
        apply_move(board, white_move)
        print(f"Move {move_num}. White: {white_move}")

        # Engine (black) move
        pos_cmd = "position startpos moves " + " ".join(moves)
        send(pos_cmd)
        send('go')
        start = time.time()
        lines = read_until('bestmove', timeout=120)
        elapsed = time.time() - start
        total_engine_time += elapsed

        engine_move = None
        for line in lines:
            if line.startswith('bestmove'):
                engine_move = line.split()[1]
                break

        if not engine_move or engine_move == '0000':
            print(f"         Black has no legal moves. White wins!\n")
            print_board(board)
            break

        moves.append(engine_move)
        apply_move(board, engine_move)
        print(f"         Black: {engine_move}  ({elapsed:.1f}s)")
        print()
        print_board(board)
        print()

    print(f"\n--- Game over after {len(moves)} half-moves ---")
    print(f"Total engine thinking time: {total_engine_time:.1f}s")
    print(f"Moves: {' '.join(moves)}")

    send('quit')
    proc.wait()


if __name__ == '__main__':
    main()
