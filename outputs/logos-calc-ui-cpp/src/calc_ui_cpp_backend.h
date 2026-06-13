#pragma once

#include "rep_calc_ui_cpp_source.h"
#include "logos_module_context.h"

// The whole hand-written backend. Derives:
//   - CalcUiCppSimpleSource — generated from calc_ui_cpp.rep; override its
//     slots (the QML replica gets each return value via Qt Remote Objects).
//   - LogosModuleContext — supplies modules() (typed callers + typed event
//     subscriptions for "dependencies") and onContextReady().
// The *Plugin / *Interface classes (Q_PLUGIN_METADATA, initLogos wiring,
// QtRO registration) are generated around it.
class CalcUiCppBackend : public CalcUiCppSimpleSource,
                         public LogosModuleContext
{
public:
    // Slots from calc_ui_cpp.rep — each delegates to calc_module.
    int add(int a, int b) override;
    int multiply(int a, int b) override;
    int factorial(int n) override;
    int fibonacci(int n) override;
    QString libVersion() override;
};
