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

# Piece-square tables from white's perspective (a1=index 0, h8=index 63)
# Based on Simplified Evaluation Function (chessprogramming.org)

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

# Map piece types to their PST
PST = {
    chess.PAWN: PST_PAWN,
    chess.KNIGHT: PST_KNIGHT,
    chess.BISHOP: PST_BISHOP,
    chess.ROOK: PST_ROOK,
    chess.QUEEN: PST_QUEEN,
}


def _mirror_square(sq: int) -> int:
    """Mirror a square vertically (for black's PST lookup)."""
    # Flip rank: rank 0 <-> rank 7
    return sq ^ 56


def _is_endgame(board: chess.Board) -> bool:
    """Simple endgame detection: no queens, or queen + minor piece max per side."""
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    if queens == 0:
        return True
    # Each side with queen must have no other major/minor pieces beyond 1
    for color in [chess.WHITE, chess.BLACK]:
        if board.pieces(chess.QUEEN, color):
            minors = (len(board.pieces(chess.KNIGHT, color)) +
                      len(board.pieces(chess.BISHOP, color)) +
                      len(board.pieces(chess.ROOK, color)))
            if minors > 1:
                return False
    return True


def evaluate(board: chess.Board) -> int:
    """Evaluate a position from white's perspective."""
    if board.is_checkmate():
        return -30000 if board.turn == chess.WHITE else 30000

    if board.is_stalemate() or board.is_insufficient_material():
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
                # PST is stored rank 8 at top (index 0), so mirror for white
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

    return score
