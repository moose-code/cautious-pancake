"""Search algorithm for CautiousPancake.

Negamax with alpha-beta, quiescence, iterative deepening, transposition table,
null move pruning, LMR, LMP, futility pruning, aspiration windows,
killer moves, history heuristic, and PV ordering.
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
TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2
_tt: dict[int, tuple[int, int, int, chess.Move | None]] = {}
TT_MAX_SIZE = 1 << 20

# Stats
nodes_searched = 0

# Futility pruning margins by depth
_FUTILITY_MARGIN = [0, 200, 350, 500]

# Late move pruning: max quiet moves to search at low depths
_LMP_THRESHOLD = [0, 5, 8, 14]


def _eval_for_side(board: chess.Board) -> int:
    """Evaluate from the perspective of the side to move."""
    raw = evaluate(board)
    return raw if board.turn == chess.WHITE else -raw


def _tt_lookup(key: int, depth: int, alpha: int, beta: int):
    """Look up position in transposition table."""
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
    return None, tt_move


def _tt_store(key: int, depth: int, score: int, flag: int, best_move: chess.Move | None):
    """Store position in transposition table. Depth-preferred replacement."""
    existing = _tt.get(key)
    # Replace if: no entry, deeper search, or same depth (fresher data)
    if existing is None or depth >= existing[0]:
        if len(_tt) >= TT_MAX_SIZE and existing is None:
            # Evict ~25% of entries when full
            keys = list(_tt.keys())
            for k in keys[:len(keys) // 4]:
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
    """Negamax with alpha-beta, TT, null move, LMR, LMP, futility, quiescence."""
    global nodes_searched
    nodes_searched += 1

    # Draw detection (repetition, 50-move, insufficient material)
    if board.is_repetition(2) or board.is_fifty_moves():
        return 0

    if board.is_game_over():
        if board.is_checkmate():
            return -(MATE_SCORE - ply)
        return 0

    # Mate distance pruning: if we already found a shorter mate, prune
    if MATE_SCORE - ply <= alpha:
        return alpha
    if -(MATE_SCORE - ply) >= beta:
        return beta

    # TT lookup
    tt_key = chess.polyglot.zobrist_hash(board)
    tt_score, tt_move = _tt_lookup(tt_key, depth, alpha, beta)
    if tt_score is not None and ply > 0:
        return tt_score

    if depth <= 0:
        return quiescence(board, alpha, beta)

    in_check = board.is_check()

    # Check extension
    if in_check:
        depth += 1

    # Get static eval for pruning decisions (cache it)
    static_eval = _eval_for_side(board)

    # Razoring: at low depth, if static eval is far below alpha, drop to qsearch
    if (depth <= 2 and not in_check and abs(alpha) < MATE_SCORE - 100
            and static_eval + 300 * depth < alpha):
        score = quiescence(board, alpha, beta)
        if score <= alpha:
            return score

    # Null move pruning
    if (do_null and depth >= 3 and not in_check
            and _has_non_pawn_material(board)
            and static_eval >= beta):
        board.push(chess.Move.null())
        r = 3 if depth >= 6 else 2
        score = -negamax(board, depth - 1 - r, -beta, -beta + 1,
                         do_null=False, ply=ply + 1)
        board.pop()
        if score >= beta:
            return beta

    # Reverse futility pruning
    if (depth <= 3 and not in_check and abs(beta) < MATE_SCORE - 100):
        if static_eval - _FUTILITY_MARGIN[depth] >= beta:
            return static_eval - _FUTILITY_MARGIN[depth]

    best_score = -INF
    best_move = None
    orig_alpha = alpha

    moves = order_moves(board, depth=depth, tt_move=tt_move)

    quiet_moves_searched = 0
    moves_searched = 0

    for move in moves:
        is_capture = board.is_capture(move)
        is_promotion = bool(move.promotion)
        is_quiet = not is_capture and not is_promotion

        # Late move pruning: skip late quiet moves at shallow depths
        if (is_quiet and depth <= 3 and not in_check
                and quiet_moves_searched >= _LMP_THRESHOLD[depth]
                and abs(alpha) < MATE_SCORE - 100):
            continue

        # Futility pruning: at shallow depths, skip quiet moves that can't improve alpha
        if (is_quiet and depth <= 3 and not in_check
                and moves_searched > 0
                and abs(alpha) < MATE_SCORE - 100
                and static_eval + _FUTILITY_MARGIN[depth] <= alpha):
            if is_quiet:
                quiet_moves_searched += 1
            continue

        board.push(move)

        # Check if this move gives check (for LMR decisions)
        gives_check = board.is_check()

        # Late move reductions
        if (moves_searched >= 3 and depth >= 3 and not in_check
                and is_quiet and not gives_check):
            # Logarithmic reduction
            if moves_searched >= 8:
                reduction = 2 + (1 if moves_searched >= 16 else 0)
            elif moves_searched >= 4:
                reduction = 1
            else:
                reduction = 1

            score = -negamax(board, depth - 1 - reduction, -beta, -alpha,
                             do_null=True, ply=ply + 1)
            # Re-search at full depth if it looks promising
            if score > alpha:
                score = -negamax(board, depth - 1, -beta, -alpha,
                                 do_null=True, ply=ply + 1)
        else:
            score = -negamax(board, depth - 1, -beta, -alpha,
                             do_null=True, ply=ply + 1)

        board.pop()
        moves_searched += 1
        if is_quiet:
            quiet_moves_searched += 1

        if score > best_score:
            best_score = score
            best_move = move

        if score > alpha:
            alpha = score
            record_history(move, board.turn, depth)

        if alpha >= beta:
            if is_quiet:
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
    """Find the best move using iterative deepening with aspiration windows."""
    global nodes_searched
    nodes_searched = 0
    start_time = time.time()
    reset_move_order()
    # Don't clear TT between moves - it's valuable across the game
    # Only clear at start of new game (via UCI ucinewgame)

    best_move = None
    prev_score = 0
    max_depth = depth if time_limit_ms is None else 50

    for current_depth in range(1, max_depth + 1):
        # Aspiration windows: search with a narrow window around previous score
        if current_depth >= 4:
            window = 50
            alpha = prev_score - window
            beta = prev_score + window
        else:
            alpha = -INF
            beta = INF

        current_best = None
        current_best_score = -INF

        # Aspiration window search with re-search on fail
        for attempt in range(3):
            current_best = None
            current_best_score = -INF
            search_alpha = alpha

            tt_key = chess.polyglot.zobrist_hash(board)
            _, pv_move = _tt_lookup(tt_key, 0, alpha, beta)
            moves = order_moves(board, depth=current_depth, tt_move=pv_move)

            for move in moves:
                if time_limit_ms is not None:
                    elapsed_ms = (time.time() - start_time) * 1000
                    if elapsed_ms > time_limit_ms * 0.7:
                        break

                board.push(move)
                score = -negamax(board, current_depth - 1, -beta, -search_alpha, ply=1)
                board.pop()

                if score > current_best_score:
                    current_best_score = score
                    current_best = move
                if score > search_alpha:
                    search_alpha = score

            # Check if we fell outside the aspiration window
            if current_best_score <= alpha:
                alpha = -INF  # Re-search with full window below
            elif current_best_score >= beta:
                beta = INF  # Re-search with full window above
            else:
                break  # Score is within window, done

        if current_best is not None:
            best_move = current_best
            prev_score = current_best_score

        if time_limit_ms is not None:
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > time_limit_ms * 0.5:
                break

        if abs(current_best_score) > MATE_SCORE - 100:
            break

    return best_move


def clear_tt():
    """Clear the transposition table (call on ucinewgame)."""
    _tt.clear()
