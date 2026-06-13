#include "calc_ui_cpp_backend.h"

// Generated umbrella: LogosModules (behind modules()) from
// metadata.json#dependencies — typed wrappers + typed event accessors.
#include "logos_sdk.h"

int CalcUiCppBackend::add(int a, int b)
{
    return modules().calc_module.add(a, b);
}

int CalcUiCppBackend::multiply(int a, int b)
{
    return modules().calc_module.multiply(a, b);
}

int CalcUiCppBackend::factorial(int n)
{
    return modules().calc_module.factorial(n);
}

int CalcUiCppBackend::fibonacci(int n)
{
    return modules().calc_module.fibonacci(n);
}

QString CalcUiCppBackend::libVersion()
{
    // calc_module is itself a universal (std-typed) module, so its typed
    // wrapper returns std::string. The .rep slot is QString, so convert.
    return QString::fromStdString(modules().calc_module.libVersion());
}
