"""Move ordering for CautiousPancake.

TT move > captures (MVV-LVA) > killer moves > countermove > history heuristic.
"""

import chess

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

_killer_moves: dict[int, list[chess.Move]] = {}
_history: dict[tuple[bool, int, int], int] = {}
_max_history = 1  # Track max to normalize


def reset():
    """Reset killer moves and history for a new search."""
    global _max_history
    _killer_moves.clear()
    _history.clear()
    _max_history = 1


def record_killer(move: chess.Move, depth: int):
    """Record a quiet move that caused a beta cutoff."""
    if depth not in _killer_moves:
        _killer_moves[depth] = []
    killers = _killer_moves[depth]
    if move not in killers:
        killers.insert(0, move)
        if len(killers) > 2:
            killers.pop()


def record_history(move: chess.Move, color: bool, depth: int):
    """Record a move that improved alpha. Uses depth^2 weighting."""
    global _max_history
    key = (color, move.from_square, move.to_square)
    val = _history.get(key, 0) + depth * depth
    _history[key] = val
    if val > _max_history:
        _max_history = val
    # Age history to prevent overflow
    if _max_history > 10000:
        for k in _history:
            _history[k] //= 2
        _max_history //= 2


def _move_score(board: chess.Board, move: chess.Move, depth: int,
                countermove: chess.Move = None) -> int:
    """Score a move for ordering. Higher = searched first."""
    # Captures: winning/equal captures high, losing captures below killers
    if board.is_capture(move):
        victim = board.piece_type_at(move.to_square)
        attacker = board.piece_type_at(move.from_square)
        if victim is None:
            return 10000 + 10  # En passant
        victim_val = PIECE_VALUES.get(victim, 0)
        attacker_val = PIECE_VALUES.get(attacker, 0)
        mvv_lva = victim_val * 10 - attacker_val
        if victim_val >= attacker_val:
            return 10000 + mvv_lva  # Good captures: above killers
        else:
            return 5000 + mvv_lva  # Losing captures: below killers, above history

    # Promotions
    if move.promotion:
        return 9000 + PIECE_VALUES.get(move.promotion, 0)

    # Killer moves (two slots per depth)
    killers = _killer_moves.get(depth, [])
    if move in killers:
        return 8000 + (1 if move == killers[0] else 0)

    # Countermove
    if countermove is not None and move == countermove:
        return 7000

    # History heuristic
    key = (board.turn, move.from_square, move.to_square)
    return _history.get(key, 0)


def order_moves(board: chess.Board, moves=None, depth: int = 0,
                tt_move: chess.Move = None, countermove: chess.Move = None) -> list[chess.Move]:
    """Order moves for alpha-beta efficiency. TT/PV move is always first."""
    if moves is None:
        moves = list(board.legal_moves)
    if tt_move is not None and tt_move in moves:
        moves.remove(tt_move)
        rest = sorted(moves, key=lambda m: _move_score(board, m, depth, countermove), reverse=True)
        return [tt_move] + rest
    return sorted(moves, key=lambda m: _move_score(board, m, depth, countermove), reverse=True)
