"""Search algorithm for CautiousPancake.

Negamax with alpha-beta, quiescence, iterative deepening, transposition table,
null move pruning, LMR, killer moves, history heuristic, and PV ordering.
"""

import time
import chess
import chess.polyglot
from engine.evaluate import evaluate
from engine.move_order import order_moves, record_killer, record_history, reset as reset_move_order

# Constants
MATE_SCORE = 30000
INF = 99999

# Transposition table
# Key: zobrist hash, Value: (depth, score, flag, best_move)
# Flags: 0 = exact, 1 = lower bound (beta cutoff), 2 = upper bound (failed low)
TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2
_tt: dict[int, tuple[int, int, int, chess.Move | None]] = {}
TT_MAX_SIZE = 1 << 20  # ~1M entries

# Stats
nodes_searched = 0


def _eval_for_side(board: chess.Board) -> int:
    """Evaluate from the perspective of the side to move."""
    raw = evaluate(board)
    return raw if board.turn == chess.WHITE else -raw


def _tt_lookup(key: int, depth: int, alpha: int, beta: int):
    """Look up position in transposition table. Returns (score, best_move) or (None, best_move)."""
    entry = _tt.get(key)
    if entry is None:
        return None, None
    tt_depth, tt_score, tt_flag, tt_move = entry
    if tt_depth >= depth:
        if tt_flag == TT_EXACT:
            return tt_score, tt_move
        elif tt_flag == TT_LOWER and tt_score >= beta:
            return tt_score, tt_move
        elif tt_flag == TT_UPPER and tt_score <= alpha:
            return tt_score, tt_move
    return None, tt_move  # Return best move even if depth insufficient


def _tt_store(key: int, depth: int, score: int, flag: int, best_move: chess.Move | None):
    """Store position in transposition table."""
    # Always replace (simple scheme)
    if len(_tt) >= TT_MAX_SIZE:
        # Clear half the table when full (age-based would be better)
        keys = list(_tt.keys())
        for k in keys[:len(keys) // 2]:
            del _tt[k]
    _tt[key] = (depth, score, flag, best_move)


def quiescence(board: chess.Board, alpha: int, beta: int, depth_limit: int = 8) -> int:
    """Quiescence search: only consider captures to avoid horizon effect."""
    global nodes_searched
    nodes_searched += 1

    stand_pat = _eval_for_side(board)

    if depth_limit == 0:
        return stand_pat

    if stand_pat >= beta:
        return beta

    # Delta pruning
    if stand_pat + 900 < alpha:
        return alpha

    if stand_pat > alpha:
        alpha = stand_pat

    capture_moves = [m for m in board.legal_moves if board.is_capture(m)]
    capture_moves = order_moves(board, capture_moves)

    for move in capture_moves:
        # SEE-like pruning: skip captures of higher value pieces by lower value
        # (simplified: skip if captured piece value < attacker value - margin)
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
    """Negamax with alpha-beta, TT, null move, LMR, and quiescence."""
    global nodes_searched
    nodes_searched += 1

    if board.is_game_over():
        if board.is_checkmate():
            return -(MATE_SCORE - ply)
        return 0  # Draw

    # TT lookup
    tt_key = chess.polyglot.zobrist_hash(board)
    tt_score, tt_move = _tt_lookup(tt_key, depth, alpha, beta)
    if tt_score is not None:
        return tt_score

    if depth <= 0:
        return quiescence(board, alpha, beta)

    in_check = board.is_check()

    # Check extension
    if in_check:
        depth += 1

    # Null move pruning
    if (do_null and depth >= 3 and not in_check
            and _has_non_pawn_material(board)
            and _eval_for_side(board) >= beta):
        board.push(chess.Move.null())
        # Adaptive R: reduce more at higher depths
        r = 3 if depth >= 6 else 2
        score = -negamax(board, depth - 1 - r, -beta, -beta + 1,
                         do_null=False, ply=ply + 1)
        board.pop()
        if score >= beta:
            return beta

    # Reverse futility pruning (static eval pruning)
    if (depth <= 3 and not in_check and abs(beta) < MATE_SCORE - 100):
        static_eval = _eval_for_side(board)
        margin = 120 * depth
        if static_eval - margin >= beta:
            return static_eval - margin

    best_score = -INF
    best_move = None
    orig_alpha = alpha

    # Order moves, with TT move first if available
    moves = order_moves(board, depth=depth, tt_move=tt_move)

    moves_searched = 0
    for move in moves:
        board.push(move)

        # Late move reductions
        if (moves_searched >= 4 and depth >= 3 and not in_check
                and not board.is_capture(move) and not move.promotion
                and not board.is_check()):
            # Reduce more for later moves
            reduction = 1 if moves_searched < 8 else 2
            score = -negamax(board, depth - 1 - reduction, -beta, -alpha,
                             do_null=True, ply=ply + 1)
            if score > alpha:
                score = -negamax(board, depth - 1, -beta, -alpha,
                                 do_null=True, ply=ply + 1)
        else:
            score = -negamax(board, depth - 1, -beta, -alpha,
                             do_null=True, ply=ply + 1)

        board.pop()
        moves_searched += 1

        if score > best_score:
            best_score = score
            best_move = move

        if score > alpha:
            alpha = score
            record_history(move, board.turn, depth)

        if alpha >= beta:
            if not board.is_capture(move):
                record_killer(move, depth)
            break

    # Store in TT
    if best_score <= orig_alpha:
        tt_flag = TT_UPPER
    elif best_score >= beta:
        tt_flag = TT_LOWER
    else:
        tt_flag = TT_EXACT
    _tt_store(tt_key, depth, best_score, tt_flag, best_move)

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


def search(board: chess.Board, depth: int = 5, time_limit_ms: int = None) -> chess.Move:
    """Find the best move using iterative deepening with TT and PV ordering.

    Default depth bumped to 5 now that TT makes deeper search feasible.
    """
    global nodes_searched
    nodes_searched = 0
    start_time = time.time()
    reset_move_order()
    _tt.clear()

    best_move = None
    max_depth = depth if time_limit_ms is None else 50

    for current_depth in range(1, max_depth + 1):
        current_best = None
        current_best_score = -INF
        alpha = -INF
        beta = INF

        # Use TT move from previous iteration for PV ordering
        tt_key = chess.polyglot.zobrist_hash(board)
        _, pv_move = _tt_lookup(tt_key, 0, alpha, beta)
        moves = order_moves(board, depth=current_depth, tt_move=pv_move)

        for move in moves:
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

        if time_limit_ms is not None:
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > time_limit_ms * 0.5:
                break

        if abs(current_best_score) > MATE_SCORE - 100:
            break

    return best_move
