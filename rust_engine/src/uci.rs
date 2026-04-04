use cozy_chess::*;
use std::io::{self, BufRead, Write};

use crate::search::Searcher;

const ENGINE_NAME: &str = "CautiousPancake-Rust";
const ENGINE_AUTHOR: &str = "Claude Code";

pub fn allocate_time(
    wtime: Option<u64>,
    btime: Option<u64>,
    winc: u64,
    binc: u64,
    is_white: bool,
    movestogo: Option<u64>,
) -> u64 {
    let remaining = if is_white { wtime } else { btime };
    let increment = if is_white { winc } else { binc };

    let remaining = match remaining {
        Some(r) => r,
        None => return 5000,
    };

    let base_time = if let Some(mtg) = movestogo {
        if mtg > 0 {
            remaining / (mtg + 1)
        } else {
            remaining / 30
        }
    } else {
        remaining / 30
    };

    let allocated = base_time + increment * 8 / 10;
    let allocated = allocated.min(remaining / 3);
    allocated.max(50)
}

fn parse_position(tokens: &[&str]) -> (Board, Vec<u64>) {
    let mut idx = 1;
    let mut board = if tokens.get(idx) == Some(&"startpos") {
        idx += 1;
        Board::default()
    } else if tokens.get(idx) == Some(&"fen") {
        idx += 1;
        let mut fen_parts = Vec::new();
        while idx < tokens.len() && tokens[idx] != "moves" {
            fen_parts.push(tokens[idx]);
            idx += 1;
        }
        let fen = fen_parts.join(" ");
        fen.parse().unwrap_or_default()
    } else {
        Board::default()
    };

    let mut hashes = Vec::new();
    hashes.push(board.hash());

    if tokens.get(idx) == Some(&"moves") {
        idx += 1;
        while idx < tokens.len() {
            if let Ok(mv) = tokens[idx].parse::<Move>() {
                let mut legal = false;
                board.generate_moves(|mvs| {
                    for legal_mv in mvs {
                        if legal_mv == mv {
                            legal = true;
                            return true;
                        }
                    }
                    false
                });
                if legal {
                    board.play_unchecked(mv);
                    hashes.push(board.hash());
                }
            }
            idx += 1;
        }
    }

    (board, hashes)
}

fn parse_go(tokens: &[&str], is_white: bool) -> (i32, Option<u64>) {
    let mut depth: Option<i32> = None;
    let mut movetime: Option<u64> = None;
    let mut wtime: Option<u64> = None;
    let mut btime: Option<u64> = None;
    let mut winc: u64 = 0;
    let mut binc: u64 = 0;
    let mut movestogo: Option<u64> = None;
    let mut infinite = false;

    let mut i = 1;
    while i < tokens.len() {
        match tokens[i] {
            "depth" => {
                if i + 1 < tokens.len() {
                    depth = tokens[i + 1].parse().ok();
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "movetime" => {
                if i + 1 < tokens.len() {
                    movetime = tokens[i + 1].parse().ok();
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "wtime" => {
                if i + 1 < tokens.len() {
                    wtime = tokens[i + 1].parse().ok();
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "btime" => {
                if i + 1 < tokens.len() {
                    btime = tokens[i + 1].parse().ok();
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "winc" => {
                if i + 1 < tokens.len() {
                    winc = tokens[i + 1].parse().unwrap_or(0);
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "binc" => {
                if i + 1 < tokens.len() {
                    binc = tokens[i + 1].parse().unwrap_or(0);
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "movestogo" => {
                if i + 1 < tokens.len() {
                    movestogo = tokens[i + 1].parse().ok();
                    i += 2;
                } else {
                    i += 1;
                }
            }
            "infinite" => {
                infinite = true;
                i += 1;
            }
            _ => {
                i += 1;
            }
        }
    }

    if let Some(d) = depth {
        return (d, None);
    }
    if let Some(mt) = movetime {
        return (50, Some(mt));
    }
    if wtime.is_some() || btime.is_some() {
        let time_ms = allocate_time(wtime, btime, winc, binc, is_white, movestogo);
        return (50, Some(time_ms));
    }
    if infinite {
        return (50, None);
    }
    (6, None) // Default depth 6 for Rust (was 4 for Python)
}

pub fn uci_loop() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut board = Board::default();
    let mut hash_history: Vec<u64> = vec![board.hash()];
    let mut searcher = Searcher::new();

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let line = line.trim().to_string();
        if line.is_empty() {
            continue;
        }
        let tokens: Vec<&str> = line.split_whitespace().collect();
        let cmd = tokens[0];

        match cmd {
            "uci" => {
                let mut out = stdout.lock();
                writeln!(out, "id name {}", ENGINE_NAME).unwrap();
                writeln!(out, "id author {}", ENGINE_AUTHOR).unwrap();
                writeln!(out, "uciok").unwrap();
                out.flush().unwrap();
            }
            "isready" => {
                let mut out = stdout.lock();
                writeln!(out, "readyok").unwrap();
                out.flush().unwrap();
            }
            "ucinewgame" => {
                board = Board::default();
                hash_history = vec![board.hash()];
                searcher.clear();
            }
            "position" => {
                let (b, hashes) = parse_position(&tokens);
                board = b;
                hash_history = hashes;
            }
            "go" => {
                let is_white = board.side_to_move() == Color::White;
                let (depth, time_limit) = parse_go(&tokens, is_white);
                // Feed hash history for repetition detection
                searcher.hash_history = hash_history.clone();
                let mv = searcher.search(&board, depth, time_limit);
                let mut out = stdout.lock();
                match mv {
                    Some(m) => writeln!(out, "bestmove {}", m).unwrap(),
                    None => writeln!(out, "bestmove 0000").unwrap(),
                }
                out.flush().unwrap();
            }
            "quit" => break,
            "d" => {
                println!("{}", board);
                println!("FEN: {}", board);
            }
            _ => {}
        }
    }
}
