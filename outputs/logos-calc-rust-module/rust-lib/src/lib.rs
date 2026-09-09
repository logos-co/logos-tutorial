//! calc_rust — statistics over `calc_module`, written in Rust.
//!
//! Rust-FIRST authoring: the trait below IS the contract. The builder derives
//! the `.lidl` from it, generates the C-ABI scaffold around it, and compiles
//! this crate to a staticlib.

/// The trait name is derived from `name` in metadata.json: PascalCase, plus
/// `Module` unless it already ends in it — `calc_rust` -> `CalcRustModule`.
pub trait CalcRustModule: Send + 'static {
    /// Sums a JSON array of integers by folding it through `calc_module.add`,
    /// so every addition crosses the language boundary.
    fn sum_all(&mut self, values_json: String) -> i64;

    /// Reports the version of the C library `calc_module` wraps.
    fn backend_version(&mut self) -> String;

    /// Describes the last sum. An omitted `label` is the empty option, not an
    /// empty string — `Option<T>` is a real LIDL type, spelled `?tstr`.
    fn describe(&mut self, label: Option<String>) -> String;

    fn on_context_ready(&mut self, _ctx: &RustModuleContext) {}
}

/// Typed events — the Rust analog of the C++ `logos_events:` section. Each
/// method becomes an `emit_<name>` free function.
pub trait CalcRustModuleEvents {
    fn summed(&self, total: i64, terms: i64);
}

// The builder injects the generated scaffold here — `install`,
// `RustModuleContext`, `context()`, `modules()` and the `emit_*` emitters.
include!(concat!(env!("CARGO_MANIFEST_DIR"), "/generated/provider_gen.rs"));

#[derive(Default)]
struct CalcRust {
    last_total: i64,
    last_terms: i64,
}

impl CalcRustModule for CalcRust {
    fn sum_all(&mut self, values_json: String) -> i64 {
        let values: Vec<i64> = serde_json::from_str(&values_json).unwrap_or_default();

        // modules().calc_module is the typed client the builder generated from
        // calc_module's published contract. It is a C++ module; nothing here
        // says so.
        let mut total = 0i64;
        for v in &values {
            total = modules().calc_module.add(total, *v).unwrap_or(total);
        }

        self.last_total = total;
        self.last_terms = values.len() as i64;
        emit_summed(total, self.last_terms);
        total
    }

    fn backend_version(&mut self) -> String {
        modules()
            .calc_module
            .lib_version()
            .unwrap_or_else(|e| format!("unavailable: {e:?}"))
    }

    fn describe(&mut self, label: Option<String>) -> String {
        let label = label.unwrap_or_else(|| "last sum".to_string());
        format!("{}: {} over {} terms", label, self.last_total, self.last_terms)
    }
}

#[no_mangle]
pub extern "Rust" fn logos_module_install() {
    install::<CalcRust>();
}
