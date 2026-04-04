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


def evaluate(board: chess.Board) -> int:
    """Evaluate a position from white's perspective.

    Phase 1: Material counting only.
    """
    if board.is_checkmate():
        # Side to move is checkmated
        return -30000 if board.turn == chess.WHITE else 30000

    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for piece_type in PIECE_VALUES:
        white_pieces = len(board.pieces(piece_type, chess.WHITE))
        black_pieces = len(board.pieces(piece_type, chess.BLACK))
        score += PIECE_VALUES[piece_type] * (white_pieces - black_pieces)

    return score
