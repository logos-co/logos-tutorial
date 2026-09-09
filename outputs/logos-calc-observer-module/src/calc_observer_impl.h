#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

// A module with two OPTIONAL dependencies. Both names are concrete, so both
// get the same typed modules().<name> wrapper a required dependency gets —
// but nothing loads them, nothing fails if they are missing, and neither is
// bundled into this module's package.
class CalcObserverImpl : public LogosModuleContext {
public:
    CalcObserverImpl() = default;
    ~CalcObserverImpl() = default;

    // ── An optional dependency you can live without ──────────────────

    /// Adds two numbers via calc_module, or says why it could not.
    std::string tryAdd(int64_t a, int64_t b);

    // ── Reading the host's own registry ──────────────────────────────

    /// How many modules the host knows about, loaded or not.
    int64_t knownModules();

    /// One module's lifecycle state, or "absent" when the host has never
    /// heard of it.
    std::string stateOf(const std::string& name);

    /// Whether the host considers a module up and usable.
    bool ready(const std::string& name);

    /// Subscribes to modules_state's transition event.
    std::string watchTransitions();

    /// The last transition the subscription saw.
    std::string lastTransition();

private:
    std::string m_lastTransition = "(none)";
};
