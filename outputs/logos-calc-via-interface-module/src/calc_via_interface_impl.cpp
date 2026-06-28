#include "calc_via_interface_impl.h"

// Generated at build time by logos-cpp-generator. Because
// metadata.json lists `interface_dependencies`, LogosModules gains a
// `bind_calculator(moduleName)` factory returning the bound
// `Calculator` wrapper. Included only in the .cpp so the impl header
// the generator parses stays free of generated types.
#include "logos_sdk.h"

// ── Synchronous binds ───────────────────────────────────────────────

int64_t CalcViaInterfaceImpl::sumVia(const std::string& provider,
                                     int64_t a, int64_t b) {
    // Bind once, then call normally — no module name on the call.
    // Every generated method also takes an optional trailing
    // logos::CallError* — the explicit way to tell a failed remote
    // call apart from a legitimate result (without it, a failed
    // call returns the type's default and only logs a warning).
    auto calc = modules().bind_calculator(provider);
    logos::CallError err;
    const int64_t sum = calc.add(a, b, &err);
    if (!err.ok()) return -1;  // e.g. the bound module isn't loaded
    return sum;
}

int64_t CalcViaInterfaceImpl::productVia(const std::string& provider,
                                         int64_t a, int64_t b) {
    return modules().bind_calculator(provider).multiply(a, b);
}

std::string CalcViaInterfaceImpl::versionVia(const std::string& provider) {
    return modules().bind_calculator(provider).libVersion();
}

// ── Asynchronous bind ────────────────────────────────────────────────

std::string CalcViaInterfaceImpl::startFibVia(const std::string& provider,
                                              int64_t n) {
    // The generated async overload is `<method>Async(args...,
    // callback, timeout)`. It returns immediately; the reply lands in
    // the callback on this module's event loop. The bound handle is a
    // temporary, but the call is registered on the LogosAPI-owned
    // client and the callback captures `this`, so it outlives it.
    modules().bind_calculator(provider).fibonacciAsync(n,
        [this](int64_t value) { m_lastFib = value; });
    return "queued";
}

int64_t CalcViaInterfaceImpl::lastFib() const {
    return m_lastFib;
}

// ── Event subscription ───────────────────────────────────────────────

std::string CalcViaInterfaceImpl::watchVersion(const std::string& provider) {
    // onVersionReady(...) is generated from the interface's
    // `logos_events:` block; the callback's arg type matches the event.
    bool ok = modules().bind_calculator(provider).onVersionReady(
        [this](const std::string& version) { m_lastVersion = version; });
    return ok ? "ok" : "failed";
}

std::string CalcViaInterfaceImpl::lastVersion() const {
    return m_lastVersion;
}
