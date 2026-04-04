"""Tests for position evaluation."""

import chess
from engine.evaluate import evaluate, PIECE_VALUES


def test_starting_position_is_equal():
    board = chess.Board()
    assert evaluate(board) == 0


def test_white_up_a_queen():
    # Remove black queen
    board = chess.Board()
    board.remove_piece_at(chess.D8)
    score = evaluate(board)
    assert score == PIECE_VALUES[chess.QUEEN]


def test_black_up_a_queen():
    # Remove white queen
    board = chess.Board()
    board.remove_piece_at(chess.D1)
    score = evaluate(board)
    assert score == -PIECE_VALUES[chess.QUEEN]


def test_checkmate_white_wins():
    # Scholar's mate position - black is checkmated
    board = chess.Board("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
    score = evaluate(board)
    assert score == 30000  # White wins


def test_checkmate_black_wins():
    # Fool's mate - white is checkmated
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    score = evaluate(board)
    assert score == -30000  # Black wins


def test_stalemate_is_zero():
    # Stalemate position: white king on a1, black queen on b3, black king on c1
    board = chess.Board("8/8/8/8/8/1q6/8/K1k5 w - - 0 1")
    assert board.is_stalemate()
    assert evaluate(board) == 0


def test_material_difference():
    # White has extra knight
    board = chess.Board()
    board.remove_piece_at(chess.B8)  # Remove black knight
    score = evaluate(board)
    assert score == PIECE_VALUES[chess.KNIGHT]
