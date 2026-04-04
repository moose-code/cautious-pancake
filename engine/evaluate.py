"""Position evaluation for CautiousPancake.

Returns a score in centipawns from white's perspective.
Positive = white is better, negative = black is better.

Optimized: uses direct bitboard access instead of board.pieces(),
int.bit_count() instead of bin().count('1'), and pawn hash caching.
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

# File masks for pawn structure evaluation
_FILE_MASKS = []
for f in range(8):
    mask = 0
    for r in range(8):
        mask |= 1 << (r * 8 + f)
    _FILE_MASKS.append(mask)

_ADJ_FILE_MASKS = []
for f in range(8):
    mask = 0
    if f > 0:
        mask |= _FILE_MASKS[f - 1]
    if f < 7:
        mask |= _FILE_MASKS[f + 1]
    _ADJ_FILE_MASKS.append(mask)

# Precomputed rank masks
_RANK_MASKS = [0xFF << (r * 8) for r in range(8)]

# Precomputed forward span masks for passed pawn detection
# _FORWARD_SPAN_WHITE[sq] = all squares on file and adjacent files, ahead of sq (for white)
_FORWARD_SPAN_WHITE = [0] * 64
_FORWARD_SPAN_BLACK = [0] * 64
for sq in range(64):
    f = sq % 8
    r = sq // 8
    mask_w = 0
    mask_b = 0
    check_files = _FILE_MASKS[f] | _ADJ_FILE_MASKS[f]
    for cr in range(r + 1, 8):
        mask_w |= check_files & _RANK_MASKS[cr]
    for cr in range(0, r):
        mask_b |= check_files & _RANK_MASKS[cr]
    _FORWARD_SPAN_WHITE[sq] = mask_w
    _FORWARD_SPAN_BLACK[sq] = mask_b

# Pawn hash cache (64k entries)
_PAWN_CACHE: dict[tuple[int, int], int] = {}
_PAWN_CACHE_MAX = 1 << 16

# Tempo bonus
TEMPO_BONUS = 12


def _popcount(bb: int) -> int:
    """Fast popcount using int.bit_count() (Python 3.10+)."""
    return bb.bit_count()


def _scan_squares(bb: int):
    """Iterate over set bits in a bitboard, yielding square indices."""
    while bb:
        sq = (bb & -bb).bit_length() - 1
        yield sq
        bb &= bb - 1


def _mirror_square(sq: int) -> int:
    return sq ^ 56


def _is_endgame(board: chess.Board) -> bool:
    white_occ = board.occupied_co[chess.WHITE]
    black_occ = board.occupied_co[chess.BLACK]
    queens = _popcount(board.queens)
    if queens == 0:
        return True
    # Queen + 1 or fewer non-pawn pieces per side
    for occ in [white_occ, black_occ]:
        if board.queens & occ:
            minors = _popcount((board.knights | board.bishops | board.rooks) & occ)
            if minors > 1:
                return False
    return True


def _eval_pawns_inner(white_pawn_bb: int, black_pawn_bb: int) -> int:
    """Evaluate pawn structure. Pure function on pawn bitboards for caching."""
    score = 0

    # White pawns
    bb = white_pawn_bb
    while bb:
        sq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        f = sq % 8
        r = sq // 8

        # Doubled pawns
        if _popcount(white_pawn_bb & _FILE_MASKS[f]) > 1:
            score -= 15

        # Isolated pawns
        if not (white_pawn_bb & _ADJ_FILE_MASKS[f]):
            score -= 20

        # Passed pawn
        if not (black_pawn_bb & _FORWARD_SPAN_WHITE[sq]):
            bonus = 20 + (r - 1) * 18
            # Connected passer
            if white_pawn_bb & _ADJ_FILE_MASKS[f] & _RANK_MASKS[r]:
                bonus += 15
            # Protected passer
            if r > 0 and (white_pawn_bb & _ADJ_FILE_MASKS[f] & _RANK_MASKS[r - 1]):
                bonus += 10
            score += bonus

    # Black pawns
    bb = black_pawn_bb
    while bb:
        sq = (bb & -bb).bit_length() - 1
        bb &= bb - 1
        f = sq % 8
        r = sq // 8

        if _popcount(black_pawn_bb & _FILE_MASKS[f]) > 1:
            score += 15

        if not (black_pawn_bb & _ADJ_FILE_MASKS[f]):
            score += 20

        if not (white_pawn_bb & _FORWARD_SPAN_BLACK[sq]):
            bonus = 20 + (6 - r) * 18
            if black_pawn_bb & _ADJ_FILE_MASKS[f] & _RANK_MASKS[r]:
                bonus += 15
            if r < 7 and (black_pawn_bb & _ADJ_FILE_MASKS[f] & _RANK_MASKS[r + 1]):
                bonus += 10
            score -= bonus

    return score


def _eval_pawns(board: chess.Board) -> int:
    """Evaluate pawn structure with caching."""
    white_bb = board.pawns & board.occupied_co[chess.WHITE]
    black_bb = board.pawns & board.occupied_co[chess.BLACK]
    key = (white_bb, black_bb)

    cached = _PAWN_CACHE.get(key)
    if cached is not None:
        return cached

    score = _eval_pawns_inner(white_bb, black_bb)

    if len(_PAWN_CACHE) >= _PAWN_CACHE_MAX:
        _PAWN_CACHE.clear()
    _PAWN_CACHE[key] = score
    return score


# King ring: squares adjacent to king (precomputed)
_KING_RING = [0] * 64
for _sq in range(64):
    _kr = 0
    _f, _r = _sq % 8, _sq // 8
    for _df in range(-1, 2):
        for _dr in range(-1, 2):
            _nf, _nr = _f + _df, _r + _dr
            if 0 <= _nf < 8 and 0 <= _nr < 8:
                _kr |= 1 << (_nr * 8 + _nf)
    _KING_RING[_sq] = _kr

# Attack weights by piece type for king safety
_ATTACK_WEIGHT = {
    chess.KNIGHT: 2,
    chess.BISHOP: 2,
    chess.ROOK: 3,
    chess.QUEEN: 5,
}


def _eval_king_safety(board: chess.Board, endgame: bool) -> int:
    if endgame:
        return 0

    score = 0
    white_occ = board.occupied_co[chess.WHITE]
    black_occ = board.occupied_co[chess.BLACK]
    white_pawns = board.pawns & white_occ
    black_pawns = board.pawns & black_occ

    for color_idx, enemy_occ, pawns, sign in [
        (chess.WHITE, black_occ, white_pawns, 1),
        (chess.BLACK, white_occ, black_pawns, -1),
    ]:
        king_sq = board.king(color_idx)
        king_file = chess.square_file(king_sq)
        king_ring = _KING_RING[king_sq]

        # Pawn shield bonus
        shield_bonus = 0
        king_rank = chess.square_rank(king_sq)
        shield_rank = king_rank + (1 if color_idx == chess.WHITE else -1)
        if 0 <= shield_rank <= 7:
            for f in range(max(0, king_file - 1), min(8, king_file + 2)):
                if pawns & (1 << (shield_rank * 8 + f)):
                    shield_bonus += 15

        # Open file penalty
        open_file_penalty = 0
        for f in range(max(0, king_file - 1), min(8, king_file + 2)):
            if not (pawns & _FILE_MASKS[f]):
                open_file_penalty += 20

        # Attack-unit system: count enemy pieces attacking king ring
        attack_units = 0
        attacker_count = 0
        for piece_type, weight in _ATTACK_WEIGHT.items():
            bb_attr = {chess.KNIGHT: 'knights', chess.BISHOP: 'bishops',
                       chess.ROOK: 'rooks', chess.QUEEN: 'queens'}[piece_type]
            for sq in _scan_squares(getattr(board, bb_attr) & enemy_occ):
                attacks = board.attacks_mask(sq)
                if attacks & king_ring:
                    attack_units += weight
                    attacker_count += 1

        # Quadratic scaling of attack danger
        attack_penalty = 0
        if attacker_count >= 2:
            attack_penalty = attack_units * attack_units // 2

        score += sign * (shield_bonus - open_file_penalty - attack_penalty)

    return score


def _eval_rook_placement(board: chess.Board) -> int:
    score = 0
    white_occ = board.occupied_co[chess.WHITE]
    black_occ = board.occupied_co[chess.BLACK]
    white_pawns = board.pawns & white_occ
    black_pawns = board.pawns & black_occ
    white_rooks = board.rooks & white_occ
    black_rooks = board.rooks & black_occ

    for sq in _scan_squares(white_rooks):
        f = sq % 8
        r = sq // 8
        fm = _FILE_MASKS[f]
        if not (white_pawns & fm):
            score += 25 if not (black_pawns & fm) else 12
        if r == 6:
            score += 20

    for sq in _scan_squares(black_rooks):
        f = sq % 8
        r = sq // 8
        fm = _FILE_MASKS[f]
        if not (black_pawns & fm):
            score -= 25 if not (white_pawns & fm) else 12
        if r == 1:
            score -= 20

    return score


def _eval_mobility(board: chess.Board) -> int:
    """Mobility using int.bit_count() and direct bitboard access."""
    score = 0
    white_occ = board.occupied_co[chess.WHITE]
    black_occ = board.occupied_co[chess.BLACK]

    # Knights
    for sq in _scan_squares(board.knights & white_occ):
        score += 4 * int(board.attacks_mask(sq)).bit_count()
    for sq in _scan_squares(board.knights & black_occ):
        score -= 4 * int(board.attacks_mask(sq)).bit_count()

    # Bishops
    for sq in _scan_squares(board.bishops & white_occ):
        score += 3 * int(board.attacks_mask(sq)).bit_count()
    for sq in _scan_squares(board.bishops & black_occ):
        score -= 3 * int(board.attacks_mask(sq)).bit_count()

    # Rooks
    for sq in _scan_squares(board.rooks & white_occ):
        score += 2 * int(board.attacks_mask(sq)).bit_count()
    for sq in _scan_squares(board.rooks & black_occ):
        score -= 2 * int(board.attacks_mask(sq)).bit_count()

    return score


def _eval_knight_outposts(board: chess.Board) -> int:
    """Bonus for knights on outpost squares (no enemy pawns on adjacent files ahead)."""
    score = 0
    white_occ = board.occupied_co[chess.WHITE]
    black_occ = board.occupied_co[chess.BLACK]
    white_pawns = board.pawns & white_occ
    black_pawns = board.pawns & black_occ

    # White knights
    for sq in _scan_squares(board.knights & white_occ):
        r = sq // 8
        f = sq % 8
        # Must be on rank 4-6 (indices 3-5) to be an outpost
        if r >= 3 and r <= 5:
            # No enemy pawns on adjacent files ahead
            if not (black_pawns & _FORWARD_SPAN_WHITE[sq] & _ADJ_FILE_MASKS[f]):
                bonus = 25
                # Extra bonus if supported by own pawn
                if r > 0 and (white_pawns & _ADJ_FILE_MASKS[f] & _RANK_MASKS[r - 1]):
                    bonus += 15
                score += bonus

    # Black knights
    for sq in _scan_squares(board.knights & black_occ):
        r = sq // 8
        f = sq % 8
        if r >= 2 and r <= 4:
            if not (white_pawns & _FORWARD_SPAN_BLACK[sq] & _ADJ_FILE_MASKS[f]):
                bonus = 25
                if r < 7 and (black_pawns & _ADJ_FILE_MASKS[f] & _RANK_MASKS[r + 1]):
                    bonus += 15
                score -= bonus

    return score


# Masks for space evaluation: ranks 2-4 for white (indices 1-3), ranks 5-7 for black (4-6)
_WHITE_SPACE_MASK = 0
_BLACK_SPACE_MASK = 0
for _r in range(1, 4):
    _WHITE_SPACE_MASK |= _RANK_MASKS[_r]
for _r in range(4, 7):
    _BLACK_SPACE_MASK |= _RANK_MASKS[_r]
# Focus on center 4 files (c-f, indices 2-5)
_CENTER_FILES_MASK = 0
for _f in range(2, 6):
    _CENTER_FILES_MASK |= _FILE_MASKS[_f]
_WHITE_SPACE_MASK &= _CENTER_FILES_MASK
_BLACK_SPACE_MASK &= _CENTER_FILES_MASK


def _eval_space(board: chess.Board, endgame: bool) -> int:
    """Space advantage: control of squares in opponent's territory (middlegame only)."""
    if endgame:
        return 0
    score = 0
    white_occ = board.occupied_co[chess.WHITE]
    black_occ = board.occupied_co[chess.BLACK]
    white_pawns = board.pawns & white_occ
    black_pawns = board.pawns & black_occ

    # White space: pawns and pieces controlling black's territory
    white_space = _popcount(white_pawns & _BLACK_SPACE_MASK)
    black_space = _popcount(black_pawns & _WHITE_SPACE_MASK)
    score += (white_space - black_space) * 8

    return score


def _center_distance(sq: int) -> int:
    f = sq % 8
    r = sq // 8
    return abs(f - 3) + abs(r - 3)


def _king_distance(sq1: int, sq2: int) -> int:
    return max(abs(sq1 % 8 - sq2 % 8), abs(sq1 // 8 - sq2 // 8))


def _eval_mopup(board: chess.Board, material_score: int) -> int:
    if abs(material_score) < 200:
        return 0

    if material_score > 0:
        losing_king = board.king(chess.BLACK)
        winning_king = board.king(chess.WHITE)
    else:
        losing_king = board.king(chess.WHITE)
        winning_king = board.king(chess.BLACK)

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

    if board.can_claim_draw():
        return 0

    score = 0
    endgame = _is_endgame(board)
    king_pst = PST_KING_ENDGAME if endgame else PST_KING_MIDDLEGAME
    white_occ = board.occupied_co[chess.WHITE]
    black_occ = board.occupied_co[chess.BLACK]

    # Material + piece-square tables using direct bitboard access
    for piece_type, pst_table in PST.items():
        bb_mask = getattr(board, {
            chess.PAWN: 'pawns', chess.KNIGHT: 'knights',
            chess.BISHOP: 'bishops', chess.ROOK: 'rooks',
            chess.QUEEN: 'queens',
        }[piece_type])
        val = PIECE_VALUES[piece_type]

        for sq in _scan_squares(bb_mask & white_occ):
            score += val + pst_table[_mirror_square(sq)]
        for sq in _scan_squares(bb_mask & black_occ):
            score -= val + pst_table[sq]

    # King PST
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)
    if wk is not None:
        score += king_pst[_mirror_square(wk)]
    if bk is not None:
        score -= king_pst[bk]

    # Bishop pair bonus
    white_bishops = _popcount(board.bishops & white_occ)
    black_bishops = _popcount(board.bishops & black_occ)
    if white_bishops >= 2:
        score += 30
    if black_bishops >= 2:
        score -= 30

    # Pawn structure (cached)
    score += _eval_pawns(board)

    # King safety
    score += _eval_king_safety(board, endgame)

    # Rook placement
    score += _eval_rook_placement(board)

    # Mobility
    score += _eval_mobility(board)

    # Knight outposts
    score += _eval_knight_outposts(board)

    # Space advantage
    score += _eval_space(board, endgame)

    # Endgame mop-up
    if endgame:
        score += _eval_mopup(board, score)

    # Tempo bonus
    if board.turn == chess.WHITE:
        score += TEMPO_BONUS
    else:
        score -= TEMPO_BONUS

    return score
