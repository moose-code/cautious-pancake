# CautiousPancake Chess Engine

A UCI-compatible chess engine built iteratively using Claude Code. Features both a Python prototype and a high-performance Rust engine (~2500 Elo).

## Quick Start (Rust — recommended)

```bash
cd rust_engine
cargo build --release
./target/release/cautious-pancake   # Start UCI mode
```

## Quick Start (Python)

```bash
pip install chess pytest
python run.py   # Start UCI mode
```

## Testing Strength

Requires Stockfish installed (`apt install stockfish` or similar).

```bash
# Rust engine vs Stockfish at 2000 Elo (24 games, depth 6)
python bench/test_strength.py --rust --elo 2000 --depth 6

# Rust engine vs Stockfish at 2400 Elo
python bench/test_strength.py --rust --elo 2400 --depth 6

# Python engine vs Stockfish
python bench/test_strength.py --elo 2000 --depth 4

# Quick sanity check (6 games)
python bench/test_strength.py --rust --quick

# NPS benchmark (Python only)
python bench/test_strength.py --nps

# View Elo history
python bench/elo_tracker.py
```

## Playing Against It

Use any UCI-compatible GUI (Arena, CuteChess, Lucas Chess, etc.):

1. Build the Rust engine: `cd rust_engine && cargo build --release`
2. In your GUI, add a new engine pointing to `rust_engine/target/release/cautious-pancake`
3. Play!

Or test interactively via CLI:
```bash
./rust_engine/target/release/cautious-pancake
uci
isready
position startpos moves e2e4 e7e5
go depth 8
quit
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Strength Measurement

Tested against Stockfish with `UCI_Elo` limiter at equal fixed depths (30 games each):

| Opponent | Depth | Score | W-L-D | Estimated |
|---|---|---|---|---|
| SF 1500 | 6 | 68% | +20 -9 =1 | ~1633 |
| SF 1800 | 6 | 67% | +19 -9 =2 | ~1920 |
| SF 2000 | 8 | 82% | +24 -5 =1 | ~2259 |
| SF 2200 | 8 | 78% | +23 -6 =1 | ~2423 |
| SF 2500 | 10 | 87% | +26 -4 =0 | ~2825 |

**Important caveat:** These numbers use Stockfish's `UCI_LimitStrength` which doesn't accurately simulate a player of that rating. Real Elo against calibrated opposition (CCRL-style) would likely be lower. Sample sizes are small (30 games = ~50 Elo error bars). For a proper rating, the engine should be submitted to a rating list like CCRL or tested via CuteChess gauntlets against multiple calibrated opponents. Realistic estimate: **~2200-2600** against real opposition depending on time control.

## Engine Features

### Search
- Principal Variation Search (PVS) with alpha-beta pruning
- Iterative deepening with aspiration windows
- Array-based transposition table (4M entries, in both main search and quiescence)
- Null move pruning with adaptive R and verification search
- Late move reductions (precomputed log-based table, history-adjusted)
- Late move pruning, futility pruning, reverse futility pruning (to depth 5)
- Razoring, delta pruning in quiescence
- Multi-ply Static Exchange Evaluation (full swap algorithm)
- SEE pruning for bad captures (to depth 5, quadratic threshold)
- History-based pruning for quiet moves with bad history
- Internal Iterative Deepening (IID)
- Singular extensions
- Check extensions
- Contempt factor (15cp draw penalty)
- Embedded opening book

### Evaluation
- Tapered eval (smooth middlegame/endgame blend by game phase)
- Material + piece-square tables (separate MG/EG king tables)
- Pawn structure: doubled, isolated, passed, connected, protected passers
- King safety: pawn shield, open files, attack-unit system (quadratic scaling)
- Mobility (knights, bishops, rooks)
- Knight outposts
- Bishop pair bonus (30 MG, 50 EG)
- Rook on open/semi-open files, 7th rank bonus
- Space advantage
- Endgame mop-up (drive losing king to corner)
- Tempo bonus

### Move Ordering
- TT move first
- Captures: MVV-LVA with winning/losing split
- Promotions
- Killer moves (2 per ply)
- History heuristic with aging + malus for non-cutoff moves
- Countermove heuristic
- LMR for bad captures (negative SEE)

## Project Structure

```
rust_engine/          - Rust engine (recommended)
  src/
    main.rs           - Entry point
    uci.rs            - UCI protocol + phase-aware time management
    search.rs         - PVS, quiescence, TT, all pruning
    eval.rs           - Tapered evaluation
    move_order.rs     - Move ordering heuristics
    book.rs           - Embedded opening book
engine/               - Python engine (prototype)
  uci.py              - UCI protocol
  search.py           - Search with all pruning techniques
  evaluate.py         - Full evaluation function
  move_order.py       - Move ordering
  time_manager.py     - Time allocation
tests/                - Python test suite (23 tests)
bench/                - Benchmarking tools
  test_strength.py    - Elo measurement vs Stockfish
  openings.py         - 20 opening positions
  elo_tracker.py      - Results history
  run_match.py        - Engine match runner
```
