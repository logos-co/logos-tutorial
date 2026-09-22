#include "api_cpp_impl.h"
#include "logos_sdk.h"
#include <chrono>
#include <memory>
#include <mutex>
#include <thread>

std::string ApiCppImpl::echoString(const std::string& v) { return v; }
std::vector<uint8_t> ApiCppImpl::echoBytes(const std::vector<uint8_t>& v) { return v; }
int64_t ApiCppImpl::echoInt(int64_t v) { return v; }
uint64_t ApiCppImpl::echoUint(uint64_t v) { return v; }
double ApiCppImpl::echoDouble(double v) { return v; }
bool ApiCppImpl::echoBool(bool v) { return v; }
nlohmann::json ApiCppImpl::echoAny(const nlohmann::json& v) { return v; }
std::vector<std::string> ApiCppImpl::echoStringList(const std::vector<std::string>& v) { return v; }
std::vector<int64_t> ApiCppImpl::echoIntList(const std::vector<int64_t>& v) { return v; }
std::vector<uint64_t> ApiCppImpl::echoUintList(const std::vector<uint64_t>& v) { return v; }
std::vector<double> ApiCppImpl::echoDoubleList(const std::vector<double>& v) { return v; }
std::vector<bool> ApiCppImpl::echoBoolList(const std::vector<bool>& v) { return v; }
LogosList ApiCppImpl::echoList(const LogosList& v) { return v; }
LogosMap ApiCppImpl::echoMap(const LogosMap& v) { return v; }
std::vector<std::vector<uint8_t>> ApiCppImpl::echoBytesList(const std::vector<std::vector<uint8_t>>& v) { return v; }
std::map<std::string, std::vector<uint8_t>> ApiCppImpl::echoBytesMap(const std::map<std::string, std::vector<uint8_t>>& v) { return v; }
std::map<std::string, int64_t> ApiCppImpl::echoIntMap(const std::map<std::string, int64_t>& v) { return v; }
std::unordered_map<std::string, int64_t> ApiCppImpl::echoUnorderedMap(const std::unordered_map<std::string, int64_t>& v) { return v; }
std::vector<std::vector<int64_t>> ApiCppImpl::echoNested(const std::vector<std::vector<int64_t>>& v) { return v; }
Entry ApiCppImpl::echoEntry(const Entry& v) { return v; }
std::vector<Entry> ApiCppImpl::echoEntries(const std::vector<Entry>& v) { return v; }
std::map<std::string, Entry> ApiCppImpl::echoEntryMap(const std::map<std::string, Entry>& v) { return v; }
Batch ApiCppImpl::echoBatch(const Batch& v) { return v; }
std::optional<std::string> ApiCppImpl::echoOptional(const std::optional<std::string>& v) { return v; }
void ApiCppImpl::doVoid() {}
StdLogosResult ApiCppImpl::makeResult(bool ok) {
    if (!ok) return {false, {}, "deliberate domain error"};
    return {true, 42, ""};
}
int64_t ApiCppImpl::slow(int64_t ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms > 0 ? ms : 0));
    return ms;
}

std::string ApiCppImpl::checkCalls(const std::string& provider) {
    auto peer = modules().bind_calls(provider);
    logos::CallError err;
    // Zero is a valid answer. Only the error channel tells us if it arrived.
    auto zero = peer.echoInt(0, &err, 2000);
    if (!err.ok()) return err.code + ": " + err.message + " (" + err.origin + ")";
    if (zero != 0) return "wrong zero value";

    // A domain error is a SUCCESSFUL call carrying a failed result value.
    auto domain = peer.makeResult(false, &err, 2000);
    if (!err.ok()) return "call failed: " + err.message;
    if (domain.success || domain.error != "deliberate domain error")
        return "wrong domain error";
    auto success = peer.makeResult(true, &err, 2000);
    if (!err.ok() || !success.success || success.value != 42)
        return "wrong success result";

    peer.doVoid(&err, 2000);
    if (!err.ok()) return "void call failed: " + err.message;

    // Warm the peer above before measuring a deadline; discovery takes time.
    peer.slow(500, &err, 50);
    if (err.code != "timeout") return "expected timeout, got: " + err.code;
    // The first handler can still be running. 2 seconds covers it and this call.
    auto completed = peer.slow(10, &err, 2000);
    if (!err.ok() || completed != 10) return "longer deadline failed";
    if (peer.echoInt(7, &err) != 7 || !err.ok()) return "default call failed";
    return "sync checks passed";
}

namespace {
struct Pending {
    std::mutex mutex;
    int done = 0;
    bool ok = true;
};
std::shared_ptr<Pending> pending;
void record(const std::shared_ptr<Pending>& state, bool ok) {
    std::lock_guard<std::mutex> lock(state->mutex);
    state->ok = state->ok && ok;
    ++state->done;
}
}

std::string ApiCppImpl::startAsync(const std::string& provider) {
    auto state = std::make_shared<Pending>();
    pending = state;
    auto peer = modules().bind_calls(provider);
    peer.echoIntAsyncResult(0, [state](logos::AsyncResult<int64_t> r) {
        record(state, r.ok() && r.value == 0);
    }, 2000);
    peer.makeResultAsyncResult(false, [state](logos::AsyncResult<StdLogosResult> r) {
        record(state, r.ok() && !r.value.success
                      && r.value.error == "deliberate domain error");
    }, 2000);
    peer.slowAsyncResult(500, [state](logos::AsyncResult<int64_t> r) {
        record(state, !r.ok() && r.error.code == "timeout");
    }, 50);
    // Return to the event loop. Do not wait here for callbacks.
    return "started";
}
std::string ApiCppImpl::asyncStatus() {
    auto state = pending;
    if (!state) return "not started";
    std::lock_guard<std::mutex> lock(state->mutex);
    if (state->done != 3) return "pending";
    return state->ok ? "async checks passed" : "async checks failed";
}
