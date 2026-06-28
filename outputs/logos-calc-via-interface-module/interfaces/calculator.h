#pragma once

// A DEPENDENCY INTERFACE: a method/event contract that names no
// module. Any module whose API is a superset of this can satisfy
// it; the consumer binds it to a concrete module name at runtime.
//
// Written in the module's own language (pure C++). The generator
// reads the public methods + the `logos_events:` block and emits a
// BOUND wrapper class `Calculator` whose target module name is a
// runtime constructor argument — not baked in.
//
// Types are std (int64_t / std::string) because the consuming
// module is `interface: "universal"`; the bound wrapper inherits
// that api-style.

#include <cstdint>
#include <string>

// Defines the `logos_events` token (expands to `public`) so this
// header is valid C++ on its own, not only as generator input.
#include <logos_module_context.h>

class ICalculator {
public:
    int64_t add(int64_t a, int64_t b);
    int64_t multiply(int64_t a, int64_t b);
    int64_t fibonacci(int64_t n);
    std::string libVersion();

logos_events:
    // Emitted by the provider; the consumer subscribes through the
    // bound wrapper's generated onVersionReady(...) accessor.
    void versionReady(const std::string& version);
};
