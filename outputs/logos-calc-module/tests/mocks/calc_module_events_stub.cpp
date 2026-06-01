// Stub bodies for the impl's `logos_events:` methods.
// In the real build the codegen generates calc_module_events.cpp with
// bodies that route through LogosModuleContext. The test build skips
// that codegen, so we provide no-op stubs to satisfy the linker.
#include "calc_module_impl.h"

void CalcModuleImpl::versionReady(const std::string&) {}
