#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

// An ORDINARY module: no "concurrency" key, so its own handlers are
// dispatched one at a time and it needs no thread-safety. It still drives
// calc_slow concurrently, because concurrency is a property of the CALLEE.
class CalcFanoutImpl : public LogosModuleContext {
public:
    CalcFanoutImpl() = default;
    ~CalcFanoutImpl() = default;

    /// Fires `n` calls to calc_slow.work(ms) without waiting between them,
    /// and returns immediately. Replies land later, on this module's own
    /// event loop.
    std::string fanOut(int64_t n, int64_t ms);

    /// How many of those replies have come back so far.
    int64_t repliesSeen() const;

private:
    int64_t m_replies = 0;
};
