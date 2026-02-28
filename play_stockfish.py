#!/usr/bin/env python3
"""
Play BFChess vs Stockfish.

BFChess communicates via the custom domove UCI protocol.
Stockfish runs at configurable skill/depth to make games interesting.

Usage:
    python3 play_stockfish.py                        # 1 game, Stockfish depth 1
    python3 play_stockfish.py --games 10             # 10 games
    python3 play_stockfish.py --depth 3              # stronger Stockfish
    python3 play_stockfish.py --elo 1320             # weakest Stockfish Elo
    python3 play_stockfish.py --bf-white             # BFChess plays white
    python3 play_stockfish.py --both-sides           # alternate sides
    python3 play_stockfish.py --pgn games.pgn        # export PGN
"""

import argparse
import math
import subprocess
import sys
import time
from datetime import date

import chess
import chess.engine
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


def play_game(sf_engine, sf_depth, bf_plays_white, game_num, verbose, sf_config_str):
    """Play one game. Returns (result, chess.pgn.Game).
    result: 1.0/0.5/0.0 from BFChess perspective.
    """
    proc, send, read_until = start_bfchess()
    board = chess.Board()
    bf_time_total = 0
    sf_time_total = 0

    bf_side = chess.WHITE if bf_plays_white else chess.BLACK
    side_label = "White" if bf_plays_white else "Black"

    # Set up PGN game
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "BFChess vs Stockfish"
    pgn_game.headers["Site"] = "Local"
    pgn_game.headers["Date"] = date.today().strftime("%Y.%m.%d")
    pgn_game.headers["Round"] = str(game_num)
    if bf_plays_white:
        pgn_game.headers["White"] = "BFChess (MVV-LVA)"
        pgn_game.headers["Black"] = f"Stockfish 18 ({sf_config_str})"
    else:
        pgn_game.headers["White"] = f"Stockfish 18 ({sf_config_str})"
        pgn_game.headers["Black"] = "BFChess (MVV-LVA)"
    node = pgn_game

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game {game_num}: BFChess ({side_label}) vs Stockfish ({sf_config_str})")
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
                    print(f"     Legal: {[m.uci() for m in list(board.legal_moves)[:10]]}")
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
            start = time.time()
            sf_result = sf_engine.play(board, chess.engine.Limit(depth=sf_depth))
            elapsed = time.time() - start
            sf_time_total += elapsed

            move = sf_result.move
            node = node.add_variation(move)
            board.push(move)
            send_domove(send, move)

            if verbose:
                mn = (ply // 2) + 1
                prefix = f"  {mn}." if board.turn == chess.BLACK else f"  {mn}..."
                print(f"{prefix} {move.uci():6s} (SF {elapsed:.1f}s)")

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

    result_str = {1.0: "BFChess wins!", 0.0: "Stockfish wins!", 0.5: "Draw"}[result]
    print(f"  Game {game_num}: {result_str} ({reason})  "
          f"[{board.fullmove_number - 1} moves, BF {bf_time_total:.1f}s, SF {sf_time_total:.1f}s]")

    if verbose:
        print(f"  Final FEN: {board.fen()}")

    return result, pgn_game


def elo_diff_from_score(score, n):
    """Estimate Elo difference from score percentage.
    score: total points, n: number of games.
    Returns Elo difference (negative means BFChess is weaker).
    """
    pct = score / n
    if pct <= 0:
        return -800  # cap
    if pct >= 1:
        return 800
    return -400 * math.log10(1 / pct - 1)


def main():
    parser = argparse.ArgumentParser(description='BFChess vs Stockfish')
    parser.add_argument('--games', type=int, default=1, help='Number of games (default: 1)')
    parser.add_argument('--depth', type=int, default=1, help='Stockfish search depth (default: 1)')
    parser.add_argument('--elo', type=int, default=None,
                        help='Stockfish UCI_Elo (1320-3190, enables UCI_LimitStrength)')
    parser.add_argument('--skill', type=int, default=None,
                        help='Stockfish Skill Level (0-20, default: 0)')
    parser.add_argument('--bf-white', action='store_true', help='BFChess plays white (default: black)')
    parser.add_argument('--both-sides', action='store_true', help='Alternate sides each game')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all moves')
    parser.add_argument('--stockfish', default='stockfish', help='Path to stockfish binary')
    parser.add_argument('--pgn', default=None, help='PGN output file')
    args = parser.parse_args()

    sf_engine = chess.engine.SimpleEngine.popen_uci(args.stockfish)

    # Configure Stockfish weakness
    sf_config = {}
    sf_config_parts = []

    skill = args.skill if args.skill is not None else 0
    sf_config["Skill Level"] = skill
    sf_config_parts.append(f"skill {skill}")

    if args.elo is not None:
        sf_config["UCI_LimitStrength"] = True
        sf_config["UCI_Elo"] = args.elo
        sf_config_parts.append(f"Elo {args.elo}")

    sf_config_parts.append(f"depth {args.depth}")
    sf_config_str = ", ".join(sf_config_parts)

    try:
        sf_engine.configure(sf_config)
    except chess.engine.EngineError as e:
        print(f"Warning: couldn't configure Stockfish: {e}")

    wins = 0
    draws = 0
    losses = 0
    pgn_games = []

    print(f"BFChess vs Stockfish ({sf_config_str}), {args.games} game(s)")
    print(f"{'='*60}")

    for i in range(1, args.games + 1):
        if args.both_sides:
            bf_white = (i % 2 == 1)
        else:
            bf_white = args.bf_white

        result, pgn_game = play_game(sf_engine, args.depth, bf_white, i,
                                     args.verbose, sf_config_str)
        pgn_games.append(pgn_game)

        if result == 1.0:
            wins += 1
        elif result == 0.0:
            losses += 1
        else:
            draws += 1

    sf_engine.quit()

    # Summary
    total = args.games
    score = wins + draws * 0.5
    pct = score / total * 100

    print(f"\n{'='*60}")
    print(f"Results: +{wins} ={draws} -{losses} / {total}")
    print(f"Score: {score}/{total} ({pct:.0f}%)")

    elo_d = elo_diff_from_score(score, total)
    if args.elo:
        bf_elo_est = args.elo + elo_d
        print(f"Elo difference: {elo_d:+.0f} (BFChess estimated Elo: ~{bf_elo_est:.0f})")
    else:
        print(f"Elo difference vs this Stockfish config: {elo_d:+.0f}")

    # Export PGN
    if args.pgn:
        with open(args.pgn, 'w') as f:
            for g in pgn_games:
                print(g, file=f)
                print(file=f)
        print(f"PGN saved to {args.pgn}")


if __name__ == '__main__':
    main()
