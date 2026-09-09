#include "calc_agent_impl.h"

#include "logos_sdk.h"

std::string CalcAgentImpl::askWhoIsCalling() {
    return modules().calc_guarded.whoIsCalling();
}

std::string CalcAgentImpl::forwardSetLimit(int64_t n) {
    return modules().calc_guarded.setLimit(n);
}
