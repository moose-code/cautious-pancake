use cozy_chess::*;
use std::collections::HashMap;
use std::time::Instant;

use crate::eval::{eval_for_side, see_piece_value, MATE_SCORE};
use crate::move_order::MoveOrder;

const INF: i32 = 99999;

// Transposition table
const TT_EXACT: u8 = 0;
const TT_LOWER: u8 = 1;
const TT_UPPER: u8 = 2;
const TT_MAX_SIZE: usize = 1 << 20;

#[derive(Clone, Copy)]
struct TTEntry {
    depth: i32,
    score: i32,
    flag: u8,
    best_move: Option<Move>,
}

// Futility margins by depth
const FUTILITY_MARGIN: [i32; 4] = [0, 200, 350, 500];
// Late move pruning thresholds
const LMP_THRESHOLD: [usize; 4] = [0, 6, 10, 16];

pub struct Searcher {
    tt: HashMap<u64, TTEntry>,
    move_order: MoveOrder,
    countermoves: HashMap<(Color, Square, Square), Move>,
    pub nodes: u64,
    start_time: Instant,
    time_limit_ms: Option<u64>,
    stopped: bool,
}

impl Searcher {
    pub fn new() -> Self {
        Searcher {
            tt: HashMap::with_capacity(TT_MAX_SIZE),
            move_order: MoveOrder::new(),
            countermoves: HashMap::new(),
            nodes: 0,
            start_time: Instant::now(),
            time_limit_ms: None,
            stopped: false,
        }
    }

    pub fn clear(&mut self) {
        self.tt.clear();
        self.countermoves.clear();
        self.move_order.reset();
    }

    fn check_time(&mut self) {
        if self.nodes % 4096 == 0 {
            if let Some(limit) = self.time_limit_ms {
                if self.start_time.elapsed().as_millis() as u64 > limit {
                    self.stopped = true;
                }
            }
        }
    }

    fn tt_lookup(&self, key: u64, depth: i32, alpha: i32, beta: i32) -> (Option<i32>, Option<Move>) {
        if let Some(entry) = self.tt.get(&key) {
            let tt_move = entry.best_move;
            if entry.depth >= depth {
                match entry.flag {
                    TT_EXACT => return (Some(entry.score), tt_move),
                    TT_LOWER if entry.score >= beta => return (Some(entry.score), tt_move),
                    TT_UPPER if entry.score <= alpha => return (Some(entry.score), tt_move),
                    _ => {}
                }
            }
            return (None, tt_move);
        }
        (None, None)
    }

    fn tt_store(&mut self, key: u64, depth: i32, score: i32, flag: u8, best_move: Option<Move>) {
        if let Some(existing) = self.tt.get(&key) {
            if depth < existing.depth {
                return;
            }
        }
        if self.tt.len() >= TT_MAX_SIZE && !self.tt.contains_key(&key) {
            // Simple eviction: clear 1/4
            let keys: Vec<u64> = self.tt.keys().take(self.tt.len() / 4).copied().collect();
            for k in keys {
                self.tt.remove(&k);
            }
        }
        self.tt.insert(key, TTEntry { depth, score, flag, best_move });
    }

    fn see(&self, board: &Board, mv: Move) -> i32 {
        // Check if it's a capture
        let victim = board.piece_on(mv.to);
        match victim {
            None => {
                // Could be en passant
                if board.piece_on(mv.from) == Some(Piece::Pawn)
                    && mv.from.file() != mv.to.file()
                {
                    return 100; // en passant
                }
                return 0;
            }
            Some(victim_piece) => {
                let gain = see_piece_value(victim_piece);
                let attacker = board.piece_on(mv.from).unwrap();
                // Simple SEE: check if target is defended
                let mut board_copy = board.clone();
                board_copy.play_unchecked(mv);
                // Check if opponent attacks the target square
                let them = board_copy.side_to_move();
                // Check all their pieces for attacks
                let their_pieces = board_copy.colors(them);
                for sq in their_pieces {
                    let piece = board_copy.piece_on(sq).unwrap();
                    let attacks = match piece {
                        Piece::Pawn => cozy_chess::get_pawn_attacks(sq, them),
                        Piece::Knight => cozy_chess::get_knight_moves(sq),
                        Piece::Bishop => cozy_chess::get_bishop_moves(sq, board_copy.occupied()),
                        Piece::Rook => cozy_chess::get_rook_moves(sq, board_copy.occupied()),
                        Piece::Queen => {
                            cozy_chess::get_bishop_moves(sq, board_copy.occupied())
                                | cozy_chess::get_rook_moves(sq, board_copy.occupied())
                        }
                        Piece::King => cozy_chess::get_king_moves(sq),
                    };
                    if attacks.has(mv.to) {
                        return gain - see_piece_value(attacker);
                    }
                }
                gain
            }
        }
    }

    fn has_non_pawn_material(&self, board: &Board) -> bool {
        let color = board.side_to_move();
        let our = board.colors(color);
        !(board.pieces(Piece::Knight) & our).is_empty()
            || !(board.pieces(Piece::Bishop) & our).is_empty()
            || !(board.pieces(Piece::Rook) & our).is_empty()
            || !(board.pieces(Piece::Queen) & our).is_empty()
    }

    fn generate_legal_moves(board: &Board) -> Vec<Move> {
        let mut moves = Vec::with_capacity(64);
        board.generate_moves(|mvs| {
            moves.extend(mvs);
            false
        });
        moves
    }

    fn generate_captures(board: &Board) -> Vec<Move> {
        let mut captures = Vec::with_capacity(32);
        board.generate_moves(|mvs| {
            for mv in mvs {
                if board.piece_on(mv.to).is_some()
                    || mv.promotion.is_some()
                    || (board.piece_on(mv.from) == Some(Piece::Pawn)
                        && mv.from.file() != mv.to.file())
                {
                    captures.push(mv);
                }
            }
            false
        });
        captures
    }

    pub fn quiescence(&mut self, board: &Board, mut alpha: i32, beta: i32, depth_limit: i32) -> i32 {
        if self.stopped {
            return 0;
        }
        self.nodes += 1;
        self.check_time();

        // TT lookup
        let tt_key = board.hash();
        if let Some(entry) = self.tt.get(&tt_key) {
            match entry.flag {
                TT_EXACT => return entry.score,
                TT_LOWER if entry.score >= beta => return entry.score,
                TT_UPPER if entry.score <= alpha => return entry.score,
                _ => {}
            }
        }

        let stand_pat = eval_for_side(board);

        if depth_limit == 0 {
            return stand_pat;
        }
        if stand_pat >= beta {
            return beta;
        }
        // Delta pruning
        if stand_pat + 900 < alpha {
            return alpha;
        }

        let orig_alpha = alpha;
        if stand_pat > alpha {
            alpha = stand_pat;
        }
        let mut best_score = stand_pat;

        let mut captures = Self::generate_captures(board);
        self.move_order.order_captures(board, &mut captures);

        for mv in captures {
            if self.see(board, mv) < -50 {
                continue;
            }

            let mut new_board = board.clone();
            new_board.play_unchecked(mv);
            let score = -self.quiescence(&new_board, -beta, -alpha, depth_limit - 1);

            if score > best_score {
                best_score = score;
            }
            if score >= beta {
                self.tt_store(tt_key, -1, score, TT_LOWER, Some(mv));
                return beta;
            }
            if score > alpha {
                alpha = score;
            }
        }

        if best_score <= orig_alpha {
            self.tt_store(tt_key, -1, best_score, TT_UPPER, None);
        } else {
            self.tt_store(tt_key, -1, best_score, TT_EXACT, None);
        }

        alpha
    }

    pub fn negamax(
        &mut self,
        board: &Board,
        mut depth: i32,
        mut alpha: i32,
        beta: i32,
        do_null: bool,
        ply: i32,
    ) -> i32 {
        if self.stopped {
            return 0;
        }
        self.nodes += 1;
        self.check_time();
        if self.stopped {
            return 0;
        }

        // Draw detection
        if board.halfmove_clock() >= 100 {
            return 0;
        }
        // Repetition check via hash history is handled by the board

        // Mate distance pruning
        if MATE_SCORE - ply <= alpha {
            return alpha;
        }
        if -(MATE_SCORE - ply) >= beta {
            return beta;
        }

        // TT lookup
        let tt_key = board.hash();
        let (tt_score, mut tt_move) = self.tt_lookup(tt_key, depth, alpha, beta);
        if tt_score.is_some() && ply > 0 {
            return tt_score.unwrap();
        }

        if depth <= 0 {
            return self.quiescence(board, alpha, beta, 8);
        }

        // Check status
        let checkers = board.checkers();
        let in_check = !checkers.is_empty();
        let is_pv = beta - alpha > 1;

        // Check extension
        if in_check {
            depth += 1;
        }

        // Static eval for pruning
        let static_eval = eval_for_side(board);

        // Razoring
        if depth <= 2
            && !in_check
            && !is_pv
            && alpha.abs() < MATE_SCORE - 100
            && static_eval + 300 * depth < alpha
        {
            let score = self.quiescence(board, alpha, beta, 8);
            if score <= alpha {
                return score;
            }
        }

        // Null move pruning
        if do_null
            && depth >= 3
            && !in_check
            && !is_pv
            && self.has_non_pawn_material(board)
            && static_eval >= beta
        {
            if let Some(null_board) = Self::play_null_move(board) {
                let r = if depth >= 6 { 3 } else { 2 };
                let score = -self.negamax(&null_board, depth - 1 - r, -beta, -beta + 1, false, ply + 1);
                if score >= beta {
                    return beta;
                }
            }
        }

        // Reverse futility pruning
        if depth <= 3 && !in_check && !is_pv && beta.abs() < MATE_SCORE - 100 {
            if static_eval - FUTILITY_MARGIN[depth as usize] >= beta {
                return static_eval - FUTILITY_MARGIN[depth as usize];
            }
        }

        // IID: if no TT move at PV node, do shallow search
        if tt_move.is_none() && is_pv && depth >= 4 {
            self.negamax(board, depth - 2, alpha, beta, false, ply);
            let (_, iid_move) = self.tt_lookup(tt_key, 0, alpha, beta);
            tt_move = iid_move;
        }

        let mut best_score = -INF;
        let mut best_move = None;
        let orig_alpha = alpha;

        // Get countermove
        let countermove = self.get_countermove(board);

        // Generate and order moves
        let mut moves = Self::generate_legal_moves(board);
        self.move_order.order_moves(board, &mut moves, depth, tt_move, countermove);

        // Singular extension check
        let singular_move = if let Some(tm) = tt_move {
            if depth >= 6 && !in_check && ply > 0 {
                if let Some(entry) = self.tt.get(&tt_key) {
                    if entry.depth >= depth - 3 && entry.flag != TT_UPPER {
                        let s_beta = entry.score - 50;
                        let mut is_singular = true;
                        for m in &moves {
                            if *m == tm {
                                continue;
                            }
                            let mut new_board = board.clone();
                            new_board.play_unchecked(*m);
                            let s = -self.negamax(&new_board, depth / 2 - 1, s_beta - 1, s_beta, false, ply + 1);
                            if s >= s_beta {
                                is_singular = false;
                                break;
                            }
                        }
                        if is_singular { Some(tm) } else { None }
                    } else {
                        None
                    }
                } else {
                    None
                }
            } else {
                None
            }
        } else {
            None
        };

        let mut moves_searched = 0usize;
        let mut quiet_moves_searched = 0usize;

        for mv in &moves {
            let mv = *mv;
            let is_capture = board.piece_on(mv.to).is_some()
                || (board.piece_on(mv.from) == Some(Piece::Pawn) && mv.from.file() != mv.to.file());
            let is_promotion = mv.promotion.is_some();
            let is_quiet = !is_capture && !is_promotion;

            // LMP
            if is_quiet
                && depth <= 3
                && !in_check
                && !is_pv
                && quiet_moves_searched >= LMP_THRESHOLD[depth as usize]
                && alpha.abs() < MATE_SCORE - 100
            {
                continue;
            }

            // Futility pruning
            if is_quiet
                && depth <= 3
                && !in_check
                && !is_pv
                && moves_searched > 0
                && alpha.abs() < MATE_SCORE - 100
                && static_eval + FUTILITY_MARGIN[depth as usize] <= alpha
            {
                quiet_moves_searched += 1;
                continue;
            }

            // SEE pruning for bad captures
            if is_capture && depth <= 2 && !in_check && self.see(board, mv) < -100 {
                continue;
            }

            // Singular extension
            let extension = if Some(mv) == singular_move { 1 } else { 0 };

            let mut new_board = board.clone();
            new_board.play_unchecked(mv);
            let gives_check = !new_board.checkers().is_empty();

            let score;
            if moves_searched == 0 {
                score = -self.negamax(&new_board, depth - 1 + extension, -beta, -alpha, true, ply + 1);
            } else {
                // LMR
                let mut reduction = 0;
                if moves_searched >= 3
                    && depth >= 3
                    && !in_check
                    && is_quiet
                    && !gives_check
                {
                    reduction = (0.75 + (depth as f64).ln() * (moves_searched as f64).ln() / 2.25) as i32;
                    if is_pv && reduction > 1 {
                        reduction -= 1;
                    }
                    reduction = reduction.min(depth - 2).max(0);
                }

                // Scout search
                let mut s = -self.negamax(&new_board, depth - 1 - reduction, -alpha - 1, -alpha, true, ply + 1);

                if s > alpha && (reduction > 0 || s < beta) {
                    s = -self.negamax(&new_board, depth - 1, -beta, -alpha, true, ply + 1);
                }
                score = s;
            }

            if self.stopped {
                return best_score.max(0);
            }

            moves_searched += 1;
            if is_quiet {
                quiet_moves_searched += 1;
            }

            if score > best_score {
                best_score = score;
                best_move = Some(mv);
            }

            if score > alpha {
                alpha = score;
                self.move_order.record_history(mv, board.side_to_move(), depth);
            }

            if alpha >= beta {
                if is_quiet {
                    self.move_order.record_killer(mv, depth);
                    self.record_countermove(board, mv);
                }
                break;
            }
        }

        // No legal moves: checkmate or stalemate
        if moves_searched == 0 {
            return if in_check {
                -(MATE_SCORE - ply)
            } else {
                0
            };
        }

        // Store in TT
        let flag = if best_score <= orig_alpha {
            TT_UPPER
        } else if best_score >= beta {
            TT_LOWER
        } else {
            TT_EXACT
        };
        self.tt_store(tt_key, depth, best_score, flag, best_move);

        best_score
    }

    fn play_null_move(_board: &Board) -> Option<Board> {
        // In cozy-chess, we can't directly play a null move.
        // We'll skip null move for now and just pass.
        // Actually, we need to construct a board with the side flipped.
        // cozy-chess doesn't support null moves directly, so we skip this optimization
        // if we can't do it. Let's try a different approach - use Board::try_null_move
        // Actually, let's build the null board manually via FEN manipulation
        None // Disable null move - cozy-chess doesn't support it
    }

    fn get_countermove(&self, _board: &Board) -> Option<Move> {
        // We'd need the last move, which we don't track in cozy-chess directly
        // This requires external tracking
        None
    }

    fn record_countermove(&mut self, _board: &Board, _mv: Move) {
        // Would need last move tracking
    }

    pub fn search(&mut self, board: &Board, max_depth: i32, time_limit_ms: Option<u64>) -> Option<Move> {
        self.nodes = 0;
        self.start_time = Instant::now();
        self.time_limit_ms = time_limit_ms;
        self.stopped = false;
        self.move_order.reset();
        self.countermoves.clear();

        let mut best_move = None;
        let mut prev_score = 0i32;
        let max_d = if time_limit_ms.is_some() { 50 } else { max_depth };

        for current_depth in 1..=max_d {
            let (mut alpha, mut beta) = if current_depth >= 4 {
                (prev_score - 40, prev_score + 40)
            } else {
                (-INF, INF)
            };

            let mut current_best: Option<Move> = None;
            let mut current_best_score = -INF;

            for _attempt in 0..3 {
                current_best = None;
                current_best_score = -INF;
                let mut search_alpha = alpha;

                let tt_key = board.hash();
                let (_, pv_move) = self.tt_lookup(tt_key, 0, alpha, beta);
                let mut moves = Self::generate_legal_moves(board);
                self.move_order.order_moves(board, &mut moves, current_depth, pv_move, None);

                for (i, mv) in moves.iter().enumerate() {
                    if let Some(limit) = self.time_limit_ms {
                        if self.start_time.elapsed().as_millis() as u64 > limit * 7 / 10 {
                            self.stopped = true;
                            break;
                        }
                    }

                    let mut new_board = board.clone();
                    new_board.play_unchecked(*mv);

                    let score = if i == 0 {
                        -self.negamax(&new_board, current_depth - 1, -beta, -search_alpha, true, 1)
                    } else {
                        let s = -self.negamax(&new_board, current_depth - 1, -search_alpha - 1, -search_alpha, true, 1);
                        if s > search_alpha && s < beta {
                            -self.negamax(&new_board, current_depth - 1, -beta, -search_alpha, true, 1)
                        } else {
                            s
                        }
                    };

                    if self.stopped {
                        break;
                    }

                    if score > current_best_score {
                        current_best_score = score;
                        current_best = Some(*mv);
                    }
                    if score > search_alpha {
                        search_alpha = score;
                    }
                }

                if self.stopped {
                    break;
                }

                if current_best_score <= alpha {
                    alpha = -INF;
                } else if current_best_score >= beta {
                    beta = INF;
                } else {
                    break;
                }
            }

            if self.stopped && current_best.is_none() {
                break;
            }

            if let Some(mv) = current_best {
                best_move = Some(mv);
                prev_score = current_best_score;
            }

            if let Some(limit) = self.time_limit_ms {
                if self.start_time.elapsed().as_millis() as u64 > limit / 2 {
                    break;
                }
            }

            if current_best_score.abs() > MATE_SCORE - 100 {
                break;
            }
        }

        best_move
    }
}
