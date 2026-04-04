mod eval;
mod move_order;
mod search;
mod uci;

fn main() {
    uci::uci_loop();
}
