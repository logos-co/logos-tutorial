#include "calc_guarded_impl.h"

#include <logos_caller.h>

namespace {
// The five arms. `Host` deliberately carries no name — see the recap.
std::string describe(const logos::LogosCaller& c) {
    switch (c.kind) {
        case logos::CallerKind::Host:     return "host";
        case logos::CallerKind::Module:   return "module " + c.name;
        case logos::CallerKind::Derived:  return "derived " + c.parent + "/" + c.leaf;
        case logos::CallerKind::Operator: return "operator " + c.name;
        default:                          return "unknown";
    }
}
}

std::string CalcGuardedImpl::whoIsCalling() {
    return describe(logos::currentCaller());
}

std::string CalcGuardedImpl::setLimit(int64_t n) {
    const logos::LogosCaller caller = logos::currentCaller();

    // isModule(name) ignores the instance, so a restarted calc_agent is
    // still calc_agent. Anything that is not that module — including the
    // host, and including `unknown` — falls through and is refused.
    if (!caller.isModule("calc_agent"))
        return "refused: " + describe(caller);

    m_limit = n;
    return "ok";
}

int64_t CalcGuardedImpl::limit() { return m_limit; }

void CalcGuardedImpl::onContextReady() {
    // No inbound dispatch is in flight during startup, so there is no caller
    // to report. That answer is `unknown`, in band and fail-closed.
    m_startupCaller = describe(logos::currentCaller());
}

std::string CalcGuardedImpl::startupCaller() { return m_startupCaller; }
