#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>  // LogosModuleContext base + `logos_events:`

// Include the C library header (extern "C" already in the header).
extern "C" {
    #include "lib/libcalc.h"
}

class CalcModuleImpl : public LogosModuleContext {
public:
    CalcModuleImpl() = default;
    ~CalcModuleImpl() = default;

    // ── Public API — every method here is callable over IPC ──────────
    // The generator maps C++ types onto the wire automatically:
    //   int64_t  ↔ int      std::string ↔ QString      bool ↔ bool
    int64_t add(int64_t a, int64_t b);
    int64_t multiply(int64_t a, int64_t b);
    int64_t factorial(int64_t n);
    int64_t fibonacci(int64_t n);
    std::string libVersion();

    // Fire-and-forget: looks up the version, then emits it as an event
    // instead of returning it. Used by the QML tutorial (Part 2).
    void libVersionNotify();

    // ── Events ───────────────────────────────────────────────────────
    // Declared like Qt signals. The generator emits the body (in
    // calc_module_events.cpp) that routes the typed args to subscribers
    // via the host's `eventResponse` mechanism. QML subscribes with
    // logos.onModuleEvent("calc_module", "versionReady").
logos_events:
    void versionReady(const std::string& version);
};
