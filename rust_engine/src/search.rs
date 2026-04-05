use cozy_chess::*;
use std::time::Instant;

use crate::eval::{eval_for_side, see_piece_value, MATE_SCORE};
use crate::move_order::MoveOrder;

const INF: i32 = 99999;

// Transposition table flags
const TT_EXACT: u8 = 0;
const TT_LOWER: u8 = 1;
const TT_UPPER: u8 = 2;
const TT_NONE: u8 = 3;

// Array-based TT for cache efficiency
const TT_SIZE: usize = 1 << 22; // 4M entries (~96MB)
const TT_MASK: usize = TT_SIZE - 1;

#[derive(Clone, Copy)]
struct TTEntry {
    key: u32, // Upper 32 bits of hash for collision detection
    depth: i8,
    score: i16,
    flag: u8,
    best_move: Option<Move>,
}

impl Default for TTEntry {
    fn default() -> Self {
        TTEntry {
            key: 0,
            depth: -127,
            score: 0,
            flag: TT_NONE,
            best_move: None,
        }
    }
}

// Futility margins by depth (extended to depth 5)
const FUTILITY_MARGIN: [i32; 6] = [0, 200, 350, 500, 650, 800];
// LMP thresholds (extended)
const LMP_THRESHOLD: [usize; 6] = [0, 5, 8, 14, 22, 32];

// Precomputed LMR table
static mut LMR_TABLE: [[i32; 64]; 64] = [[0; 64]; 64];

fn init_lmr_table() {
    unsafe {
        for depth in 1..64 {
            for moves in 1..64 {
                LMR_TABLE[depth][moves] =
                    (0.75 + (depth as f64).ln() * (moves as f64).ln() / 2.25) as i32;
            }
        }
    }
}

fn lmr_reduction(depth: i32, moves_searched: usize) -> i32 {
    let d = (depth as usize).min(63);
    let m = moves_searched.min(63);
    unsafe { LMR_TABLE[d][m] }
}

pub struct Searcher {
    tt: Vec<TTEntry>,
    move_order: MoveOrder,
    countermoves: [[Option<Move>; 64]; 2], // [color][to_square] -> move
    pub nodes: u64,
    start_time: Instant,
    time_limit_ms: Option<u64>,
    stopped: bool,
    last_move: Option<Move>, // Track for countermove heuristic
    // Repetition detection
    pub hash_history: Vec<u64>,
}

impl Searcher {
    pub fn new() -> Self {
        init_lmr_table();
        Searcher {
            tt: vec![TTEntry::default(); TT_SIZE],
            move_order: MoveOrder::new(),
            countermoves: [[None; 64]; 2],
            nodes: 0,
            start_time: Instant::now(),
            time_limit_ms: None,
            stopped: false,
            last_move: None,
            hash_history: Vec::with_capacity(512),
        }
    }

    pub fn clear(&mut self) {
        for entry in self.tt.iter_mut() {
            *entry = TTEntry::default();
        }
        self.countermoves = [[None; 64]; 2];
        self.move_order.reset();
        self.hash_history.clear();
    }

    pub fn push_hash(&mut self, hash: u64) {
        self.hash_history.push(hash);
    }

    pub fn pop_hash(&mut self) {
        self.hash_history.pop();
    }

    fn is_repetition(&self, hash: u64) -> bool {
        // Check for 2-fold repetition (sufficient for search)
        let len = self.hash_history.len();
        if len < 4 {
            return false;
        }
        // Only need to check positions where same side was on move (every 2 plies)
        let mut i = len.saturating_sub(2);
        loop {
            if self.hash_history[i] == hash {
                return true;
            }
            if i < 2 {
                break;
            }
            i -= 2;
        }
        false
    }

    fn check_time(&mut self) {
        if self.nodes & 4095 == 0 {
            if let Some(limit) = self.time_limit_ms {
                if self.start_time.elapsed().as_millis() as u64 > limit {
                    self.stopped = true;
                }
            }
        }
    }

    #[inline]
    fn tt_index(key: u64) -> usize {
        (key as usize) & TT_MASK
    }

    #[inline]
    fn tt_verify(key: u64) -> u32 {
        (key >> 32) as u32
    }

    fn tt_lookup(&self, key: u64, depth: i32, alpha: i32, beta: i32) -> (Option<i32>, Option<Move>) {
        let idx = Self::tt_index(key);
        let entry = &self.tt[idx];
        if entry.flag == TT_NONE || entry.key != Self::tt_verify(key) {
            return (None, None);
        }
        let tt_move = entry.best_move;
        let tt_score = entry.score as i32;
        let tt_depth = entry.depth as i32;
        if tt_depth >= depth {
            match entry.flag {
                TT_EXACT => return (Some(tt_score), tt_move),
                TT_LOWER if tt_score >= beta => return (Some(tt_score), tt_move),
                TT_UPPER if tt_score <= alpha => return (Some(tt_score), tt_move),
                _ => {}
            }
        }
        (None, tt_move)
    }

    fn tt_store(&mut self, key: u64, depth: i32, score: i32, flag: u8, best_move: Option<Move>) {
        let idx = Self::tt_index(key);
        let entry = &self.tt[idx];
        // Replace if: new entry has greater depth, or different position, or same position same depth
        if entry.flag == TT_NONE || entry.key != Self::tt_verify(key) || depth >= entry.depth as i32 {
            self.tt[idx] = TTEntry {
                key: Self::tt_verify(key),
                depth: depth.clamp(-127, 127) as i8,
                score: score.clamp(-32000, 32000) as i16,
                flag,
                best_move,
            };
        }
    }

    fn see(&self, board: &Board, mv: Move) -> i32 {
        let victim = board.piece_on(mv.to);
        match victim {
            None => {
                if board.piece_on(mv.from) == Some(Piece::Pawn) && mv.from.file() != mv.to.file() {
                    return 100; // en passant
                }
                return 0;
            }
            Some(victim_piece) => {
                let gain = see_piece_value(victim_piece);
                let attacker = board.piece_on(mv.from).unwrap();
                let attacker_val = see_piece_value(attacker);

                // If we capture with a less valuable piece, always good
                if attacker_val <= gain {
                    return gain;
                }

                // Quick check: is the square defended at all?
                let mut board_copy = board.clone();
                board_copy.play_unchecked(mv);
                // Check if opponent can recapture
                let mut can_recapture = false;
                board_copy.generate_moves(|mvs| {
                    for m in mvs {
                        if m.to == mv.to {
                            can_recapture = true;
                            return true;
                        }
                    }
                    false
                });

                if can_recapture {
                    gain - attacker_val
                } else {
                    gain
                }
            }
        }
    }

    fn has_non_pawn_material(board: &Board) -> bool {
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

    #[inline]
    fn is_capture(board: &Board, mv: Move) -> bool {
        board.piece_on(mv.to).is_some()
            || (board.piece_on(mv.from) == Some(Piece::Pawn) && mv.from.file() != mv.to.file())
    }

    pub fn quiescence(&mut self, board: &Board, mut alpha: i32, beta: i32, depth_limit: i32) -> i32 {
        if self.stopped {
            return 0;
        }
        self.nodes += 1;
        self.check_time();

        let tt_key = board.hash();

        // TT lookup
        let (tt_score, _) = self.tt_lookup(tt_key, -1, alpha, beta);
        if let Some(score) = tt_score {
            return score;
        }

        let stand_pat = eval_for_side(board);

        if depth_limit == 0 {
            return stand_pat;
        }
        if stand_pat >= beta {
            return beta;
        }
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
        let hash = board.hash();
        if board.halfmove_clock() >= 100 || self.is_repetition(hash) {
            return 0;
        }

        // Mate distance pruning
        let mut mating_score = MATE_SCORE - ply;
        if mating_score < beta {
            if mating_score <= alpha {
                return alpha;
            }
        }
        mating_score = -(MATE_SCORE - ply);
        if mating_score > alpha {
            alpha = mating_score;
            if alpha >= beta {
                return beta;
            }
        }

        // TT lookup
        let tt_key = board.hash();
        let (tt_score, mut tt_move) = self.tt_lookup(tt_key, depth, alpha, beta);
        if tt_score.is_some() && ply > 0 {
            return tt_score.unwrap();
        }

        if depth <= 0 {
            return self.quiescence(board, alpha, beta, 10);
        }

        let in_check = !board.checkers().is_empty();
        let is_pv = beta - alpha > 1;

        // Check extension
        if in_check {
            depth += 1;
        }

        // Static eval for pruning decisions
        let static_eval = if in_check { -INF } else { eval_for_side(board) };

        // Razoring: if static eval is way below alpha, drop to qsearch
        if !in_check
            && !is_pv
            && depth <= 3
            && alpha.abs() < MATE_SCORE - 100
            && static_eval + 200 * depth <= alpha
        {
            let score = self.quiescence(board, alpha, beta, 10);
            if score <= alpha {
                return score;
            }
        }

        // Null move pruning (now enabled!)
        if do_null
            && !in_check
            && !is_pv
            && depth >= 3
            && Self::has_non_pawn_material(board)
            && static_eval >= beta
        {
            if let Some(null_board) = board.null_move() {
                self.push_hash(hash);
                let r = if depth >= 6 { 3 } else { 2 };
                let r = r + (depth / 6); // Adaptive R
                let score = -self.negamax(&null_board, depth - 1 - r, -beta, -beta + 1, false, ply + 1);
                self.pop_hash();
                if score >= beta {
                    // Verification search at high depths to avoid zugzwang
                    if depth >= 10 {
                        let v = self.negamax(board, depth - 1 - r, beta - 1, beta, false, ply);
                        if v >= beta {
                            return beta;
                        }
                    } else {
                        return beta;
                    }
                }
            }
        }

        // Reverse futility pruning (extended to depth 5)
        if !in_check && !is_pv && depth <= 5 && beta.abs() < MATE_SCORE - 100 {
            if static_eval - FUTILITY_MARGIN[depth as usize] >= beta {
                return static_eval - FUTILITY_MARGIN[depth as usize];
            }
        }

        // IID
        if tt_move.is_none() && is_pv && depth >= 4 {
            self.negamax(board, depth - 2, alpha, beta, false, ply);
            let (_, iid_move) = self.tt_lookup(tt_key, 0, alpha, beta);
            tt_move = iid_move;
        }

        let mut best_score = -INF;
        let mut best_move: Option<Move> = None;
        let orig_alpha = alpha;

        // Countermove lookup
        let countermove = if let Some(last) = self.last_move {
            let ci = if board.side_to_move() == Color::White { 1 } else { 0 }; // opponent's color index
            self.countermoves[ci][last.to as usize]
        } else {
            None
        };

        let mut moves = Self::generate_legal_moves(board);
        self.move_order.order_moves(board, &mut moves, depth, tt_move, countermove);

        // Singular extension
        let singular_move = if let Some(tm) = tt_move {
            if depth >= 8 && !in_check && ply > 0 {
                let idx = Self::tt_index(tt_key);
                let entry = &self.tt[idx];
                if entry.key == Self::tt_verify(tt_key) && entry.depth as i32 >= depth - 3 && entry.flag != TT_UPPER {
                    let s_beta = entry.score as i32 - 2 * depth;
                    let mut found_fail = false;
                    for m in &moves {
                        if *m == tm {
                            continue;
                        }
                        let mut new_board = board.clone();
                        new_board.play_unchecked(*m);
                        self.push_hash(hash);
                        let s = -self.negamax(&new_board, depth / 2 - 1, s_beta - 1, s_beta, false, ply + 1);
                        self.pop_hash();
                        if s >= s_beta {
                            found_fail = true;
                            break;
                        }
                    }
                    if !found_fail { Some(tm) } else { None }
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
        let mut quiet_moves_tried: Vec<Move> = Vec::new();

        for mv in &moves {
            let mv = *mv;
            let is_cap = Self::is_capture(board, mv);
            let is_promotion = mv.promotion.is_some();
            let is_quiet = !is_cap && !is_promotion;

            // LMP (extended to depth 5)
            if is_quiet
                && depth <= 5
                && !in_check
                && !is_pv
                && quiet_moves_searched >= LMP_THRESHOLD[depth as usize]
                && alpha.abs() < MATE_SCORE - 100
            {
                continue;
            }

            // Futility pruning (extended to depth 5)
            if is_quiet
                && depth <= 5
                && !in_check
                && !is_pv
                && moves_searched > 0
                && alpha.abs() < MATE_SCORE - 100
                && static_eval + FUTILITY_MARGIN[depth as usize] <= alpha
            {
                quiet_moves_searched += 1;
                continue;
            }

            // SEE pruning for bad captures at low depths
            if is_cap && depth <= 3 && !in_check && self.see(board, mv) < -50 * depth {
                continue;
            }

            // Extensions
            let mut extension = 0;
            if Some(mv) == singular_move {
                extension = 1;
            }

            let mut new_board = board.clone();
            new_board.play_unchecked(mv);
            let gives_check = !new_board.checkers().is_empty();

            // Check extension for non-PV first move too
            if gives_check && extension == 0 && depth <= 4 {
                extension = 1;
            }

            self.push_hash(hash);
            let old_last = self.last_move;
            self.last_move = Some(mv);

            let score;
            if moves_searched == 0 {
                score = -self.negamax(&new_board, depth - 1 + extension, -beta, -alpha, true, ply + 1);
            } else {
                // LMR with precomputed table
                let mut reduction = 0;
                if moves_searched >= 3
                    && depth >= 3
                    && !in_check
                    && is_quiet
                    && !gives_check
                {
                    reduction = lmr_reduction(depth, moves_searched);
                    if is_pv && reduction > 0 {
                        reduction -= 1;
                    }
                    // Reduce more for moves with bad history
                    let hist = self.move_order.get_history(mv, board.side_to_move());
                    if hist < 0 {
                        reduction += 1;
                    }
                    reduction = reduction.clamp(0, depth - 2);
                }

                let mut s = -self.negamax(&new_board, depth - 1 - reduction, -alpha - 1, -alpha, true, ply + 1);

                if s > alpha && (reduction > 0 || s < beta) {
                    s = -self.negamax(&new_board, depth - 1 + extension, -beta, -alpha, true, ply + 1);
                }
                score = s;
            }

            self.last_move = old_last;
            self.pop_hash();

            if self.stopped {
                return best_score.max(0);
            }

            moves_searched += 1;
            if is_quiet {
                quiet_moves_searched += 1;
                quiet_moves_tried.push(mv);
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
                    // Record countermove
                    if let Some(last) = old_last {
                        let ci = if board.side_to_move() == Color::White { 1 } else { 0 };
                        self.countermoves[ci][last.to as usize] = Some(mv);
                    }
                    // History malus for quiet moves that didn't cause cutoff
                    for &prev in &quiet_moves_tried {
                        if prev != mv {
                            self.move_order.record_history_malus(prev, board.side_to_move(), depth);
                        }
                    }
                }
                break;
            }
        }

        if moves_searched == 0 {
            return if in_check {
                -(MATE_SCORE - ply)
            } else {
                0
            };
        }

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

    pub fn search(&mut self, board: &Board, max_depth: i32, time_limit_ms: Option<u64>) -> Option<Move> {
        self.nodes = 0;
        self.start_time = Instant::now();
        self.time_limit_ms = time_limit_ms;
        self.stopped = false;
        self.move_order.new_search();

        let mut best_move = None;
        let mut prev_score = 0i32;
        let max_d = if time_limit_ms.is_some() { 64 } else { max_depth };

        for current_depth in 1..=max_d {
            let (mut alpha, mut beta) = if current_depth >= 4 {
                let w = 30; // tighter aspiration
                (prev_score - w, prev_score + w)
            } else {
                (-INF, INF)
            };

            let mut current_best: Option<Move> = None;
            let mut current_best_score = -INF;

            for attempt in 0..4 {
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
                    let hash = board.hash();
                    self.push_hash(hash);
                    self.last_move = Some(*mv);

                    let score = if i == 0 {
                        -self.negamax(&new_board, current_depth - 1, -beta, -search_alpha, true, 1)
                    } else {
                        let s = -self.negamax(&new_board, current_depth - 1, -search_alpha - 1, -search_alpha, true, 1);
                        if s > search_alpha && s < beta && !self.stopped {
                            -self.negamax(&new_board, current_depth - 1, -beta, -search_alpha, true, 1)
                        } else {
                            s
                        }
                    };

                    self.pop_hash();

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

                // Widen aspiration window on fail
                if current_best_score <= alpha {
                    alpha = if attempt >= 2 { -INF } else { alpha - 100 * (1 << attempt) };
                } else if current_best_score >= beta {
                    beta = if attempt >= 2 { INF } else { beta + 100 * (1 << attempt) };
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
