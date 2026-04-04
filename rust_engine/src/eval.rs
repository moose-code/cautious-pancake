use cozy_chess::*;

pub const MATE_SCORE: i32 = 30000;

const PAWN_VAL: i32 = 100;
const KNIGHT_VAL: i32 = 320;
const BISHOP_VAL: i32 = 330;
const ROOK_VAL: i32 = 500;
const QUEEN_VAL: i32 = 900;

pub const TEMPO_BONUS: i32 = 12;

pub fn piece_value(piece: Piece) -> i32 {
    match piece {
        Piece::Pawn => PAWN_VAL,
        Piece::Knight => KNIGHT_VAL,
        Piece::Bishop => BISHOP_VAL,
        Piece::Rook => ROOK_VAL,
        Piece::Queen => QUEEN_VAL,
        Piece::King => 0,
    }
}

pub fn see_piece_value(piece: Piece) -> i32 {
    match piece {
        Piece::Pawn => PAWN_VAL,
        Piece::Knight => KNIGHT_VAL,
        Piece::Bishop => BISHOP_VAL,
        Piece::Rook => ROOK_VAL,
        Piece::Queen => QUEEN_VAL,
        Piece::King => 20000,
    }
}

// PSTs indexed [square] where square 0 = A1 for white perspective
// We store from white's view (rank 1 at bottom = index 0..7)
// Original Python tables had rank 8 at index 0, so we reverse them.
#[rustfmt::skip]
const PST_PAWN: [i32; 64] = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10,-20,-20, 10, 10,  5,
     5, -5,-10,  0,  0,-10, -5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5,  5, 10, 25, 25, 10,  5,  5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
     0,  0,  0,  0,  0,  0,  0,  0,
];

#[rustfmt::skip]
const PST_KNIGHT: [i32; 64] = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
];

#[rustfmt::skip]
const PST_BISHOP: [i32; 64] = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
];

#[rustfmt::skip]
const PST_ROOK: [i32; 64] = [
     0,  0,  0,  5,  5,  0,  0,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     5, 10, 10, 10, 10, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
];

#[rustfmt::skip]
const PST_QUEEN: [i32; 64] = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -10,  5,  5,  5,  5,  5,  0,-10,
      0,  0,  5,  5,  5,  5,  0, -5,
     -5,  0,  5,  5,  5,  5,  0, -5,
    -10,  0,  5,  5,  5,  5,  0,-10,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
];

#[rustfmt::skip]
const PST_KING_MG: [i32; 64] = [
     20, 30, 10,  0,  0, 10, 30, 20,
     20, 20,  0,  0,  0,  0, 20, 20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
];

#[rustfmt::skip]
const PST_KING_EG: [i32; 64] = [
    -50,-30,-30,-30,-30,-30,-30,-50,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -50,-40,-30,-20,-20,-30,-40,-50,
];

fn pst_value(piece: Piece, sq: Square, is_white: bool, endgame: bool) -> i32 {
    let idx = if is_white {
        sq as usize
    } else {
        // Mirror vertically for black
        (sq as usize) ^ 56
    };
    match piece {
        Piece::Pawn => PST_PAWN[idx],
        Piece::Knight => PST_KNIGHT[idx],
        Piece::Bishop => PST_BISHOP[idx],
        Piece::Rook => PST_ROOK[idx],
        Piece::Queen => PST_QUEEN[idx],
        Piece::King => {
            if endgame { PST_KING_EG[idx] } else { PST_KING_MG[idx] }
        }
    }
}

fn is_endgame(board: &Board) -> bool {
    let queens = board.pieces(Piece::Queen);
    if queens.is_empty() {
        return true;
    }
    for color in [Color::White, Color::Black] {
        let our_queens = queens & board.colors(color);
        if !our_queens.is_empty() {
            let minors = (board.pieces(Piece::Knight) | board.pieces(Piece::Bishop) | board.pieces(Piece::Rook))
                & board.colors(color);
            if minors.len() > 1 {
                return false;
            }
        }
    }
    true
}

// File and adjacent file masks
const fn file_mask(file: u8) -> u64 {
    0x0101010101010101u64 << file
}

const fn adj_file_mask(file: u8) -> u64 {
    let mut mask = 0u64;
    if file > 0 {
        mask |= file_mask(file - 1);
    }
    if file < 7 {
        mask |= file_mask(file + 1);
    }
    mask
}

const fn rank_mask(rank: u8) -> u64 {
    0xFFu64 << (rank * 8)
}

// Forward span for passed pawn detection
fn forward_span_white(sq: Square) -> u64 {
    let file = sq.file() as u8;
    let rank = sq.rank() as u8;
    let files = file_mask(file) | adj_file_mask(file);
    let mut mask = 0u64;
    for r in (rank + 1)..8 {
        mask |= files & rank_mask(r);
    }
    mask
}

fn forward_span_black(sq: Square) -> u64 {
    let file = sq.file() as u8;
    let rank = sq.rank() as u8;
    let files = file_mask(file) | adj_file_mask(file);
    let mut mask = 0u64;
    for r in 0..rank {
        mask |= files & rank_mask(r);
    }
    mask
}

fn eval_pawns(board: &Board) -> i32 {
    let white_pawns = board.pieces(Piece::Pawn) & board.colors(Color::White);
    let black_pawns = board.pieces(Piece::Pawn) & board.colors(Color::Black);
    let wp = white_pawns.0;
    let bp = black_pawns.0;
    let mut score = 0i32;

    // White pawns
    for sq in white_pawns {
        let f = sq.file() as u8;
        let r = sq.rank() as u8;

        // Doubled
        if (wp & file_mask(f)).count_ones() > 1 {
            score -= 15;
        }
        // Isolated
        if wp & adj_file_mask(f) == 0 {
            score -= 20;
        }
        // Passed
        if bp & forward_span_white(sq) == 0 {
            let mut bonus = 20 + (r as i32 - 1) * 18;
            // Connected
            if wp & adj_file_mask(f) & rank_mask(r) != 0 {
                bonus += 15;
            }
            // Protected
            if r > 0 && wp & adj_file_mask(f) & rank_mask(r - 1) != 0 {
                bonus += 10;
            }
            score += bonus;
        }
    }

    // Black pawns
    for sq in black_pawns {
        let f = sq.file() as u8;
        let r = sq.rank() as u8;

        if (bp & file_mask(f)).count_ones() > 1 {
            score += 15;
        }
        if bp & adj_file_mask(f) == 0 {
            score += 20;
        }
        if wp & forward_span_black(sq) == 0 {
            let mut bonus = 20 + (6 - r as i32) * 18;
            if bp & adj_file_mask(f) & rank_mask(r) != 0 {
                bonus += 15;
            }
            if r < 7 && bp & adj_file_mask(f) & rank_mask(r + 1) != 0 {
                bonus += 10;
            }
            score -= bonus;
        }
    }

    score
}

fn king_ring(sq: Square) -> BitBoard {
    // King attacks + the square itself
    let attacks = cozy_chess::get_king_moves(sq);
    attacks | sq.bitboard()
}

fn eval_king_safety(board: &Board, endgame: bool) -> i32 {
    if endgame {
        return 0;
    }
    let mut score = 0;

    for &(color, enemy_color, sign) in &[
        (Color::White, Color::Black, 1i32),
        (Color::Black, Color::White, -1i32),
    ] {
        let king_sq = board.king(color);
        let king_file = king_sq.file() as u8;
        let king_rank = king_sq.rank() as u8;
        let pawns = (board.pieces(Piece::Pawn) & board.colors(color)).0;
        let kr = king_ring(king_sq);

        // Pawn shield
        let mut shield = 0i32;
        let shield_rank = if color == Color::White {
            king_rank.wrapping_add(1)
        } else {
            king_rank.wrapping_sub(1)
        };
        if shield_rank < 8 {
            let start_f = if king_file > 0 { king_file - 1 } else { 0 };
            let end_f = if king_file < 7 { king_file + 2 } else { 8 };
            for f in start_f..end_f {
                if pawns & (1u64 << (shield_rank * 8 + f)) != 0 {
                    shield += 15;
                }
            }
        }

        // Open file penalty
        let mut open_penalty = 0i32;
        let start_f = if king_file > 0 { king_file - 1 } else { 0 };
        let end_f = if king_file < 7 { king_file + 2 } else { 8 };
        for f in start_f..end_f {
            if pawns & file_mask(f) == 0 {
                open_penalty += 20;
            }
        }

        // Attack-unit system
        let mut attack_units = 0i32;
        let mut attacker_count = 0i32;
        let enemy_occ = board.colors(enemy_color);

        for &(piece, weight) in &[
            (Piece::Knight, 2i32),
            (Piece::Bishop, 2),
            (Piece::Rook, 3),
            (Piece::Queen, 5),
        ] {
            for sq in board.pieces(piece) & enemy_occ {
                let attacks = match piece {
                    Piece::Knight => cozy_chess::get_knight_moves(sq),
                    Piece::Bishop => cozy_chess::get_bishop_moves(sq, board.occupied()),
                    Piece::Rook => cozy_chess::get_rook_moves(sq, board.occupied()),
                    Piece::Queen => {
                        cozy_chess::get_bishop_moves(sq, board.occupied())
                            | cozy_chess::get_rook_moves(sq, board.occupied())
                    }
                    _ => BitBoard::EMPTY,
                };
                if !(attacks & kr).is_empty() {
                    attack_units += weight;
                    attacker_count += 1;
                }
            }
        }

        let attack_penalty = if attacker_count >= 2 {
            attack_units * attack_units / 2
        } else {
            0
        };

        score += sign * (shield - open_penalty - attack_penalty);
    }

    score
}

fn eval_rook_placement(board: &Board) -> i32 {
    let mut score = 0;
    let wp = (board.pieces(Piece::Pawn) & board.colors(Color::White)).0;
    let bp = (board.pieces(Piece::Pawn) & board.colors(Color::Black)).0;

    for sq in board.pieces(Piece::Rook) & board.colors(Color::White) {
        let f = sq.file() as u8;
        let r = sq.rank() as u8;
        let fm = file_mask(f);
        if wp & fm == 0 {
            score += if bp & fm == 0 { 25 } else { 12 };
        }
        if r == 6 {
            score += 20;
        }
    }

    for sq in board.pieces(Piece::Rook) & board.colors(Color::Black) {
        let f = sq.file() as u8;
        let r = sq.rank() as u8;
        let fm = file_mask(f);
        if bp & fm == 0 {
            score -= if wp & fm == 0 { 25 } else { 12 };
        }
        if r == 1 {
            score -= 20;
        }
    }

    score
}

fn eval_mobility(board: &Board) -> i32 {
    let mut score = 0i32;
    let occ = board.occupied();

    for sq in board.pieces(Piece::Knight) & board.colors(Color::White) {
        score += 4 * cozy_chess::get_knight_moves(sq).len() as i32;
    }
    for sq in board.pieces(Piece::Knight) & board.colors(Color::Black) {
        score -= 4 * cozy_chess::get_knight_moves(sq).len() as i32;
    }
    for sq in board.pieces(Piece::Bishop) & board.colors(Color::White) {
        score += 3 * cozy_chess::get_bishop_moves(sq, occ).len() as i32;
    }
    for sq in board.pieces(Piece::Bishop) & board.colors(Color::Black) {
        score -= 3 * cozy_chess::get_bishop_moves(sq, occ).len() as i32;
    }
    for sq in board.pieces(Piece::Rook) & board.colors(Color::White) {
        score += 2 * cozy_chess::get_rook_moves(sq, occ).len() as i32;
    }
    for sq in board.pieces(Piece::Rook) & board.colors(Color::Black) {
        score -= 2 * cozy_chess::get_rook_moves(sq, occ).len() as i32;
    }

    score
}

fn eval_knight_outposts(board: &Board) -> i32 {
    let mut score = 0;
    let wp = (board.pieces(Piece::Pawn) & board.colors(Color::White)).0;
    let bp = (board.pieces(Piece::Pawn) & board.colors(Color::Black)).0;

    for sq in board.pieces(Piece::Knight) & board.colors(Color::White) {
        let r = sq.rank() as u8;
        let f = sq.file() as u8;
        if r >= 3 && r <= 5 {
            if bp & forward_span_white(sq) & adj_file_mask(f) == 0 {
                let mut bonus = 25;
                if r > 0 && wp & adj_file_mask(f) & rank_mask(r - 1) != 0 {
                    bonus += 15;
                }
                score += bonus;
            }
        }
    }

    for sq in board.pieces(Piece::Knight) & board.colors(Color::Black) {
        let r = sq.rank() as u8;
        let f = sq.file() as u8;
        if r >= 2 && r <= 4 {
            if wp & forward_span_black(sq) & adj_file_mask(f) == 0 {
                let mut bonus = 25;
                if r < 7 && bp & adj_file_mask(f) & rank_mask(r + 1) != 0 {
                    bonus += 15;
                }
                score -= bonus;
            }
        }
    }

    score
}

fn eval_space(board: &Board, endgame: bool) -> i32 {
    if endgame {
        return 0;
    }
    // Center files c-f, ranks 5-7 for white space, ranks 2-4 for black space
    let center_files: u64 = file_mask(2) | file_mask(3) | file_mask(4) | file_mask(5);
    let white_space_zone: u64 = (rank_mask(4) | rank_mask(5) | rank_mask(6)) & center_files;
    let black_space_zone: u64 = (rank_mask(1) | rank_mask(2) | rank_mask(3)) & center_files;

    let wp = (board.pieces(Piece::Pawn) & board.colors(Color::White)).0;
    let bp = (board.pieces(Piece::Pawn) & board.colors(Color::Black)).0;

    let ws = (wp & white_space_zone).count_ones() as i32;
    let bs = (bp & black_space_zone).count_ones() as i32;
    (ws - bs) * 8
}

fn center_distance(sq: Square) -> i32 {
    let f = sq.file() as i32;
    let r = sq.rank() as i32;
    (f - 3).abs() + (r - 3).abs()
}

fn king_distance(sq1: Square, sq2: Square) -> i32 {
    let fd = (sq1.file() as i32 - sq2.file() as i32).abs();
    let rd = (sq1.rank() as i32 - sq2.rank() as i32).abs();
    fd.max(rd)
}

fn eval_mopup(board: &Board, material_score: i32) -> i32 {
    if material_score.abs() < 200 {
        return 0;
    }
    let (losing_king, winning_king) = if material_score > 0 {
        (board.king(Color::Black), board.king(Color::White))
    } else {
        (board.king(Color::White), board.king(Color::Black))
    };

    let corner = center_distance(losing_king) * 10;
    let close = (7 - king_distance(winning_king, losing_king)) * 5;
    let mopup = corner + close;
    if material_score > 0 { mopup } else { -mopup }
}

/// Check if position is a draw by insufficient material
fn is_insufficient_material(board: &Board) -> bool {
    // If there are pawns, rooks, or queens, not insufficient
    if !board.pieces(Piece::Pawn).is_empty()
        || !board.pieces(Piece::Rook).is_empty()
        || !board.pieces(Piece::Queen).is_empty()
    {
        return false;
    }
    // K vs K
    let total = board.occupied().len();
    if total <= 2 {
        return true;
    }
    // K+minor vs K
    if total == 3
        && (board.pieces(Piece::Knight).len() + board.pieces(Piece::Bishop).len() == 1)
    {
        return true;
    }
    false
}

/// Evaluate a position from white's perspective
pub fn evaluate(board: &Board) -> i32 {
    // Check for insufficient material
    if is_insufficient_material(board) {
        return 0;
    }

    let mut score = 0i32;
    let endgame = is_endgame(board);

    // Material + PST
    for &color in &[Color::White, Color::Black] {
        let sign = if color == Color::White { 1 } else { -1 };
        let is_white = color == Color::White;
        for &piece in &[Piece::Pawn, Piece::Knight, Piece::Bishop, Piece::Rook, Piece::Queen, Piece::King] {
            for sq in board.pieces(piece) & board.colors(color) {
                score += sign * (piece_value(piece) + pst_value(piece, sq, is_white, endgame));
            }
        }
    }

    // Bishop pair
    if (board.pieces(Piece::Bishop) & board.colors(Color::White)).len() >= 2 {
        score += 30;
    }
    if (board.pieces(Piece::Bishop) & board.colors(Color::Black)).len() >= 2 {
        score -= 30;
    }

    score += eval_pawns(board);
    score += eval_king_safety(board, endgame);
    score += eval_rook_placement(board);
    score += eval_mobility(board);
    score += eval_knight_outposts(board);
    score += eval_space(board, endgame);

    if endgame {
        score += eval_mopup(board, score);
    }

    // Tempo
    if board.side_to_move() == Color::White {
        score += TEMPO_BONUS;
    } else {
        score -= TEMPO_BONUS;
    }

    score
}

/// Evaluate from the side to move's perspective
pub fn eval_for_side(board: &Board) -> i32 {
    let raw = evaluate(board);
    if board.side_to_move() == Color::White { raw } else { -raw }
}
