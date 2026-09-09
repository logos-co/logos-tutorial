#include "calc_observer_impl.h"

#include "logos_sdk.h"

std::string CalcObserverImpl::tryAdd(int64_t a, int64_t b) {
    // Bound the call. A module that is not running costs the full protocol
    // deadline before it fails, and this one is optional by definition.
    logos::CallError err;
    int64_t sum = modules().calc_module.add(a, b, &err, /*timeout_ms=*/1500);

    // "not there" and "there, and it said no" are different answers. Code
    // that cannot tell them apart eventually treats a sick dependency as a
    // missing one.
    if (err.code == "object_unavailable")
        return "calc_module is not running";
    if (!err.ok())
        return "calc_module failed: " + err.code;

    return std::to_string(sum);
}

int64_t CalcObserverImpl::knownModules() {
    auto listing = modules().modules_state.list_modules();

    // `partial` is an honest short answer, not a health flag: it is true when
    // the host's last scan skipped something. A silently short list would be
    // worse than a flagged one.
    if (listing.partial)
        return -1;

    return static_cast<int64_t>(listing.modules.size());
}

std::string CalcObserverImpl::stateOf(const std::string& name) {
    LogosMap record = modules().modules_state.module_record(name);

    // Null is the empty optional — the host's view does not contain this
    // module. It is NOT a failed call, and it is the only spelling of
    // "absent": no record ever carries that as a state.
    if (record.is_null())
        return "absent";

    return record.value("state", "unknown");
}

bool CalcObserverImpl::ready(const std::string& name) {
    return modules().modules_state.is_ready(name);
}

std::string CalcObserverImpl::watchTransitions() {
    // The optional event parameters arrive as LogosMap, which is how an
    // absent value stays distinguishable from an empty one.
    modules().modules_state.onModule_state_changed(
        [this](const std::string& module,
               const LogosMap&, const LogosMap&,
               const std::string& oldState,
               const std::string& newState,
               const LogosMap&, uint64_t) {
            m_lastTransition = module + ": " + oldState + " -> " + newState;
        });
    return "subscribed";
}

std::string CalcObserverImpl::lastTransition() {
    return m_lastTransition;
}
