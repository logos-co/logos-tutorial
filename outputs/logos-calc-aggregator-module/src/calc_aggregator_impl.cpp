#include "calc_aggregator_impl.h"

#include <fstream>

// Generated at build time by logos-cpp-generator. Defines `LogosModules`
// with one std-typed accessor per metadata.json dependency — here
// `calc_module`. Included only in the .cpp so the impl header the
// generator parses stays free of Qt and codegen types.
#include "logos_sdk.h"

namespace {
// The run-count file lives inside the host-provisioned persistence dir.
// An empty dir means the module was constructed outside a host (e.g. a
// unit test) — treat that as "nothing to persist".
std::string runCountPath(const std::string& dir) {
    return dir.empty() ? std::string() : dir + "/runcount.txt";
}
}  // namespace

void CalcAggregatorImpl::onContextReady() {
    // The three context getters are populated now. Load any previously
    // persisted run count so bumpRunCount() continues across restarts.
    const std::string path = runCountPath(instancePersistencePath());
    if (path.empty()) return;
    std::ifstream in(path);
    if (in) in >> m_runCount;
}

// ── Context getters — thin pass-throughs to the SDK base class ──────

std::string CalcAggregatorImpl::moduleDir() const {
    return modulePath();
}

std::string CalcAggregatorImpl::instanceID() const {
    return instanceId();
}

bool CalcAggregatorImpl::hasInstanceID() const {
    return !instanceId().empty();
}

std::string CalcAggregatorImpl::persistenceDir() const {
    return instancePersistencePath();
}

int64_t CalcAggregatorImpl::bumpRunCount() {
    ++m_runCount;
    const std::string path = runCountPath(instancePersistencePath());
    if (!path.empty()) {
        std::ofstream out(path, std::ios::trunc);
        out << m_runCount;
    }
    return m_runCount;
}

// ── Sync composition: five calls into one map ───────────────────────

LogosMap CalcAggregatorImpl::computeReport(int64_t a, int64_t b, int64_t n) {
    // modules().calc_module is the generated, std-typed wrapper for the
    // `calc_module` dependency — no raw LogosAPI, no QVariant. Five
    // synchronous calls, composed into one map the caller gets back.
    auto& calc = modules().calc_module;
    LogosMap report;
    report["sum"]        = calc.add(a, b);
    report["product"]    = calc.multiply(a, b);
    report["factorial"]  = calc.factorial(n);
    report["fibonacci"]  = calc.fibonacci(n);
    report["libVersion"] = calc.libVersion();
    return report;
}

// ── Async composition: fire now, read the reply later ───────────────

std::string CalcAggregatorImpl::startAsyncFibonacci(int64_t n) {
    // The generated async overload is `<method>Async(args...,
    // callback, timeout = Timeout())`. It returns immediately; the
    // reply is delivered to the callback on this module's event loop.
    modules().calc_module.fibonacciAsync(n, [this](int64_t value) {
        m_asyncResult = value;
    });
    return "queued";
}

int64_t CalcAggregatorImpl::asyncResult() const {
    return m_asyncResult;
}

// ── Event subscription on a dependency ──────────────────────────────

std::string CalcAggregatorImpl::subscribeVersion() {
    if (m_subscribed) return "ok";
    // Typed subscriber generated from calc_module's `logos_events:`
    // versionReady(const std::string&). The accessor is `on` + the
    // capitalized event name; the callback's arg types match the event.
    m_subscribed = modules().calc_module.onVersionReady(
        [this](const std::string& version) {
            m_lastVersionEvent = version;
        });
    return m_subscribed ? "ok" : "failed";
}

std::string CalcAggregatorImpl::lastVersionEvent() const {
    return m_lastVersionEvent;
}
