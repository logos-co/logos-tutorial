#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

// Two surfaces with two different audiences. The read surface is open;
// the write surface admits exactly one peer module.
class CalcGuardedImpl : public LogosModuleContext {
public:
    /// Reports who the caller is, as this module sees them.
    std::string whoIsCalling();

    /// Guarded: only calc_agent may change the limit.
    std::string setLimit(int64_t n);

    /// Open to everyone.
    int64_t limit();

    /// What currentCaller() answered during onContextReady().
    std::string startupCaller();

    void onContextReady() override;

private:
    int64_t m_limit = 10;
    std::string m_startupCaller;
};
