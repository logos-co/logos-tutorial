#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>  // LogosModuleContext base → modules()

// Binds the `calculator` interface (interfaces/calculator.h) to a
// module name chosen at runtime and calls it through the generated,
// type-safe bound wrapper. It names no concrete module of its own —
// the provider is whatever string you pass in.
class CalcViaInterfaceImpl : public LogosModuleContext {
public:
    CalcViaInterfaceImpl() = default;
    ~CalcViaInterfaceImpl() = default;

    // ── Synchronous binds ──────────────────────────────────────
    // Bind `calculator` to `provider`, then call it. The module
    // name appears only at bind time, never on the call.
    int64_t     sumVia(const std::string& provider, int64_t a, int64_t b);
    int64_t     productVia(const std::string& provider, int64_t a, int64_t b);
    std::string versionVia(const std::string& provider);

    // ── Asynchronous bind ──────────────────────────────────────
    // Fire calculator.fibonacci(n) asynchronously against `provider`
    // and return immediately ("queued"). Read the reply later with
    // lastFib().
    std::string startFibVia(const std::string& provider, int64_t n);
    int64_t     lastFib() const;

    // ── Event subscription ─────────────────────────────────────
    // Subscribe to the interface's `versionReady` event on
    // `provider` via the generated onVersionReady(...) accessor.
    std::string watchVersion(const std::string& provider);
    std::string lastVersion() const;

private:
    int64_t     m_lastFib = -1;
    std::string m_lastVersion;
};
