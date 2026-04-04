"""Tests for position evaluation."""

import chess
from engine.evaluate import evaluate, PIECE_VALUES


def test_starting_position_is_equal():
    board = chess.Board()
    assert evaluate(board) == 0


def test_white_up_a_queen():
    # Remove black queen - score should be strongly positive
    board = chess.Board()
    board.remove_piece_at(chess.D8)
    score = evaluate(board)
    assert score > 800  # At least ~queen value even with PST adjustments


def test_black_up_a_queen():
    # Remove white queen - score should be strongly negative
    board = chess.Board()
    board.remove_piece_at(chess.D1)
    score = evaluate(board)
    assert score < -800


def test_checkmate_white_wins():
    board = chess.Board("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
    score = evaluate(board)
    assert score == 30000


def test_checkmate_black_wins():
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    score = evaluate(board)
    assert score == -30000


def test_stalemate_is_zero():
    board = chess.Board("8/8/8/8/8/1q6/8/K1k5 w - - 0 1")
    assert board.is_stalemate()
    assert evaluate(board) == 0


def test_material_difference():
    # White has extra knight - should be clearly positive
    board = chess.Board()
    board.remove_piece_at(chess.B8)
    score = evaluate(board)
    assert score > 200  # Knight value minus PST adjustment


def test_pst_center_pawns_better():
    # A pawn in the center should evaluate better than on the rim
    board_center = chess.Board("8/8/8/4P3/8/8/8/4K2k w - - 0 1")
    board_rim = chess.Board("8/8/8/P7/8/8/8/4K2k w - - 0 1")
    assert evaluate(board_center) > evaluate(board_rim)


def test_bishop_pair_bonus():
    # Two bishops should get a bonus
    board_pair = chess.Board("8/8/8/8/8/2BB4/8/4K2k w - - 0 1")
    board_one = chess.Board("8/8/8/8/8/2B5/8/4K2k w - - 0 1")
    diff = evaluate(board_pair) - evaluate(board_one)
    # Diff should be bishop value + ~30 bonus (pair) + PST
    assert diff > PIECE_VALUES[chess.BISHOP]
