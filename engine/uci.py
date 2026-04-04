"""UCI protocol implementation for CautiousPancake.

Handles stdin/stdout communication following the Universal Chess Interface spec.
"""

import chess
from engine.search import search, clear_tt
from engine.time_manager import allocate_time

ENGINE_NAME = "CautiousPancake"
ENGINE_AUTHOR = "Claude Code"


def main():
    """Main UCI loop. Reads commands from stdin, writes responses to stdout."""
    board = chess.Board()

    while True:
        try:
            line = input().strip()
        except EOFError:
            break

        if not line:
            continue

        tokens = line.split()
        cmd = tokens[0]

        if cmd == "uci":
            print(f"id name {ENGINE_NAME}", flush=True)
            print(f"id author {ENGINE_AUTHOR}", flush=True)
            print("uciok", flush=True)

        elif cmd == "isready":
            print("readyok", flush=True)

        elif cmd == "ucinewgame":
            board = chess.Board()
            clear_tt()

        elif cmd == "position":
            board = _parse_position(tokens)

        elif cmd == "go":
            depth, time_limit_ms = _parse_go(tokens, board.turn == chess.WHITE)
            move = search(board, depth=depth, time_limit_ms=time_limit_ms)
            if move is not None:
                print(f"bestmove {move.uci()}", flush=True)
            else:
                print("bestmove 0000", flush=True)

        elif cmd == "quit":
            break

        elif cmd == "d":
            print(board, flush=True)
            print(f"FEN: {board.fen()}", flush=True)


def _parse_position(tokens: list[str]) -> chess.Board:
    """Parse a 'position' UCI command and return the resulting board."""
    board = chess.Board()
    idx = 1

    if tokens[idx] == "startpos":
        idx += 1
    elif tokens[idx] == "fen":
        idx += 1
        fen_parts = []
        while idx < len(tokens) and tokens[idx] != "moves":
            fen_parts.append(tokens[idx])
            idx += 1
        board = chess.Board(" ".join(fen_parts))

    if idx < len(tokens) and tokens[idx] == "moves":
        idx += 1
        while idx < len(tokens):
            board.push_uci(tokens[idx])
            idx += 1

    return board


def _parse_go(tokens: list[str], is_white: bool) -> tuple[int, int | None]:
    """Parse 'go' command. Returns (depth, time_limit_ms).

    If time controls are given, uses time management.
    If depth is given, uses fixed depth.
    Otherwise defaults to depth 4.
    """
    params = {}
    i = 1
    while i < len(tokens):
        key = tokens[i]
        if key in ("depth", "movetime", "wtime", "btime", "winc", "binc", "movestogo") and i + 1 < len(tokens):
            params[key] = int(tokens[i + 1])
            i += 2
        elif key == "infinite":
            params["infinite"] = True
            i += 1
        else:
            i += 1

    # Fixed depth
    if "depth" in params:
        return params["depth"], None

    # Fixed time per move
    if "movetime" in params:
        return 50, params["movetime"]  # High max depth, time-limited

    # Time controls (wtime/btime)
    if "wtime" in params or "btime" in params:
        time_ms = allocate_time(
            wtime=params.get("wtime"),
            btime=params.get("btime"),
            winc=params.get("winc", 0),
            binc=params.get("binc", 0),
            is_white=is_white,
            movestogo=params.get("movestogo"),
        )
        return 50, time_ms  # High max depth, time-limited

    # Infinite
    if "infinite" in params:
        return 50, None  # Search deep

    # Default
    return 4, None


if __name__ == "__main__":
    main()
