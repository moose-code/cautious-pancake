use cozy_chess::*;

use crate::eval::piece_value;

pub struct MoveOrder {
    killer_moves: [[Option<Move>; 2]; 128], // per ply
    // History table: [color][from][to]
    history: [[[i32; 64]; 64]; 2],
    max_history: i32,
}

impl MoveOrder {
    pub fn new() -> Self {
        MoveOrder {
            killer_moves: [[None; 2]; 128],
            history: [[[0; 64]; 64]; 2],
            max_history: 1,
        }
    }

    pub fn reset(&mut self) {
        self.killer_moves = [[None; 2]; 128];
        self.history = [[[0; 64]; 64]; 2];
        self.max_history = 1;
    }

    /// Called at start of each iterative deepening search - age history
    pub fn new_search(&mut self) {
        self.killer_moves = [[None; 2]; 128];
        // Age history by halving instead of clearing
        for color in 0..2 {
            for from in 0..64 {
                for to in 0..64 {
                    self.history[color][from][to] /= 2;
                }
            }
        }
        self.max_history = self.max_history / 2 + 1;
    }

    pub fn record_killer(&mut self, mv: Move, depth: i32) {
        let d = (depth as usize).min(127);
        if self.killer_moves[d][0] != Some(mv) {
            self.killer_moves[d][1] = self.killer_moves[d][0];
            self.killer_moves[d][0] = Some(mv);
        }
    }

    pub fn record_history(&mut self, mv: Move, color: Color, depth: i32) {
        let ci = color as usize;
        let bonus = depth * depth;
        let val = &mut self.history[ci][mv.from as usize][mv.to as usize];
        *val += bonus;
        if *val > self.max_history {
            self.max_history = *val;
        }
        if self.max_history > 16000 {
            for c in 0..2 {
                for f in 0..64 {
                    for t in 0..64 {
                        self.history[c][f][t] /= 2;
                    }
                }
            }
            self.max_history /= 2;
        }
    }

    pub fn record_history_malus(&mut self, mv: Move, color: Color, depth: i32) {
        let ci = color as usize;
        let penalty = depth * depth;
        self.history[ci][mv.from as usize][mv.to as usize] -= penalty;
    }

    pub fn get_history(&self, mv: Move, color: Color) -> i32 {
        self.history[color as usize][mv.from as usize][mv.to as usize]
    }

    fn move_score(
        &self,
        board: &Board,
        mv: Move,
        depth: i32,
        countermove: Option<Move>,
    ) -> i32 {
        // Captures: MVV-LVA with winning/losing split
        if let Some(victim) = board.piece_on(mv.to) {
            let attacker = board.piece_on(mv.from).unwrap();
            let victim_val = piece_value(victim);
            let attacker_val = piece_value(attacker);
            let mvv_lva = victim_val * 10 - attacker_val;
            return if victim_val >= attacker_val {
                10000 + mvv_lva // Good captures above killers
            } else {
                5000 + mvv_lva // Losing captures below killers, above history
            };
        }

        // En passant
        if board.piece_on(mv.from) == Some(Piece::Pawn) && mv.from.file() != mv.to.file() {
            return 10010;
        }

        // Promotions
        if let Some(promo) = mv.promotion {
            return 9000 + piece_value(promo);
        }

        // Killers
        let d = (depth as usize).min(127);
        if self.killer_moves[d][0] == Some(mv) {
            return 8001;
        }
        if self.killer_moves[d][1] == Some(mv) {
            return 8000;
        }

        // Countermove
        if let Some(cm) = countermove {
            if mv == cm {
                return 7000;
            }
        }

        // History
        let ci = board.side_to_move() as usize;
        self.history[ci][mv.from as usize][mv.to as usize]
    }

    pub fn order_moves(
        &self,
        board: &Board,
        moves: &mut Vec<Move>,
        depth: i32,
        tt_move: Option<Move>,
        countermove: Option<Move>,
    ) {
        if let Some(tm) = tt_move {
            if let Some(pos) = moves.iter().position(|m| *m == tm) {
                moves.swap(0, pos);
                let rest = &mut moves[1..];
                rest.sort_by(|a, b| {
                    self.move_score(board, *b, depth, countermove)
                        .cmp(&self.move_score(board, *a, depth, countermove))
                });
                return;
            }
        }
        moves.sort_by(|a, b| {
            self.move_score(board, *b, depth, countermove)
                .cmp(&self.move_score(board, *a, depth, countermove))
        });
    }

    pub fn order_captures(&self, board: &Board, captures: &mut Vec<Move>) {
        captures.sort_by(|a, b| {
            self.move_score(board, *b, 0, None)
                .cmp(&self.move_score(board, *a, 0, None))
        });
    }
}
