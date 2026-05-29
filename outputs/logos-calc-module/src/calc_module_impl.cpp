#include "calc_module_impl.h"

int64_t CalcModuleImpl::add(int64_t a, int64_t b)
{
    return calc_add(static_cast<int>(a), static_cast<int>(b));
}

int64_t CalcModuleImpl::multiply(int64_t a, int64_t b)
{
    return calc_multiply(static_cast<int>(a), static_cast<int>(b));
}

int64_t CalcModuleImpl::factorial(int64_t n)
{
    return calc_factorial(static_cast<int>(n));
}

int64_t CalcModuleImpl::fibonacci(int64_t n)
{
    return calc_fibonacci(static_cast<int>(n));
}

std::string CalcModuleImpl::libVersion()
{
    return std::string(calc_version());
}

void CalcModuleImpl::libVersionNotify()
{
    // Emit the event declared in `logos_events:`. When the module is
    // loaded by a host, this reaches every subscriber. When the class
    // is constructed outside a host (e.g. in unit tests), it is a
    // safe no-op.
    versionReady(std::string(calc_version()));
}
