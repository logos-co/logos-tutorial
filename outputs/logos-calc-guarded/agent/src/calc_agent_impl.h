#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

class CalcAgentImpl : public LogosModuleContext {
public:
    /// Asks calc_guarded who IT thinks is calling.
    std::string askWhoIsCalling();

    /// Forwards a setLimit through, so the guard sees a module.
    std::string forwardSetLimit(int64_t n);
};
