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

## Elo History

| Version | Elo | Notes |
|---|---|---|
| Python Phase 7 | ~2043 | PVS, SEE, countermoves, pawn eval |
| Python WP1-7 | ~2029 | Speed fixes, eval enhancements |
| Rust v1 (depth 6) | ~2520 | Port to Rust, 100x faster |
| Rust v2 (depth 8) | ~3073 | Null move, array TT, tapered eval |
| Rust v2 (depth 10) | ~3590 | Same engine, deeper search |

## Engine Features

### Search
- Principal Variation Search (PVS) with alpha-beta pruning
- Iterative deepening with aspiration windows
- Transposition table (TT in both main search and quiescence)
- Null move pruning (Python only, pending Rust implementation)
- Late move reductions (log-based formula)
- Late move pruning, futility pruning, reverse futility pruning
- Razoring, delta pruning in quiescence
- Static Exchange Evaluation (SEE) pruning
- Internal Iterative Deepening (IID)
- Singular extensions
- Check extensions

### Evaluation
- Material + piece-square tables (middlegame/endgame king tables)
- Pawn structure: doubled, isolated, passed, connected, protected passers
- King safety: pawn shield, open files, attack-unit system (quadratic scaling)
- Mobility (knights, bishops, rooks)
- Knight outposts
- Bishop pair bonus
- Rook on open/semi-open files, 7th rank bonus
- Space advantage
- Endgame mop-up (drive losing king to corner)
- Tempo bonus

### Move Ordering
- TT move first
- Captures: MVV-LVA with winning/losing split
- Promotions
- Killer moves (2 per ply)
- History heuristic with aging
- Countermove heuristic (Python only)

## Project Structure

```
rust_engine/          - Rust engine (recommended)
  src/
    main.rs           - Entry point
    uci.rs            - UCI protocol + time management
    search.rs         - PVS, quiescence, TT, pruning
    eval.rs           - Position evaluation
    move_order.rs     - Move ordering heuristics
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
