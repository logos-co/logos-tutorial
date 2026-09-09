//! calc_slow — the SINGLE-dispatch control for the same experiment.

use std::sync::atomic::{AtomicI64, Ordering};

/// `single` is the default mode: handlers run one at a time on the module's
/// event loop, so the receiver is `&mut self` and no `Sync` is needed.
pub trait CalcSlowModule: Send + 'static {
    /// Blocks for `ms` milliseconds, then returns `ms`.
    fn work(&mut self, ms: i64) -> i64;

    /// The highest number of `work` calls that were ever in flight at once.
    fn peak(&mut self) -> i64;

    fn on_context_ready(&mut self, _ctx: &RustModuleContext) {}
}

include!(concat!(env!("CARGO_MANIFEST_DIR"), "/generated/provider_gen.rs"));

#[derive(Default)]
struct SlowWorker {
    in_flight: AtomicI64,
    max_seen: AtomicI64,
}

impl CalcSlowModule for SlowWorker {
    fn work(&mut self, ms: i64) -> i64 {
        let now = self.in_flight.fetch_add(1, Ordering::SeqCst) + 1;
        self.max_seen.fetch_max(now, Ordering::SeqCst);
        std::thread::sleep(std::time::Duration::from_millis(ms.max(0) as u64));
        self.in_flight.fetch_sub(1, Ordering::SeqCst);
        ms
    }

    fn peak(&mut self) -> i64 {
        self.max_seen.load(Ordering::SeqCst)
    }
}

#[no_mangle]
pub extern "Rust" fn logos_module_install() {
    install::<SlowWorker>();
}
