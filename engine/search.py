"""Search algorithm for CautiousPancake.

Negamax with alpha-beta pruning, quiescence search, iterative deepening,
null move pruning, killer moves, and history heuristic.
"""

import time
import chess
from engine.evaluate import evaluate
from engine.move_order import order_moves, record_killer, record_history, reset as reset_move_order

# Mate score constants
MATE_SCORE = 30000
INF = 99999

# Global node counter for stats
nodes_searched = 0


def _eval_for_side(board: chess.Board) -> int:
    """Evaluate from the perspective of the side to move."""
    raw = evaluate(board)
    return raw if board.turn == chess.WHITE else -raw


def quiescence(board: chess.Board, alpha: int, beta: int, depth_limit: int = 8) -> int:
    """Quiescence search: only consider captures to avoid horizon effect."""
    global nodes_searched
    nodes_searched += 1

    stand_pat = _eval_for_side(board)

    if depth_limit == 0:
        return stand_pat

    if stand_pat >= beta:
        return beta

    # Delta pruning: if we're far behind, skip captures that can't help
    BIG_DELTA = 900  # Queen value
    if stand_pat + BIG_DELTA < alpha:
        return alpha

    if stand_pat > alpha:
        alpha = stand_pat

    capture_moves = [m for m in board.legal_moves if board.is_capture(m)]
    capture_moves = order_moves(board, capture_moves)

    for move in capture_moves:
        board.push(move)
        score = -quiescence(board, -beta, -alpha, depth_limit - 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def negamax(board: chess.Board, depth: int, alpha: int, beta: int,
            do_null: bool = True, ply: int = 0) -> int:
    """Negamax search with alpha-beta pruning, null move, and quiescence."""
    global nodes_searched
    nodes_searched += 1

    if board.is_game_over():
        if board.is_checkmate():
            return -(MATE_SCORE - ply)  # Prefer shorter mates
        return 0  # Draw

    if depth <= 0:
        return quiescence(board, alpha, beta)

    in_check = board.is_check()

    # Check extension: search one deeper when in check
    if in_check:
        depth += 1

    # Null move pruning
    if (do_null and depth >= 3 and not in_check
            and _has_non_pawn_material(board)):
        board.push(chess.Move.null())
        score = -negamax(board, depth - 3, -beta, -beta + 1,
                         do_null=False, ply=ply + 1)
        board.pop()
        if score >= beta:
            return beta

    best_score = -INF
    orig_alpha = alpha
    moves = order_moves(board, depth=depth)

    for i, move in enumerate(moves):
        board.push(move)

        # Late move reductions: search later quiet moves at reduced depth
        if (i >= 4 and depth >= 3 and not in_check
                and not board.is_capture(move) and not move.promotion
                and not board.is_check()):
            # Reduced depth search
            score = -negamax(board, depth - 2, -beta, -alpha,
                             do_null=True, ply=ply + 1)
            # Re-search at full depth if it looks promising
            if score > alpha:
                score = -negamax(board, depth - 1, -beta, -alpha,
                                 do_null=True, ply=ply + 1)
        else:
            score = -negamax(board, depth - 1, -beta, -alpha,
                             do_null=True, ply=ply + 1)

        board.pop()

        if score > best_score:
            best_score = score

        if score > alpha:
            alpha = score
            record_history(move, board.turn, depth)

        if alpha >= beta:
            # Record killer move for quiet moves that cause cutoffs
            if not board.is_capture(move):
                record_killer(move, depth)
            break

    return best_score


def _has_non_pawn_material(board: chess.Board) -> bool:
    """Check if side to move has non-pawn material."""
    color = board.turn
    return bool(
        board.pieces(chess.KNIGHT, color) or
        board.pieces(chess.BISHOP, color) or
        board.pieces(chess.ROOK, color) or
        board.pieces(chess.QUEEN, color)
    )


def search(board: chess.Board, depth: int = 4, time_limit_ms: int = None) -> chess.Move:
    """Find the best move using iterative deepening.

    Args:
        board: Current position
        depth: Maximum search depth (used if no time_limit_ms)
        time_limit_ms: Time limit in milliseconds (overrides depth)

    Returns the best move found.
    """
    global nodes_searched
    nodes_searched = 0
    start_time = time.time()
    reset_move_order()

    best_move = None
    max_depth = depth if time_limit_ms is None else 50

    for current_depth in range(1, max_depth + 1):
        current_best = None
        current_best_score = -INF
        alpha = -INF
        beta = INF

        moves = order_moves(board, depth=current_depth)

        for move in moves:
            # Time check
            if time_limit_ms is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > time_limit_ms * 0.7:
                    break

            board.push(move)
            score = -negamax(board, current_depth - 1, -beta, -alpha, ply=1)
            board.pop()

            if score > current_best_score:
                current_best_score = score
                current_best = move
            if score > alpha:
                alpha = score

        if current_best is not None:
            best_move = current_best

        # Stop deepening if time is up
        if time_limit_ms is not None:
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > time_limit_ms * 0.5:
                break

        # Stop if we found a forced mate
        if abs(current_best_score) > MATE_SCORE - 100:
            break

    return best_move
