#!/usr/bin/env python3
"""Interactive play against BFChess engine."""

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
    """Parse 'e2' -> (file_idx, rank_idx)."""
    return ord(s[0]) - ord('a'), int(s[1]) - 1

def apply_move(board, move_str):
    """Apply a move like 'e2e4' to the board array."""
    ff, fr = parse_square(move_str[0:2])
    tf, tr = parse_square(move_str[2:4])
    piece = board[fr][ff]
    board[fr][ff] = '.'
    # Handle promotion
    if len(move_str) > 4 and move_str[4] in 'qrbn':
        promo = move_str[4]
        if piece.isupper():
            piece = promo.upper()
        else:
            piece = promo
    board[tr][tf] = piece

def print_board(board):
    """Print board from white's perspective."""
    print()
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
    print()

def main():
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
        """Read lines until one starts with prefix."""
        import select
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

    # Init board once via domove protocol
    send('position startpos')

    board = [row[:] for row in INITIAL_BOARD]
    moves = []
    move_num = 1

    print("=== BFChess Interactive Game ===")
    print("You play White. Enter moves in UCI format (e.g. e2e4).")
    print("Type 'quit' to exit, 'board' to redraw.")
    print_board(board)

    while True:
        # Human (white) move
        while True:
            try:
                user_input = input(f"{move_num}. White> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                send('quit')
                proc.wait()
                return

            if user_input == 'quit':
                send('quit')
                proc.wait()
                return
            if user_input == 'board':
                print_board(board)
                continue
            if len(user_input) >= 4 and user_input[0] in 'abcdefgh' and user_input[2] in 'abcdefgh':
                break
            print("Invalid format. Use UCI notation like 'e2e4'.")

        moves.append(user_input)
        apply_move(board, user_input)
        print_board(board)

        # Send user's move via domove, then go
        send(f'domove {user_input}')
        send('go')
        print(f"   Engine thinking...", end='', flush=True)
        start = time.time()
        lines = read_until('bestmove', timeout=120)
        elapsed = time.time() - start

        engine_move = None
        for line in lines:
            if line.startswith('bestmove'):
                engine_move = line.split()[1]
                break

        if not engine_move or engine_move == '0000':
            print(f"\r   Engine has no legal moves. You win!")
            send('quit')
            proc.wait()
            return

        # Apply engine's move via domove
        send(f'domove {engine_move}')
        print(f"\r{move_num}. ...Black: {engine_move}  ({elapsed:.1f}s)")
        moves.append(engine_move)
        apply_move(board, engine_move)
        print_board(board)
        move_num += 1


if __name__ == '__main__':
    main()
