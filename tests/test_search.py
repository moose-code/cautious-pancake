"""Tests for search algorithm."""

import chess
from engine.search import search, negamax


def test_search_returns_legal_move():
    board = chess.Board()
    move = search(board, depth=2)
    assert move in board.legal_moves


def test_captures_hanging_queen():
    # White queen on d5 can be captured by black knight on f6
    board = chess.Board("rnbqkb1r/pppppppp/5n2/3Q4/8/8/PPPP1PPP/RNB1KBNR b KQkq - 0 1")
    move = search(board, depth=2)
    # Black should capture the queen
    assert move == chess.Move.from_uci("f6d5")


def test_captures_hanging_piece():
    # White to move, black knight hanging on e5, white bishop on c3 can take
    board = chess.Board("rnbqkb1r/pppp1ppp/8/4n3/8/2B5/PPPPPPPP/RN1QKBNR w KQkq - 0 1")
    move = search(board, depth=3)
    # Should capture the free knight
    assert board.is_capture(move)


def test_avoids_losing_queen():
    # White queen is attacked, should move to safety
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/3Q4/8/PPP1PPPP/RNB1KBNR w KQkq - 0 1")
    move = search(board, depth=3)
    # After any reasonable move, white should still have the queen
    board.push(move)
    # Count white queens - should still have one
    assert len(board.pieces(chess.QUEEN, chess.WHITE)) == 1


def test_mate_in_one():
    # White to move, Qh7# is mate in 1
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
    move = search(board, depth=2)
    board.push(move)
    assert board.is_checkmate()


def test_depth_1_returns_move():
    board = chess.Board()
    move = search(board, depth=1)
    assert move is not None
    assert move in board.legal_moves


def test_no_crash_on_near_endgame():
    # King and pawn vs king
    board = chess.Board("8/8/8/8/8/4k3/4P3/4K3 w - - 0 1")
    move = search(board, depth=3)
    assert move in board.legal_moves
