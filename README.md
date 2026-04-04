# CautiousPancake Chess Engine

A UCI-compatible chess engine built iteratively to maximize Elo.

## Quick Start

```bash
pip install chess pytest
python run.py          # Start UCI mode
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Run Engine Matches

```bash
# Self-play (our engine vs itself)
python bench/run_match.py --games 20 --depth 3

# Against another engine
python bench/run_match.py --games 20 --depth 3 --opponent "stockfish"

# View Elo history
python bench/elo_tracker.py
```

## Project Structure

```
engine/
  uci.py          - UCI protocol loop
  search.py       - Negamax with alpha-beta pruning
  evaluate.py     - Position evaluation (material)
  move_order.py   - Move ordering (MVV-LVA)
tests/            - pytest test suite
bench/            - Benchmarking and Elo tracking
```
