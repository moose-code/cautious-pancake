"""Search algorithm for CautiousPancake.

PVS with alpha-beta, quiescence+SEE, iterative deepening, transposition table,
null move pruning, LMR, LMP, futility pruning, aspiration windows,
killer moves, history heuristic, countermove heuristic, and PV ordering.
"""

import math
import time
import chess
from engine.evaluate import evaluate, PIECE_VALUES as EVAL_PIECE_VALUES
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

# Countermove table: the move that refuted the opponent's last move
_countermoves: dict[tuple[bool, int, int], chess.Move] = {}

# Stats
nodes_searched = 0

# Futility pruning margins by depth
_FUTILITY_MARGIN = [0, 200, 350, 500]

# Late move pruning: max quiet moves to search at low depths
_LMP_THRESHOLD = [0, 6, 10, 16]

# SEE piece values for static exchange evaluation
_SEE_VALUES = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000,
}


def _eval_for_side(board: chess.Board) -> int:
    """Evaluate from the perspective of the side to move."""
    raw = evaluate(board)
    return raw if board.turn == chess.WHITE else -raw


def _see(board: chess.Board, move: chess.Move) -> int:
    """Static Exchange Evaluation - estimate if a capture sequence is winning.

    Returns approximate material gain/loss of the capture.
    Simplified version: just check if the immediate recapture loses.
    """
    if not board.is_capture(move):
        return 0

    # Value of captured piece
    victim_type = board.piece_type_at(move.to_square)
    if victim_type is None:
        # En passant
        return 100

    attacker_type = board.piece_type_at(move.from_square)
    gain = _SEE_VALUES.get(victim_type, 0)

    # Check if the target square is defended
    board.push(move)
    if board.is_attacked_by(board.turn, move.to_square):
        # We might lose our piece
        gain -= _SEE_VALUES.get(attacker_type, 0)
    board.pop()

    return gain


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
    if existing is None or depth >= existing[0]:
        if len(_tt) >= TT_MAX_SIZE and existing is None:
            keys = list(_tt.keys())
            for k in keys[:len(keys) // 4]:
                del _tt[k]
        _tt[key] = (depth, score, flag, best_move)


def quiescence(board: chess.Board, alpha: int, beta: int, depth_limit: int = 8) -> int:
    """Quiescence search with SEE pruning and TT."""
    global nodes_searched
    nodes_searched += 1

    # TT lookup in quiescence
    tt_key = board._transposition_key()
    entry = _tt.get(tt_key)
    if entry is not None:
        tt_depth, tt_score, tt_flag, _ = entry
        if tt_flag == TT_EXACT:
            return tt_score
        elif tt_flag == TT_LOWER and tt_score >= beta:
            return tt_score
        elif tt_flag == TT_UPPER and tt_score <= alpha:
            return tt_score

    stand_pat = _eval_for_side(board)

    if depth_limit == 0:
        return stand_pat

    if stand_pat >= beta:
        return beta

    # Delta pruning
    if stand_pat + 900 < alpha:
        return alpha

    orig_alpha = alpha
    if stand_pat > alpha:
        alpha = stand_pat

    best_score = stand_pat

    # Use generate_legal_captures() - faster than filtering legal_moves
    capture_moves = list(board.generate_legal_captures())
    capture_moves = order_moves(board, capture_moves)

    for move in capture_moves:
        # SEE pruning: skip clearly losing captures
        if _see(board, move) < -50:
            continue

        board.push(move)
        score = -quiescence(board, -beta, -alpha, depth_limit - 1)
        board.pop()

        if score > best_score:
            best_score = score

        if score >= beta:
            # Store lower bound in TT
            _tt_store(tt_key, -1, score, TT_LOWER, move)
            return beta
        if score > alpha:
            alpha = score

    # Store in TT
    if best_score <= orig_alpha:
        _tt_store(tt_key, -1, best_score, TT_UPPER, None)
    elif best_score > orig_alpha:
        _tt_store(tt_key, -1, best_score, TT_EXACT, None)

    return alpha


def negamax(board: chess.Board, depth: int, alpha: int, beta: int,
            do_null: bool = True, ply: int = 0) -> int:
    """PVS with alpha-beta, TT, null move, LMR, LMP, futility, quiescence."""
    global nodes_searched
    nodes_searched += 1

    # Draw detection
    if board.is_repetition(2) or board.is_fifty_moves():
        return 0

    # Mate distance pruning
    if MATE_SCORE - ply <= alpha:
        return alpha
    if -(MATE_SCORE - ply) >= beta:
        return beta

    # TT lookup
    tt_key = board._transposition_key()
    tt_score, tt_move = _tt_lookup(tt_key, depth, alpha, beta)
    if tt_score is not None and ply > 0:
        return tt_score

    if depth <= 0:
        return quiescence(board, alpha, beta)

    in_check = board.is_check()
    is_pv = beta - alpha > 1  # Are we in a PV node?

    # Check extension
    if in_check:
        depth += 1

    # Static eval for pruning
    static_eval = _eval_for_side(board)

    # Razoring
    if (depth <= 2 and not in_check and not is_pv
            and abs(alpha) < MATE_SCORE - 100
            and static_eval + 300 * depth < alpha):
        score = quiescence(board, alpha, beta)
        if score <= alpha:
            return score

    # Null move pruning
    if (do_null and depth >= 3 and not in_check and not is_pv
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
    if (depth <= 3 and not in_check and not is_pv
            and abs(beta) < MATE_SCORE - 100):
        if static_eval - _FUTILITY_MARGIN[depth] >= beta:
            return static_eval - _FUTILITY_MARGIN[depth]

    # Internal Iterative Deepening: if no TT move at PV node, do shallow search
    if tt_move is None and is_pv and depth >= 4:
        negamax(board, depth - 2, alpha, beta, do_null=False, ply=ply)
        _, tt_move = _tt_lookup(tt_key, 0, alpha, beta)

    best_score = -INF
    best_move = None
    orig_alpha = alpha

    # Get countermove for the opponent's last move
    countermove = None
    if board.move_stack:
        last = board.move_stack[-1]
        cm_key = (not board.turn, last.from_square, last.to_square)
        countermove = _countermoves.get(cm_key)

    moves = order_moves(board, depth=depth, tt_move=tt_move, countermove=countermove)

    # Singular extension: check if TT move is significantly better
    singular_move = None
    if (tt_move is not None and depth >= 6 and not in_check
            and ply > 0):
        entry = _tt.get(tt_key)
        if entry is not None and entry[0] >= depth - 3 and entry[2] != TT_UPPER:
            tt_val = entry[1]
            s_beta = tt_val - 50
            # Search all moves except TT move with reduced depth
            s_score = -INF
            for m in moves:
                if m == tt_move:
                    continue
                board.push(m)
                s = -negamax(board, depth // 2 - 1, s_beta - 1, s_beta,
                             do_null=False, ply=ply + 1)
                board.pop()
                if s >= s_beta:
                    s_score = s
                    break
            if s_score < s_beta:
                singular_move = tt_move

    quiet_moves_searched = 0
    moves_searched = 0

    for move in moves:
        is_capture = board.is_capture(move)
        is_promotion = bool(move.promotion)
        is_quiet = not is_capture and not is_promotion

        # Late move pruning
        if (is_quiet and depth <= 3 and not in_check and not is_pv
                and quiet_moves_searched >= _LMP_THRESHOLD[depth]
                and abs(alpha) < MATE_SCORE - 100):
            continue

        # Futility pruning
        if (is_quiet and depth <= 3 and not in_check and not is_pv
                and moves_searched > 0
                and abs(alpha) < MATE_SCORE - 100
                and static_eval + _FUTILITY_MARGIN[depth] <= alpha):
            quiet_moves_searched += 1
            continue

        # SEE pruning for bad captures at low depths
        if (is_capture and depth <= 2 and not in_check
                and _see(board, move) < -100):
            continue

        # Singular extension: extend TT move if it's singular
        extension = 0
        if move == singular_move:
            extension = 1

        board.push(move)
        gives_check = board.is_check()

        # PVS: search first move with full window, rest with null window
        if moves_searched == 0:
            # First move (likely PV): full window search
            score = -negamax(board, depth - 1 + extension, -beta, -alpha,
                             do_null=True, ply=ply + 1)
        else:
            # Late move reductions: log-based formula for quiet non-checking moves
            reduction = 0
            if (moves_searched >= 3 and depth >= 3 and not in_check
                    and is_quiet and not gives_check):
                reduction = int(0.75 + math.log(depth) * math.log(moves_searched) / 2.25)
                # Reduce less in PV nodes
                if is_pv and reduction > 1:
                    reduction -= 1
                # Don't reduce to 0 or below
                reduction = min(reduction, depth - 2)
                reduction = max(reduction, 0)

            # Null window search (scout)
            score = -negamax(board, depth - 1 - reduction, -alpha - 1, -alpha,
                             do_null=True, ply=ply + 1)

            # Re-search with full window if scout found something better
            if score > alpha and (reduction > 0 or score < beta):
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
                # Record countermove
                if board.move_stack:
                    last = board.move_stack[-1]
                    cm_key = (not board.turn, last.from_square, last.to_square)
                    _countermoves[cm_key] = move
            break

    # No legal moves: checkmate or stalemate
    if moves_searched == 0:
        if in_check:
            return -(MATE_SCORE - ply)
        return 0  # Stalemate

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
    """Find the best move using iterative deepening with aspiration windows + PVS."""
    global nodes_searched
    nodes_searched = 0
    start_time = time.time()
    reset_move_order()
    _countermoves.clear()

    best_move = None
    prev_score = 0
    max_depth = depth if time_limit_ms is None else 50

    for current_depth in range(1, max_depth + 1):
        # Aspiration windows
        if current_depth >= 4:
            window = 40
            alpha = prev_score - window
            beta = prev_score + window
        else:
            alpha = -INF
            beta = INF

        current_best = None
        current_best_score = -INF

        for attempt in range(3):
            current_best = None
            current_best_score = -INF
            search_alpha = alpha

            tt_key = board._transposition_key()
            _, pv_move = _tt_lookup(tt_key, 0, alpha, beta)
            moves = order_moves(board, depth=current_depth, tt_move=pv_move)

            for i, move in enumerate(moves):
                if time_limit_ms is not None:
                    elapsed_ms = (time.time() - start_time) * 1000
                    if elapsed_ms > time_limit_ms * 0.7:
                        break

                board.push(move)

                # PVS at root too
                if i == 0:
                    score = -negamax(board, current_depth - 1, -beta, -search_alpha, ply=1)
                else:
                    score = -negamax(board, current_depth - 1, -search_alpha - 1, -search_alpha, ply=1)
                    if score > search_alpha and score < beta:
                        score = -negamax(board, current_depth - 1, -beta, -search_alpha, ply=1)

                board.pop()

                if score > current_best_score:
                    current_best_score = score
                    current_best = move
                if score > search_alpha:
                    search_alpha = score

            if current_best_score <= alpha:
                alpha = -INF
            elif current_best_score >= beta:
                beta = INF
            else:
                break

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
    _countermoves.clear()
