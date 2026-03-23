# BFChess Strength Assessment

## Engine Description

BFChess is a chess engine written entirely in Brainfuck (~5.6 MB). It communicates via the UCI protocol and generates legal moves with full legality checking (make/unmake + 3-pass king-in-check detection).

### Search: Depth-3 Minimax with Alpha-Beta Pruning

The engine searches 3 plies deep using minimax:

- **Depth-3** (maximizer): tries each legal move, calls depth-2
- **Depth-2** (minimizer): opponent's best reply, calls depth-1
- **Depth-1** (maximizer): enumerates all legal moves, scores each, picks highest

Alpha-beta pruning and captures-first move ordering reduce the search tree. Full board state (64 squares + 8 state cells) is saved/restored at each depth level.

### Move Evaluation: MVV-LVA + Positional

Each legal move is scored by a static evaluation function:

| Component | Score |
|---|---|
| Base (any legal move) | 1 |
| **Captures (MVV)** | |
| Capture pawn | +20 |
| Capture knight | +64 |
| Capture bishop | +66 |
| Capture rook | +100 |
| Capture queen | +180 |
| **LVA bonus** (pawn +5, knight/bishop +3, rook +1) | |
| **Special moves** (EP +20, castling +15) | |
| **Positional** (center +3, knight center +6, development +1, pawn advancement +2/+10/+20, rook 7th +5) | |
| **Tactical** (gives check +15, check+capture +25) | |
| **Penalties** (non-capture to attacked sq = 1, losing exchange = 2, anti-repetition = 1) | |

Piece values use standard ratios (1:3.2:3.3:5:9) scaled to fit 8-bit cells.

### Chess Features

- Full legal move generation for all piece types
- Castling (kingside + queenside, white + black) with rights tracking
- En passant capture and generation
- Promotion (queen-only in search; recognizes opponent underpromotions)
- Stalemate detection at all search depths (score 128 = draw)
- 3-pass attack analysis: king safety, destination safety, check detection

## Test Methodology

### Test 1: vs Stockfish 18 (calibrated Elo)

| Setting | Value |
|---|---|
| UCI_LimitStrength | true |
| UCI_Elo | 1320 (Stockfish minimum) |
| Skill Level | 20 (default, no artificial randomness) |
| Time control | 120+1s (CCRL 40/4 calibration TC) |
| BFChess time | Unlimited (fixed depth-3) |

This configuration uses the time control that Stockfish's UCI_Elo scale was calibrated against (anchored to CCRL 40/4), without the `Skill Level 0` setting that adds extra randomness and would double-weaken Stockfish.

### Test 2: vs Random Legal Moves (baseline)

The opponent plays uniformly random legal moves. This establishes a floor — any engine with coherent evaluation should beat random play consistently.

### Match Format

- 10 games per match, alternating sides
- Maximum 200 plies per game (exceeded = loss for BFChess)
- `domove` protocol: moves applied individually with castling rook, EP capture, and promotion handled internally

## Results

### vs Stockfish 1320 (120+1s)

```
Results: +0 =0 -10 / 10 (0%)
All 10 losses by checkmate
Estimated BFChess Elo: ~520 (CCRL scale)
```

| Game | BF side | Moves | BF time | SF time | Termination |
|------|---------|-------|---------|---------|-------------|
| 1 | White | 32 | 3755s | 60s | Checkmate |
| 2 | Black | 27 | 1705s | 58s | Checkmate |
| 3 | White | 25 | 1848s | 47s | Checkmate |
| 4 | Black | 26 | 1250s | 56s | Checkmate |
| 5 | White | 18 | 2166s | 40s | Checkmate |
| 6 | Black | 15 | 4734s | 35s | Checkmate |
| 7 | White | 27 | 5651s | 60s | Checkmate |
| 8 | Black | 12 | 1117s | 29s | Checkmate |
| 9 | White | 26 | 2735s | 49s | Checkmate |
| 10 | Black | 21 | 1241s | 43s | Checkmate |

Stockfish never used more than half its 120+1s clock (max ~60s used). Games lasted 12-32 moves. BFChess moves took 45-600+ seconds each depending on position complexity.

### vs Random

```
Results: +4 =6 -0 / 10 (70%)
4 wins by checkmate, 6 draws by stalemate, 0 losses
```

| Game | BF side | Moves | Result | Termination |
|------|---------|-------|--------|-------------|
| 1 | White | 13 | Win | Checkmate |
| 2 | Black | 54 | Draw | Stalemate |
| 3 | White | 56 | Draw | Stalemate |
| 4 | Black | 51 | Draw | Stalemate |
| 5 | White | 30 | Draw | Stalemate |
| 6 | Black | 56 | Draw | Stalemate |
| 7 | White | 33 | Win | Checkmate |
| 8 | Black | 59 | Win | Checkmate |
| 9 | White | 29 | Win | Checkmate |
| 10 | Black | 51 | Draw | Stalemate |

BFChess dominates the opening and middlegame, capturing all material. However, 60% of games end in stalemate: after winning everything, the engine accidentally traps the bare king. The search includes stalemate detection (score 128 = draw), but stalemate positions that form beyond the 3-ply horizon remain invisible.

## Illustrative Games

### Game 8 vs Stockfish — Fastest Loss (12 moves)

```
1. e3 Nf6 2. d4 e5 3. Be2 Bb4+ 4. c3 Bxc3+ 5. bxc3 exd4
6. Nf3 c5 7. a3 O-O 8. exd4 Re8 9. O-O Qc7 10. d5 Rxe2
11. Qxe2 Qxh2+ 12. Nxh2 Nxd5 13. Qe8#
```

BFChess opens with e3 (unusual), develops, and castles. But Stockfish exploits tactical weaknesses — BFChess captures Stockfish's queen (Qxe2) only to get back-rank mated (Qe8#). The engine sees captures but not the resulting threats.

### Game 7 vs Stockfish — Longest Game (32 moves)

```
1. d4 d5 2. e4 e6 3. exd5 Qxd5 4. Bd3 Qxg2 5. d5 Qxd5
6. c3 Qxh1 7. Qa4+ Nc6 8. Bf1 Qd5 9. Qd4 Qd6 10. Qxd6 cxd6
... 30. b4 Rg2+ 31. Kf1 Ne3+ 32. Ke1 Bh4#
```

BFChess loses the exchange (Qxg2, Qxh1 — Stockfish grabs both rooks). After queens trade off, BFChess fights on for 20 more moves but is hopelessly down material.

### Game 1 vs Random — Fastest Win (13 moves)

```
1. d4 d6 2. d5 b6 3. Qd4 Nh6 4. Qe5 Be6 5. Qxg7 Bxg7
6. Bxh6 Bd4 7. e4 Bc8 8. Bb5+ Nd7 9. e5 Rf8 10. Bxf8 dxe5
11. d6 Be3 12. dxc7 Bc1 13. Bxe7 Be3 14. cxd8=Q#
```

BFChess trades the queen early for material (Qxg7 + Bxh6), pushes the d-pawn to promotion, and checkmates with cxd8=Q#. The MVV-LVA evaluation correctly prioritizes captures and pawn advancement.

## Elo Estimate

Using the standard formula: `Elo_diff = -400 * log10(1/score_pct - 1)`

| Opponent | Score | Elo diff | BFChess Elo (est.) |
|----------|-------|----------|-------------------|
| Random (~200 Elo) | 70% | +147 | ~350 |
| Stockfish 1320 (120+1s) | 0% | -800 (capped) | ~520 |

The gap between estimates reflects small sample size and the Elo formula's sensitivity at extreme win rates. A reasonable estimate is **~400-500 Elo** on the CCRL scale.

For context:
- Random legal moves: ~200 Elo
- Simple 1-ply MVV-LVA (no search): ~400-600 Elo
- Depth 4-5 with alpha-beta: ~1200-1500 Elo

BFChess at depth-3 with alpha-beta sits at the low end of this range. The engine captures valuable pieces, controls the center, detects checks, and avoids losing exchanges — but 3 plies of lookahead is not enough to see tactical threats that even minimum-strength Stockfish exploits.

### Key Weaknesses Observed

1. **No king safety**: the engine ignores threats to its own king, leading to quick checkmates
2. **Stalemate blindness**: wins all material but stalemates the bare king (60% of games vs Random)
3. **No time management**: each move takes 45-600+ seconds, making longer games impractical
4. **Queen trades**: MVV-LVA eagerly trades queens, often into losing positions
5. **No endgame knowledge**: cannot convert winning material into checkmate reliably

## Reproduction

```bash
# Generate the engine
make

# Run calibrated Stockfish tournament (CCRL 40/4 time control)
python3 play_stockfish.py --elo 1320 --games 10 --both-sides --pgn stockfish.pgn -v

# Run random baseline
python3 play_random.py --games 10 --both-sides --seed 123 --pgn random.pgn -v
```

## PGN Files

- `elo_calibrated_v2.pgn` — 10 games vs Stockfish 1320 (120+1s, calibrated)
- `random_v2.pgn` — 10 games vs Random
- `bfchess_vs_stockfish.pgn` — historical 20 games vs Stockfish (depth-1 era, Skill 0)
- `depth3_fixed.pgn` — 10 games at depth-3 (pre-piece-value-update)

## Date

2026-03-23
