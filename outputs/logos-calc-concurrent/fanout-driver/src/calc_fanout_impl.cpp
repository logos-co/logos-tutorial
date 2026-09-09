#include "calc_fanout_impl.h"

#include <string>

// Generated at build time. Defines `LogosModules` with one typed accessor
// per metadata.json dependency — here `calc_slow`, a Rust module. Included
// only in the .cpp, so the header the generator parses stays free of it.
#include "logos_sdk.h"

std::string CalcFanoutImpl::fanOut(int64_t n, int64_t ms) {
    for (int64_t i = 0; i < n; ++i) {
        // The generated async caller returns immediately; the reply is
        // delivered to the callback on this module's event loop. Because
        // we never wait, all n calls are in flight at once.
        modules().calc_slow.workAsync(ms, [this](int64_t) { ++m_replies; });
    }
    return "fired " + std::to_string(n);
}

int64_t CalcFanoutImpl::repliesSeen() const {
    return m_replies;
}
