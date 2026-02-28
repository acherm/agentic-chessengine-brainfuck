# BFChess Strength Assessment

## Engine Description

BFChess is a chess engine written entirely in Brainfuck (~943 KB). It communicates via the UCI protocol and generates legal moves with full legality checking (make/unmake + king-in-check detection).

### Move Selection: MVV-LVA + Center Bonus

The engine enumerates all legal moves in a position, scores each one, and picks the highest-scoring move. There is no search tree — it evaluates moves one ply deep based on a static scoring formula:

| Component | Score |
|---|---|
| Base (any legal move) | 1 |
| Capture pawn | +10 |
| Capture knight/bishop | +30 |
| Capture rook | +50 |
| Capture queen | +90 |
| Move to center (d4/e4/d5/e5) | +3 |

This means the engine will:
- Always prefer capturing a queen over capturing a pawn
- Prefer center moves over rim moves when no captures are available
- Never look ahead (no minimax, no alpha-beta, no quiescence search)

### Known Limitations

- No castling in move generation (engine never castles)
- No en passant
- Queen-only promotion (no underpromotion)
- No search depth — purely greedy single-ply evaluation
- No king safety, pawn structure, or positional evaluation

## Test Methodology

### Opponent: Stockfish 18 (weakest configuration)

| Setting | Value |
|---|---|
| UCI_LimitStrength | true |
| UCI_Elo | 1320 (minimum) |
| Skill Level | 0 (minimum) |
| Search depth | 1 |

### Match Format

- 20 games, alternating sides (BFChess white on odd games, black on even)
- Maximum 200 plies per game
- Castling synchronization: when Stockfish castles, 3 `domove` commands are sent to BFChess (king move + rook move + side-fix no-op) to keep boards in sync despite the engine's side-to-move toggle behavior

## Results

```
BFChess vs Stockfish (skill 0, Elo 1320, depth 1), 20 games
============================================================
Score: +0 =0 -20 / 20 (0%)
Estimated BFChess Elo: ~520
```

All 20 games ended in checkmate. No illegal moves, no draws.

### Game Length Statistics

| Metric | Moves |
|---|---|
| Shortest game | 7 (Game 19) |
| Longest game | 50 (Game 5) |
| Average | ~25 |
| Median | ~24 |

### As White (10 games)

BFChess opens with d2d4 (center pawn, reflecting center bonus). Typical patterns:
- Trades queens early when given the chance (MVV-LVA prioritizes high-value captures)
- Loses material quickly after the opening due to no tactical awareness
- Rooks often shuttle Ra1-Rb1-Ra1 (no good captures, limited quiet move evaluation)

### As Black (10 games)

BFChess responds to 1.c3 with d5, to 1.e4 with d5 or dxe4. Typical patterns:
- Eagerly captures central pawns (good)
- Gives away queen for minor pieces when opponent attacks it (no defensive awareness)
- Passed pawns sometimes advance deep but get captured before promoting

## Illustrative Games

### Game 19 — Fastest Loss (7 moves)

```
1. d4 Nf6 2. e4 Nxe4 3. d5 e6 4. dxe6 Bb4+ 5. Nd2 fxe6 6. Rb1 Qh4 7. Ra1 Qxf2#
```

BFChess captures pawns aggressively but ignores the mate threat on f2. The rook shuttles uselessly between a1 and b1 while Stockfish delivers a quick checkmate.

### Game 5 — Longest Game (50 moves)

BFChess survives 50 moves by trading queens early (1.d4 e6 2.e4 d5 3.exd5 Qxd5 ... 10.Qxd5 Nc6). Without queens on the board, Stockfish takes longer to construct a mating attack, but BFChess lacks any plan and eventually gets ground down.

### Game 13 — Pawn Promotion

```
1. d4 d5 2. e4 dxe4 3. d5 e5 4. Qd4 Be6 5. dxe6 exd4 6. exf7+ Ke7 7. fxg8=Q Rxg8
```

BFChess pushes a pawn to promotion and gets a queen, showing the MVV-LVA scoring works for pawn advances. However, the engine still loses because it has no positional understanding and trades the new queen away.

## Elo Estimate

Using the standard formula: `Elo_diff = -400 * log10(1/score_pct - 1)`

With 0/20 score, the formula gives -800 (capped). Against Stockfish's minimum Elo of 1320, this gives an upper bound estimate of **~520 Elo** for BFChess.

For context:
- Random legal moves: ~200 Elo
- MVV-LVA only (no search): ~400-600 Elo
- Simple 1-ply search: ~800-1000 Elo
- Depth 4-5 with alpha-beta: ~1200-1500 Elo

The MVV-LVA scoring provides a clear improvement over random play (the engine captures valuable pieces and prefers center squares), but the lack of any lookahead means it cannot see threats, avoid traps, or plan ahead.

## Reproduction

```bash
# Generate the engine
python3 generate.py

# Run 20 games against weakest Stockfish
python3 play_stockfish.py --games 20 --both-sides --elo 1320 --skill 0 --depth 1 --pgn games.pgn -v
```

## PGN

Full game records are in `bfchess_vs_stockfish.pgn`.

## Date

2026-02-23
