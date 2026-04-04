"""Move ordering for CautiousPancake.

Phase 1: Captures first (MVV-LVA), then quiet moves.
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


def mvv_lva_score(board: chess.Board, move: chess.Move) -> int:
    """Score a capture by Most Valuable Victim - Least Valuable Attacker."""
    if not board.is_capture(move):
        return 0
    victim = board.piece_type_at(move.to_square)
    attacker = board.piece_type_at(move.from_square)
    if victim is None:
        # En passant
        return 10
    return PIECE_VALUES.get(victim, 0) * 10 - PIECE_VALUES.get(attacker, 0)


def order_moves(board: chess.Board, moves=None) -> list[chess.Move]:
    """Order moves: captures first (by MVV-LVA), then quiet moves."""
    if moves is None:
        moves = list(board.legal_moves)
    return sorted(moves, key=lambda m: mvv_lva_score(board, m), reverse=True)
