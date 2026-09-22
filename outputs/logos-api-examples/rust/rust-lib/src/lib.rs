//! Contract-first Rust: the builder generates the trait and record structs.
include!(concat!(env!("CARGO_MANIFEST_DIR"), "/generated/provider_gen.rs"));

#[derive(Default)]
struct ApiRust;

impl ApiRustModule for ApiRust {
    fn echo_string(&mut self, v: String) -> String { v }
    fn echo_bytes(&mut self, v: Vec<u8>) -> Vec<u8> { v }
    fn echo_int(&mut self, v: i64) -> i64 { v }
    fn echo_uint(&mut self, v: u64) -> u64 { v }
    fn echo_double(&mut self, v: f64) -> f64 { v }
    fn echo_bool(&mut self, v: bool) -> bool { v }
    fn echo_any(&mut self, v: serde_json::Value) -> serde_json::Value { v }
    fn echo_string_list(&mut self, v: Vec<String>) -> Vec<String> { v }
    fn echo_int_list(&mut self, v: Vec<i64>) -> Vec<i64> { v }
    fn echo_uint_list(&mut self, v: Vec<u64>) -> Vec<u64> { v }
    fn echo_double_list(&mut self, v: Vec<f64>) -> Vec<f64> { v }
    fn echo_bool_list(&mut self, v: Vec<bool>) -> Vec<bool> { v }
    fn echo_list(&mut self, v: Vec<serde_json::Value>) -> Vec<serde_json::Value> { v }
    fn echo_map(&mut self, v: std::collections::BTreeMap<String, serde_json::Value>) -> std::collections::BTreeMap<String, serde_json::Value> { v }
    fn echo_bytes_list(&mut self, v: Vec<Vec<u8>>) -> Vec<Vec<u8>> { v }
    fn echo_bytes_map(&mut self, v: std::collections::BTreeMap<String, Vec<u8>>) -> std::collections::BTreeMap<String, Vec<u8>> { v }
    fn echo_int_map(&mut self, v: std::collections::BTreeMap<String, i64>) -> std::collections::BTreeMap<String, i64> { v }
    fn echo_unordered_map(&mut self, v: std::collections::BTreeMap<String, i64>) -> std::collections::BTreeMap<String, i64> { v }
    fn echo_nested(&mut self, v: Vec<Vec<i64>>) -> Vec<Vec<i64>> { v }
    fn echo_entry(&mut self, v: Entry) -> Entry { v }
    fn echo_entries(&mut self, v: Vec<Entry>) -> Vec<Entry> { v }
    fn echo_entry_map(&mut self, v: std::collections::BTreeMap<String, Entry>) -> std::collections::BTreeMap<String, Entry> { v }
    fn echo_batch(&mut self, v: Batch) -> Batch { v }
    fn echo_optional(&mut self, v: Option<String>) -> Option<String> { v }
    fn do_void(&mut self) {}
    fn make_result(&mut self, ok: bool) -> Result<serde_json::Value, String> {
        if ok { Ok(serde_json::json!(42)) }
        else { Err("deliberate domain error".to_string()) }
    }
    fn slow(&mut self, ms: i64) -> i64 {
        std::thread::sleep(std::time::Duration::from_millis(ms.max(0) as u64));
        ms
    }
    fn check_calls(&mut self, provider: String) -> String {
        check_calls(&provider).unwrap_or_else(|e| e)
    }
    fn start_async(&mut self, provider: String) -> String {
        start_async(&provider);
        "started".to_string()
    }
    fn async_status(&mut self) -> String {
        let state = ASYNC_STATE.lock().unwrap();
        if state.0 != 3 { "pending" }
        else if state.1 { "async checks passed" }
        else { "async checks failed" }.to_string()
    }
}

fn check_calls(provider: &str) -> Result<String, String> {
    use std::time::Duration;
    let peer = calls::CallsClient::bind(provider);
    // The outer Result reports a call failure, even if T can be zero or null.
    let zero = peer.echo_int_with_timeout(0, Duration::from_secs(2))
        .map_err(|e| format!("call failed: {e}"))?;
    if zero != 0 { return Err("wrong zero value".into()); }

    // For LIDL `result`, a Rust CLIENT receives the envelope as JSON.
    // Ok(envelope) does not imply that envelope["success"] is true.
    let domain = peer.make_result_with_timeout(false, Duration::from_secs(2))
        .map_err(|e| e.to_string())?;
    if domain["success"] != false || domain["error"] != "deliberate domain error" {
        return Err("wrong domain error".into());
    }
    let success = peer.make_result(true).map_err(|e| e.to_string())?;
    if success["success"] != true || success["value"] != 42 {
        return Err("wrong success result".into());
    }
    peer.do_void().map_err(|e| e.to_string())?;

    match peer.slow_with_timeout(500, Duration::from_millis(50)) {
        Err(logos_rust_sdk::LogosError::PluginCallFailed { message, .. }) => {
            // The SDK carries the protocol's structured error as message JSON.
            let error: serde_json::Value = serde_json::from_str(&message)
                .map_err(|e| e.to_string())?;
            if error["code"] != "timeout" { return Err(message); }
        }
        other => return Err(format!("expected timeout: {other:?}")),
    }
    let completed = peer.slow_with_timeout(10, Duration::from_secs(2))
        .map_err(|e| e.to_string())?;
    if completed != 10 { return Err("longer deadline failed".into()); }
    if peer.echo_int(7).map_err(|e| e.to_string())? != 7 {
        return Err("default call failed".into());
    }
    if !matches!(peer.echo_int_with_timeout(0, Duration::ZERO),
                 Err(logos_rust_sdk::LogosError::InvalidTimeout { .. })) {
        return Err("zero timeout should be rejected".into());
    }
    Ok("sync checks passed".into())
}

// The callbacks may run on another thread. Keep shared state behind a mutex.
static ASYNC_STATE: std::sync::Mutex<(usize, bool)> = std::sync::Mutex::new((0, true));
fn record(ok: bool) {
    let mut state = ASYNC_STATE.lock().unwrap();
    state.0 += 1;
    state.1 &= ok;
}
fn start_async(provider: &str) {
    use std::time::Duration;
    *ASYNC_STATE.lock().unwrap() = (0, true);
    let peer = calls::CallsClient::bind(provider);
    peer.echo_int_async_with_timeout(0, Duration::from_secs(2), |r| {
        record(matches!(r, Ok(0)));
    });
    peer.make_result_async_with_timeout(false, Duration::from_secs(2), |r| {
        record(r.map(|v| v["success"] == false
                        && v["error"] == "deliberate domain error").unwrap_or(false));
    });
    peer.slow_async_with_timeout(500, Duration::from_millis(50), |r| {
        // Async errors currently retain the message, not the structured code.
        // This controlled slow call should fail; the sync probe checks the code.
        record(matches!(r, Err(logos_rust_sdk::LogosError::PluginCallFailed { .. })));
    });
}

#[no_mangle]
pub extern "Rust" fn logos_module_install() {
    install::<ApiRust>();
}
