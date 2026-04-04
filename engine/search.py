"""Search algorithm for CautiousPancake.

Phase 1: Negamax with depth-limited search.
"""

import chess
from engine.evaluate import evaluate
from engine.move_order import order_moves


def negamax(board: chess.Board, depth: int, alpha: int, beta: int) -> int:
    """Negamax search with alpha-beta pruning.

    Returns score from the perspective of the side to move.
    """
    if depth == 0 or board.is_game_over():
        # Evaluate from white's perspective, then adjust for side to move
        raw = evaluate(board)
        return raw if board.turn == chess.WHITE else -raw

    max_score = -99999
    for move in order_moves(board):
        board.push(move)
        score = -negamax(board, depth - 1, -beta, -alpha)
        board.pop()

        if score > max_score:
            max_score = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break  # Beta cutoff

    return max_score


def search(board: chess.Board, depth: int = 3) -> chess.Move:
    """Find the best move at a given depth.

    Returns the best move found.
    """
    best_move = None
    best_score = -99999
    alpha = -99999
    beta = 99999

    for move in order_moves(board):
        board.push(move)
        # Negate because opponent's best is our worst
        score = -negamax(board, depth - 1, -beta, -alpha)
        board.pop()

        if score > best_score:
            best_score = score
            best_move = move
        if score > alpha:
            alpha = score

    return best_move
