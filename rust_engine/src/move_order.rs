use cozy_chess::*;
use std::collections::HashMap;

use crate::eval::piece_value;

pub struct MoveOrder {
    killer_moves: HashMap<i32, [Option<Move>; 2]>,
    history: HashMap<(Color, Square, Square), i32>,
    max_history: i32,
}

impl MoveOrder {
    pub fn new() -> Self {
        MoveOrder {
            killer_moves: HashMap::new(),
            history: HashMap::new(),
            max_history: 1,
        }
    }

    pub fn reset(&mut self) {
        self.killer_moves.clear();
        self.history.clear();
        self.max_history = 1;
    }

    pub fn record_killer(&mut self, mv: Move, depth: i32) {
        let entry = self.killer_moves.entry(depth).or_insert([None, None]);
        if entry[0] != Some(mv) {
            entry[1] = entry[0];
            entry[0] = Some(mv);
        }
    }

    pub fn record_history(&mut self, mv: Move, color: Color, depth: i32) {
        let key = (color, mv.from, mv.to);
        let val = self.history.entry(key).or_insert(0);
        *val += depth * depth;
        if *val > self.max_history {
            self.max_history = *val;
        }
        if self.max_history > 10000 {
            for v in self.history.values_mut() {
                *v /= 2;
            }
            self.max_history /= 2;
        }
    }

    fn move_score(
        &self,
        board: &Board,
        mv: Move,
        depth: i32,
        countermove: Option<Move>,
    ) -> i32 {
        // Captures
        if let Some(victim) = board.piece_on(mv.to) {
            let attacker = board.piece_on(mv.from).unwrap();
            let victim_val = piece_value(victim);
            let attacker_val = piece_value(attacker);
            let mvv_lva = victim_val * 10 - attacker_val;
            return if victim_val >= attacker_val {
                10000 + mvv_lva
            } else {
                5000 + mvv_lva
            };
        }

        // En passant capture
        if board.piece_on(mv.from) == Some(Piece::Pawn) && mv.from.file() != mv.to.file() {
            return 10010;
        }

        // Promotions
        if let Some(promo) = mv.promotion {
            return 9000 + piece_value(promo);
        }

        // Killers
        if let Some(killers) = self.killer_moves.get(&depth) {
            if killers[0] == Some(mv) {
                return 8001;
            }
            if killers[1] == Some(mv) {
                return 8000;
            }
        }

        // Countermove
        if let Some(cm) = countermove {
            if mv == cm {
                return 7000;
            }
        }

        // History
        let key = (board.side_to_move(), mv.from, mv.to);
        *self.history.get(&key).unwrap_or(&0)
    }

    pub fn order_moves(
        &self,
        board: &Board,
        moves: &mut Vec<Move>,
        depth: i32,
        tt_move: Option<Move>,
        countermove: Option<Move>,
    ) {
        // Put TT move first
        if let Some(tm) = tt_move {
            if let Some(pos) = moves.iter().position(|m| *m == tm) {
                moves.swap(0, pos);
                // Sort the rest
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
