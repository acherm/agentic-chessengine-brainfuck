#!/usr/bin/env python3
"""
Perft test harness for BFChess engine.

Compares BF engine's perft output (depth 1) against python-chess reference.
"""

import subprocess
import sys
import time

try:
    import chess
except ImportError:
    print("ERROR: python-chess required. Install with: pip install python-chess")
    sys.exit(1)


BFI = "./bfi"
BF_FILE = "chess.bf"


def get_reference_moves(board):
    """Get legal moves from python-chess."""
    moves = []
    for move in board.legal_moves:
        uci = move.uci()
        # Use 4-char base move for comparison (BFChess uses queen-only promotion)
        base = uci[:4]
        moves.append(base)
    return sorted(set(moves))


def run_perft(proc, setup_commands):
    """Run perft via the BF engine and return (move_list, node_count)."""
    def send(cmd):
        proc.stdin.write(cmd + '\n')
        proc.stdin.flush()

    # Send setup commands
    for cmd in setup_commands:
        send(cmd)

    # Send perft
    send('perft')

    # Read output until we see "Nodes: "
    moves = []
    node_count = None
    deadline = time.time() + 300  # 5 minute timeout

    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.rstrip('\n').rstrip('\r')
        if not line:
            continue
        if line.startswith("Nodes: "):
            node_count = int(line.split(": ")[1])
            break
        # Should be a 4-char move like "e2e4"
        if len(line) == 4 and line[0] in 'abcdefgh' and line[2] in 'abcdefgh':
            moves.append(line)

    return sorted(moves), node_count


def start_engine():
    """Start the BF engine process."""
    proc = subprocess.Popen(
        [BFI, BF_FILE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def send(cmd):
        proc.stdin.write(cmd + '\n')
        proc.stdin.flush()

    def read_until(prefix, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            if line.rstrip('\n').startswith(prefix):
                return True
        return False

    send('uci')
    if not read_until('uciok'):
        print("ERROR: Engine did not respond to uci")
        proc.kill()
        sys.exit(1)

    send('isready')
    if not read_until('readyok'):
        print("ERROR: Engine did not respond to isready")
        proc.kill()
        sys.exit(1)

    return proc


def test_position(proc, name, setup_commands, board):
    """Test a single position. Returns True if passed."""
    print(f"\n--- {name} ---")

    ref_moves = get_reference_moves(board)
    ref_count = len(ref_moves)
    print(f"  Reference: {ref_count} legal moves")

    start = time.time()
    bf_moves, bf_count = run_perft(proc, setup_commands)
    elapsed = time.time() - start
    print(f"  BFChess:   {bf_count} nodes, {len(bf_moves)} moves listed ({elapsed:.1f}s)")

    passed = True

    # Check count
    if bf_count != ref_count:
        print(f"  FAIL: count mismatch: expected {ref_count}, got {bf_count}")
        passed = False

    # Check move lists
    missing = sorted(set(ref_moves) - set(bf_moves))
    extra = sorted(set(bf_moves) - set(ref_moves))

    if missing:
        print(f"  FAIL: missing moves: {' '.join(missing)}")
        passed = False
    if extra:
        print(f"  FAIL: extra moves:   {' '.join(extra)}")
        passed = False

    if passed:
        print(f"  PASS")

    return passed


def main():
    # Test positions: (name, domove_sequence, expected_side)
    test_cases = [
        ("Starting position (white)", [], "w"),
        ("After e2e4 (black)", ["e2e4"], "b"),
        ("After e2e4 e7e5 (white)", ["e2e4", "e7e5"], "w"),
        ("After d2d4 d7d5 c2c4 (black)", ["d2d4", "d7d5", "c2c4"], "b"),
        ("After e2e4 d7d5 (white)", ["e2e4", "d7d5"], "w"),
        ("After g1f3 (black)", ["g1f3"], "b"),
        ("After e2e4 e7e5 g1f3 b8c6 (white)", ["e2e4", "e7e5", "g1f3", "b8c6"], "w"),
        # Castling positions
        ("Castling ready (white)", ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"], "w"),
        ("Castling ready (black)", ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "d2d3"], "b"),
        # En passant positions
        ("EP available (white)", ["e2e4", "d7d5", "e4e5", "f7f5"], "w"),
        ("EP available (black)", ["d2d4", "e7e5", "d4d5", "a7a6", "a2a3", "c7c5"], "b"),
    ]

    passed = 0
    failed = 0

    for name, domoves, side in test_cases:
        # Start a fresh engine for each test
        proc = start_engine()

        try:
            # Build setup commands
            setup = ['position startpos']
            for m in domoves:
                setup.append(f'domove {m}')

            # Build reference board
            board = chess.Board()
            for m in domoves:
                board.push(chess.Move.from_uci(m))

            if test_position(proc, name, setup, board):
                passed += 1
            else:
                failed += 1
        finally:
            proc.stdin.write('quit\n')
            proc.stdin.flush()
            proc.wait(timeout=10)

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
