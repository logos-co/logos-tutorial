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
    //
    // A doc comment directly above a method becomes that method's
    // `description` in the module's method introspection — surfaced
    // by `lm`, `logoscore module-info`, and Basecamp's Methods list.
    // Use `///` (one or more lines) or a `/** ... */` block; the
    // comment's line breaks are preserved. (Plain `//` comments like
    // this block are ignored, so they never leak into the API.)

    /// Adds two integers and returns the sum.
    int64_t add(int64_t a, int64_t b);

    /// Multiplies two integers and returns the product.
    int64_t multiply(int64_t a, int64_t b);

    // A multi-line description: consecutive `///` lines keep their breaks.
    /// Computes the factorial n! of a non-negative integer.
    /// Defined as n * (n-1) * ... * 1, with 0! = 1.
    int64_t factorial(int64_t n);

    /// Returns the nth Fibonacci number (0-indexed).
    int64_t fibonacci(int64_t n);

    // A `/** ... */` block comment works too (line breaks preserved).
    /**
     * Returns the version string of the wrapped libcalc C library.
     * Read straight from the linked native library, not metadata.json.
     */
    std::string libVersion();

    /// Looks up the library version and emits it as a `versionReady`
    /// event instead of returning it. Used by the QML tutorial (Part 2).
    void libVersionNotify();

    // ── Events ───────────────────────────────────────────────────────
    // Declared like Qt signals. The generator emits the body (in
    // calc_module_events.cpp) that routes the typed args to subscribers
    // via the host's `eventResponse` mechanism. QML subscribes with
    // logos.onModuleEvent("calc_module", "versionReady").
    //
    // A `///` doc comment documents the event too — it surfaces as the
    // event's `description` alongside methods (`lm events`, `logoscore
    // module-info`, and Basecamp's Interface screen).
logos_events:
    /// Emitted by libVersionNotify() once the library version is known.
    /// Carries the version string read from libcalc.
    void versionReady(const std::string& version);
};
