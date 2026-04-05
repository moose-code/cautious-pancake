/// Simple embedded opening book using position hashes -> move strings.
/// Covers the most common strong opening lines for both colors.

use cozy_chess::*;
use std::collections::HashMap;

/// Build the opening book as a hash map from board hash to best move.
/// We compute hashes by playing out the lines on a board.
pub fn build_book() -> HashMap<u64, &'static str> {
    let mut book = HashMap::new();

    // Each entry is (sequence of moves to reach position, move to play from there)
    let lines: &[(&[&str], &str)] = &[
        // === WHITE OPENINGS ===
        // 1. e4 (King's pawn)
        (&[], "e2e4"),
        // After 1...e5: play Nf3 (open game)
        (&["e2e4", "e7e5"], "g1f3"),
        // Italian: after 2...Nc6, play Bc4
        (&["e2e4", "e7e5", "g1f3", "b8c6"], "f1c4"),
        // Italian main: after 3...Bc5, play c3 (Giuoco Piano)
        (&["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"], "c2c3"),
        // Italian: after 3...Nf6, play d3 (Giuoco Pianissimo)
        (&["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"], "d2d3"),
        // Ruy Lopez: after 3...a6, play Ba4
        (&["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"], "b5a4"),

        // After 1...c5 (Sicilian): play Nf3
        (&["e2e4", "c7c5"], "g1f3"),
        // Sicilian Open: after 2...d6, play d4
        (&["e2e4", "c7c5", "g1f3", "d7d6"], "d2d4"),
        // Sicilian Open: after 2...Nc6, play d4
        (&["e2e4", "c7c5", "g1f3", "b8c6"], "d2d4"),
        // Sicilian Open: after 2...e6, play d4
        (&["e2e4", "c7c5", "g1f3", "e7e6"], "d2d4"),

        // After 1...e6 (French): play d4
        (&["e2e4", "e7e6"], "d2d4"),
        // French: after 2...d5, play Nc3 (Classical)
        (&["e2e4", "e7e6", "d2d4", "d7d5"], "b1c3"),

        // After 1...c6 (Caro-Kann): play d4
        (&["e2e4", "c7c6"], "d2d4"),
        // Caro-Kann: after 2...d5, play Nc3
        (&["e2e4", "c7c6", "d2d4", "d7d5"], "b1c3"),

        // After 1...d5 (Scandinavian): play exd5
        (&["e2e4", "d7d5"], "e4d5"),

        // === BLACK RESPONSES ===
        // After 1. d4: play d5 (QGD family)
        (&["d2d4"], "d7d5"),
        // After 1. d4 d5 2. c4: play e6 (QGD)
        (&["d2d4", "d7d5", "c2c4"], "e7e6"),
        // QGD: after 3. Nc3, play Nf6
        (&["d2d4", "d7d5", "c2c4", "e7e6", "b1c3"], "g8f6"),

        // After 1. d4 d5 2. Nf3: play Nf6
        (&["d2d4", "d7d5", "g1f3"], "g8f6"),
        // After 1. d4 d5 2. Bf4 (London): play Nf6
        (&["d2d4", "d7d5", "c1f4"], "g8f6"),

        // After 1. e4: play e5 (open game for black)
        (&["e2e4"], "e7e5"),  // This is overridden by white's entry; handled by side check

        // After 1. Nf3: play d5
        (&["g1f3"], "d7d5"),
        // After 1. c4 (English): play e5
        (&["c2c4"], "e7e5"),
        // After 1. c4 e5 2. Nc3: play Nf6
        (&["c2c4", "e7e5", "b1c3"], "g8f6"),
    ];

    for &(moves, reply) in lines {
        let mut board = Board::default();
        let mut valid = true;
        for mv_str in moves {
            match mv_str.parse::<Move>() {
                Ok(mv) => {
                    // Verify it's legal
                    let mut legal = false;
                    board.generate_moves(|mvs| {
                        for m in mvs {
                            if m == mv {
                                legal = true;
                                return true;
                            }
                        }
                        false
                    });
                    if legal {
                        board.play_unchecked(mv);
                    } else {
                        valid = false;
                        break;
                    }
                }
                Err(_) => {
                    valid = false;
                    break;
                }
            }
        }
        if valid {
            book.insert(board.hash(), reply);
        }
    }

    book
}

/// Look up a position in the opening book.
/// Returns Some(Move) if found and the move is legal.
pub fn lookup(book: &HashMap<u64, &str>, board: &Board) -> Option<Move> {
    let hash = board.hash();
    if let Some(mv_str) = book.get(&hash) {
        if let Ok(mv) = mv_str.parse::<Move>() {
            // Verify it's legal in this position
            let mut legal = false;
            board.generate_moves(|mvs| {
                for m in mvs {
                    if m == mv {
                        legal = true;
                        return true;
                    }
                }
                false
            });
            if legal {
                return Some(mv);
            }
        }
    }
    None
}
