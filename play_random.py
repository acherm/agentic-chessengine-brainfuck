#!/usr/bin/env python3
"""
Play BFChess vs a Random chess engine.

The random engine picks a uniformly random legal move each turn.
This is a baseline test: BFChess should beat random play consistently.

Usage:
    python3 play_random.py                        # 1 game
    python3 play_random.py --games 10 --both-sides --pgn random.pgn -v
"""

import argparse
import math
import random
import subprocess
import sys
import time
from datetime import date

import chess
import chess.pgn


def send_domove(send, move):
    """Send domove for a move. Castling/EP handled by apply_single_move."""
    send(f'domove {move.uci()}')


def start_bfchess():
    """Start BFChess engine subprocess, do UCI handshake."""
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

    send('uci')
    read_until('uciok')
    send('isready')
    read_until('readyok')
    send('position startpos')

    return proc, send, read_until


def bf_get_move(send, read_until):
    """Ask BFChess for its best move. Returns UCI move string or None."""
    send('go')
    start = time.time()
    lines = read_until('bestmove', timeout=300)
    elapsed = time.time() - start
    for line in lines:
        if line.startswith('bestmove'):
            move_str = line.split()[1]
            if move_str == '0000':
                return None, elapsed
            return move_str, elapsed
    return None, elapsed


def play_game(bf_plays_white, game_num, verbose, seed=None):
    """Play one game. Returns (result, chess.pgn.Game).
    result: 1.0/0.5/0.0 from BFChess perspective.
    """
    rng = random.Random(seed)
    proc, send, read_until = start_bfchess()
    board = chess.Board()
    bf_time_total = 0

    bf_side = chess.WHITE if bf_plays_white else chess.BLACK
    side_label = "White" if bf_plays_white else "Black"

    # Set up PGN game
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "BFChess vs Random"
    pgn_game.headers["Site"] = "Local"
    pgn_game.headers["Date"] = date.today().strftime("%Y.%m.%d")
    pgn_game.headers["Round"] = str(game_num)
    if bf_plays_white:
        pgn_game.headers["White"] = "BFChess (depth-3)"
        pgn_game.headers["Black"] = "Random"
    else:
        pgn_game.headers["White"] = "Random"
        pgn_game.headers["Black"] = "BFChess (depth-3)"
    node = pgn_game

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game {game_num}: BFChess ({side_label}) vs Random")
        print(f"{'='*60}")

    max_plies = 200
    result = None
    reason = None

    for ply in range(max_plies):
        if board.is_game_over():
            break

        is_bf_turn = (board.turn == bf_side)

        if is_bf_turn:
            move_str, elapsed = bf_get_move(send, read_until)
            bf_time_total += elapsed

            if move_str is None:
                if verbose:
                    print(f"  ** BFChess returned no move (bestmove 0000 or timeout)")
                    print(f"     FEN: {board.fen()}")
                result = 0.0
                reason = "no move returned"
                break

            try:
                move = chess.Move.from_uci(move_str)
                if move not in board.legal_moves:
                    move = chess.Move.from_uci(move_str + 'q')
                    if move not in board.legal_moves:
                        if verbose:
                            print(f"  ** BFChess illegal move: {move_str}")
                            print(f"     FEN: {board.fen()}")
                            print(f"     Legal: {[m.uci() for m in board.legal_moves]}")
                        result = 0.0
                        reason = f"illegal move {move_str}"
                        break
            except ValueError:
                if verbose:
                    print(f"  ** BFChess invalid move format: {move_str}")
                result = 0.0
                reason = f"invalid move {move_str}"
                break

            node = node.add_variation(move)
            board.push(move)
            send_domove(send, move)

            if verbose:
                mn = (ply // 2) + 1
                prefix = f"  {mn}." if board.turn == chess.BLACK else f"  {mn}..."
                print(f"{prefix} {move.uci():6s} (BF {elapsed:.1f}s)")

        else:
            # Random engine: pick a uniformly random legal move
            legal_moves = list(board.legal_moves)
            move = rng.choice(legal_moves)

            node = node.add_variation(move)
            board.push(move)
            send_domove(send, move)

            if verbose:
                mn = (ply // 2) + 1
                prefix = f"  {mn}." if board.turn == chess.BLACK else f"  {mn}..."
                print(f"{prefix} {move.uci():6s} (Random)")

    # Determine result
    send('quit')
    proc.wait()

    if result is None:
        if board.is_checkmate():
            if board.turn == bf_side:
                result = 0.0
            else:
                result = 1.0
        elif board.is_game_over():
            result = 0.5
        else:
            result = 0.0  # max plies reached — count as loss for BFChess

    # Set PGN result and reason
    outcome = board.outcome()
    if reason is None:
        if outcome:
            reason = outcome.termination.name
        elif not board.is_game_over():
            reason = "max plies"
        else:
            reason = "unknown"

    if outcome:
        pgn_game.headers["Result"] = outcome.result()
    elif result == 0.5:
        pgn_game.headers["Result"] = "1/2-1/2"
    elif result == 1.0:
        pgn_game.headers["Result"] = "1-0" if bf_plays_white else "0-1"
    else:
        pgn_game.headers["Result"] = "0-1" if bf_plays_white else "1-0"

    result_str = {1.0: "BFChess wins!", 0.0: "Random wins!", 0.5: "Draw"}[result]
    print(f"  Game {game_num}: {result_str} ({reason})  "
          f"[{board.fullmove_number - 1} moves, BF {bf_time_total:.1f}s]")

    if verbose:
        print(f"  Final FEN: {board.fen()}")

    return result, pgn_game


def elo_diff_from_score(score, n):
    """Estimate Elo difference from score percentage."""
    pct = score / n
    if pct <= 0:
        return -800
    if pct >= 1:
        return 800
    return -400 * math.log10(1 / pct - 1)


def main():
    parser = argparse.ArgumentParser(description='BFChess vs Random engine')
    parser.add_argument('--games', type=int, default=1, help='Number of games (default: 1)')
    parser.add_argument('--bf-white', action='store_true', help='BFChess plays white (default: black)')
    parser.add_argument('--both-sides', action='store_true', help='Alternate sides each game')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all moves')
    parser.add_argument('--pgn', default=None, help='PGN output file')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for reproducibility')
    args = parser.parse_args()

    wins = 0
    draws = 0
    losses = 0
    pgn_games = []

    print(f"BFChess vs Random engine, {args.games} game(s)")
    print(f"{'='*60}")

    for i in range(1, args.games + 1):
        if args.both_sides:
            bf_white = (i % 2 == 1)
        else:
            bf_white = args.bf_white

        game_seed = (args.seed + i) if args.seed is not None else None
        result, pgn_game = play_game(bf_white, i, args.verbose, seed=game_seed)
        pgn_games.append(pgn_game)

        if result == 1.0:
            wins += 1
        elif result == 0.0:
            losses += 1
        else:
            draws += 1

    # Summary
    total = args.games
    score = wins + draws * 0.5
    pct = score / total * 100

    print(f"\n{'='*60}")
    print(f"Results: +{wins} ={draws} -{losses} / {total}")
    print(f"Score: {score}/{total} ({pct:.0f}%)")

    # Random play is roughly Elo 0-100
    elo_d = elo_diff_from_score(score, total)
    est_random_elo = 50  # Random play baseline
    bf_elo_est = est_random_elo + elo_d
    print(f"Elo difference vs Random: {elo_d:+.0f} (BFChess estimated Elo: ~{bf_elo_est:.0f})")

    # Export PGN
    if args.pgn:
        with open(args.pgn, 'w') as f:
            for g in pgn_games:
                print(g, file=f)
                print(file=f)
        print(f"PGN saved to {args.pgn}")


if __name__ == '__main__':
    main()
