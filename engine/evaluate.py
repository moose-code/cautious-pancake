"""Position evaluation for CautiousPancake.

Returns a score in centipawns from white's perspective.
Positive = white is better, negative = black is better.
"""

import chess

# Material values in centipawns
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables (rank 8 at index 0, rank 1 at index 56)
PST_PAWN = (
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
)

PST_KNIGHT = (
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
)

PST_BISHOP = (
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
)

PST_ROOK = (
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
)

PST_QUEEN = (
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
)

PST_KING_MIDDLEGAME = (
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20,
)

PST_KING_ENDGAME = (
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50,
)

PST = {
    chess.PAWN: PST_PAWN,
    chess.KNIGHT: PST_KNIGHT,
    chess.BISHOP: PST_BISHOP,
    chess.ROOK: PST_ROOK,
    chess.QUEEN: PST_QUEEN,
}

# File masks for pawn structure evaluation (precomputed)
_FILE_MASKS = []
for f in range(8):
    mask = chess.BB_EMPTY
    for r in range(8):
        mask |= chess.BB_SQUARES[r * 8 + f]
    _FILE_MASKS.append(mask)

# Adjacent file masks
_ADJ_FILE_MASKS = []
for f in range(8):
    mask = chess.BB_EMPTY
    if f > 0:
        mask |= _FILE_MASKS[f - 1]
    if f < 7:
        mask |= _FILE_MASKS[f + 1]
    _ADJ_FILE_MASKS.append(mask)


def _mirror_square(sq: int) -> int:
    return sq ^ 56


def _is_endgame(board: chess.Board) -> bool:
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    if queens == 0:
        return True
    for color in [chess.WHITE, chess.BLACK]:
        if board.pieces(chess.QUEEN, color):
            minors = (len(board.pieces(chess.KNIGHT, color)) +
                      len(board.pieces(chess.BISHOP, color)) +
                      len(board.pieces(chess.ROOK, color)))
            if minors > 1:
                return False
    return True


def _eval_pawns(board: chess.Board) -> int:
    """Evaluate pawn structure: doubled, isolated, passed pawns."""
    score = 0
    white_pawns = board.pieces(chess.PAWN, chess.WHITE)
    black_pawns = board.pieces(chess.PAWN, chess.BLACK)
    white_pawn_bb = int(white_pawns)
    black_pawn_bb = int(black_pawns)

    for sq in white_pawns:
        f = chess.square_file(sq)
        r = chess.square_rank(sq)

        # Doubled pawns: another white pawn on same file
        file_pawns = white_pawn_bb & _FILE_MASKS[f]
        if bin(file_pawns).count('1') > 1:
            score -= 15

        # Isolated pawns: no friendly pawns on adjacent files
        if not (white_pawn_bb & _ADJ_FILE_MASKS[f]):
            score -= 20

        # Passed pawn: no enemy pawns can block or capture on the way
        is_passed = True
        check_mask = _FILE_MASKS[f] | _ADJ_FILE_MASKS[f]
        for check_rank in range(r + 1, 8):
            sq_check = check_rank * 8 + f
            # Check all squares on file and adjacent files ahead
            if black_pawn_bb & check_mask & _rank_mask(check_rank):
                is_passed = False
                break
        if is_passed:
            # Bonus increases with rank (closer to promotion)
            score += 20 + (r - 1) * 15

    for sq in black_pawns:
        f = chess.square_file(sq)
        r = chess.square_rank(sq)

        file_pawns = black_pawn_bb & _FILE_MASKS[f]
        if bin(file_pawns).count('1') > 1:
            score += 15

        if not (black_pawn_bb & _ADJ_FILE_MASKS[f]):
            score += 20

        is_passed = True
        check_mask = _FILE_MASKS[f] | _ADJ_FILE_MASKS[f]
        for check_rank in range(0, r):
            if white_pawn_bb & check_mask & _rank_mask(check_rank):
                is_passed = False
                break
        if is_passed:
            score -= 20 + (6 - r) * 15

    return score


def _rank_mask(rank: int) -> int:
    """Return bitmask for a given rank (0-7)."""
    return 0xFF << (rank * 8)


def _eval_king_safety(board: chess.Board, endgame: bool) -> int:
    """Evaluate king safety based on pawn shield and open files."""
    if endgame:
        return 0  # King safety less important in endgame

    score = 0

    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        king_sq = board.king(color)
        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)
        pawns = int(board.pieces(chess.PAWN, color))

        # Pawn shield: check pawns in front of king
        shield_bonus = 0
        shield_rank = king_rank + (1 if color == chess.WHITE else -1)
        if 0 <= shield_rank <= 7:
            for f in range(max(0, king_file - 1), min(8, king_file + 2)):
                sq = shield_rank * 8 + f
                if pawns & chess.BB_SQUARES[sq]:
                    shield_bonus += 15

        # Open file near king penalty
        open_file_penalty = 0
        for f in range(max(0, king_file - 1), min(8, king_file + 2)):
            file_mask = _FILE_MASKS[f]
            if not (pawns & file_mask):
                open_file_penalty += 20

        score += sign * (shield_bonus - open_file_penalty)

    return score


def _eval_rook_placement(board: chess.Board) -> int:
    """Bonus for rooks on open and semi-open files, and on 7th rank."""
    score = 0
    white_pawns = int(board.pieces(chess.PAWN, chess.WHITE))
    black_pawns = int(board.pieces(chess.PAWN, chess.BLACK))

    for sq in board.pieces(chess.ROOK, chess.WHITE):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        file_mask = _FILE_MASKS[f]
        if not (white_pawns & file_mask):
            if not (black_pawns & file_mask):
                score += 25  # Open file
            else:
                score += 12  # Semi-open
        if r == 6:  # 7th rank
            score += 20

    for sq in board.pieces(chess.ROOK, chess.BLACK):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        file_mask = _FILE_MASKS[f]
        if not (black_pawns & file_mask):
            if not (white_pawns & file_mask):
                score -= 25
            else:
                score -= 12
        if r == 1:  # 2nd rank (7th from black's perspective)
            score -= 20

    return score


def _eval_mobility(board: chess.Board) -> int:
    """Simple mobility bonus: count pseudo-legal moves for knights, bishops, rooks."""
    score = 0

    # Knight mobility
    for sq in board.pieces(chess.KNIGHT, chess.WHITE):
        score += 4 * bin(int(board.attacks(sq))).count('1')
    for sq in board.pieces(chess.KNIGHT, chess.BLACK):
        score -= 4 * bin(int(board.attacks(sq))).count('1')

    # Bishop mobility
    for sq in board.pieces(chess.BISHOP, chess.WHITE):
        score += 3 * bin(int(board.attacks(sq))).count('1')
    for sq in board.pieces(chess.BISHOP, chess.BLACK):
        score -= 3 * bin(int(board.attacks(sq))).count('1')

    # Rook mobility
    for sq in board.pieces(chess.ROOK, chess.WHITE):
        score += 2 * bin(int(board.attacks(sq))).count('1')
    for sq in board.pieces(chess.ROOK, chess.BLACK):
        score -= 2 * bin(int(board.attacks(sq))).count('1')

    return score


def _center_distance(sq: int) -> int:
    """Manhattan distance from center (3.5, 3.5). Higher = further from center."""
    f = chess.square_file(sq)
    r = chess.square_rank(sq)
    return abs(f - 3) + abs(r - 3)  # Simplified, max=6


def _king_distance(sq1: int, sq2: int) -> int:
    """Chebyshev distance between two squares."""
    f1, r1 = chess.square_file(sq1), chess.square_rank(sq1)
    f2, r2 = chess.square_file(sq2), chess.square_rank(sq2)
    return max(abs(f1 - f2), abs(r1 - r2))


def _eval_mopup(board: chess.Board, material_score: int) -> int:
    """In winning endgames, incentivize driving the losing king to the corner
    and bringing our king close to theirs."""
    # Only apply when one side has significant material advantage
    if abs(material_score) < 200:
        return 0

    if material_score > 0:
        # White is winning - push black king to corner
        losing_king = board.king(chess.BLACK)
        winning_king = board.king(chess.WHITE)
    else:
        # Black is winning - push white king to corner
        losing_king = board.king(chess.WHITE)
        winning_king = board.king(chess.BLACK)

    # Reward: losing king far from center + kings close together
    corner_bonus = _center_distance(losing_king) * 10
    close_bonus = (7 - _king_distance(winning_king, losing_king)) * 5

    mopup = corner_bonus + close_bonus

    return mopup if material_score > 0 else -mopup


def evaluate(board: chess.Board) -> int:
    """Evaluate a position from white's perspective."""
    if board.is_checkmate():
        return -30000 if board.turn == chess.WHITE else 30000

    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    # Draw by repetition or 50-move rule
    if board.can_claim_draw():
        return 0

    score = 0
    endgame = _is_endgame(board)
    king_pst = PST_KING_ENDGAME if endgame else PST_KING_MIDDLEGAME

    # Material + piece-square tables
    for piece_type in PIECE_VALUES:
        pst = king_pst if piece_type == chess.KING else PST.get(piece_type)

        for sq in board.pieces(piece_type, chess.WHITE):
            score += PIECE_VALUES[piece_type]
            if pst:
                score += pst[_mirror_square(sq)]

        for sq in board.pieces(piece_type, chess.BLACK):
            score -= PIECE_VALUES[piece_type]
            if pst:
                score -= pst[sq]

    # Bishop pair bonus
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 30
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 30

    # Pawn structure
    score += _eval_pawns(board)

    # King safety
    score += _eval_king_safety(board, endgame)

    # Rook placement
    score += _eval_rook_placement(board)

    # Mobility
    score += _eval_mobility(board)

    # Endgame mop-up: when winning, drive enemy king to corner
    if endgame:
        score += _eval_mopup(board, score)

    return score
