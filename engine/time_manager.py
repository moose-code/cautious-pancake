"""Time management for CautiousPancake."""


def allocate_time(
    wtime: int = None,
    btime: int = None,
    winc: int = 0,
    binc: int = 0,
    is_white: bool = True,
    movestogo: int = None,
) -> int:
    """Calculate how many milliseconds to spend on this move.

    Args:
        wtime/btime: Remaining time in ms for white/black
        winc/binc: Increment per move in ms
        is_white: True if engine is white
        movestogo: Moves until next time control (None = sudden death)

    Returns:
        Time to spend in milliseconds.
    """
    remaining = wtime if is_white else btime
    increment = winc if is_white else binc

    if remaining is None:
        return 5000  # Default 5 seconds if no time info

    if movestogo is not None and movestogo > 0:
        # Moves to go until time control
        base_time = remaining // (movestogo + 1)
    else:
        # Sudden death: assume ~30 moves left
        base_time = remaining // 30

    # Add most of the increment
    allocated = base_time + int(increment * 0.8)

    # Never use more than 1/3 of remaining time
    allocated = min(allocated, remaining // 3)

    # Minimum 50ms to avoid flagging on very fast time controls
    allocated = max(allocated, 50)

    return allocated
