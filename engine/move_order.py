"""Move ordering for CautiousPancake.

Captures first (MVV-LVA), then killer moves, then quiet moves.
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

# Killer moves: quiet moves that caused beta cutoffs, indexed by depth
# Each depth stores up to 2 killer moves
_killer_moves: dict[int, list[chess.Move]] = {}

# History heuristic: tracks how often a move causes cutoffs
_history: dict[tuple[bool, int, int], int] = {}  # (color, from_sq, to_sq) -> score


def reset():
    """Reset killer moves and history for a new search."""
    _killer_moves.clear()
    _history.clear()


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
    """Record a move that improved alpha."""
    key = (color, move.from_square, move.to_square)
    _history[key] = _history.get(key, 0) + depth * depth


def _move_score(board: chess.Board, move: chess.Move, depth: int) -> int:
    """Score a move for ordering. Higher = searched first."""
    # Captures get high priority via MVV-LVA
    if board.is_capture(move):
        victim = board.piece_type_at(move.to_square)
        attacker = board.piece_type_at(move.from_square)
        if victim is None:
            return 10000 + 10  # En passant
        return 10000 + PIECE_VALUES.get(victim, 0) * 10 - PIECE_VALUES.get(attacker, 0)

    # Promotions
    if move.promotion:
        return 9000 + PIECE_VALUES.get(move.promotion, 0)

    # Killer moves
    killers = _killer_moves.get(depth, [])
    if move in killers:
        return 8000

    # History heuristic
    key = (board.turn, move.from_square, move.to_square)
    return _history.get(key, 0)


def order_moves(board: chess.Board, moves=None, depth: int = 0, tt_move: chess.Move = None) -> list[chess.Move]:
    """Order moves for alpha-beta efficiency. TT/PV move is searched first."""
    if moves is None:
        moves = list(board.legal_moves)
    if tt_move is not None and tt_move in moves:
        moves.remove(tt_move)
        return [tt_move] + sorted(moves, key=lambda m: _move_score(board, m, depth), reverse=True)
    return sorted(moves, key=lambda m: _move_score(board, m, depth), reverse=True)
