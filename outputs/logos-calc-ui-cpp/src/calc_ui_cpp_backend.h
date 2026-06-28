#pragma once

#include "rep_calc_ui_cpp_source.h"
#include "logos_ui_plugin_context.h"

// The whole hand-written backend. Derives:
//   - CalcUiCppSimpleSource — generated from calc_ui_cpp.rep; override its
//     slots (the QML replica gets each return value via Qt Remote Objects).
//   - LogosUiPluginContext — supplies modules() (Qt-typed callers + typed event
//     subscriptions for "dependencies") and onContextReady(). A UI plugin is a
//     view, not a module, so that is all the context carries.
// The *Plugin / *Interface classes (Q_PLUGIN_METADATA, initLogos wiring,
// QtRO registration) are generated around it.
class CalcUiCppBackend : public CalcUiCppSimpleSource,
                         public LogosUiPluginContext
{
public:
    // Slots from calc_ui_cpp.rep — each delegates to calc_module.
    int add(int a, int b) override;
    int multiply(int a, int b) override;
    int factorial(int n) override;
    int fibonacci(int n) override;
    QString libVersion() override;

    // Tells calc_module to emit its `versionReady` event.
    void announceVersion() override;

    // Fires once when ui-host hands the plugin its LogosAPI — the
    // typed dependency surface is live, so we arm the event
    // subscription here (before the view's first call).
    void onContextReady() override;

private:
    // Feeds the non-slot surfaces of the .rep after each calculation:
    // bumps the computeCount PROP (setComputeCount, generated) and
    // emits the `computed` SIGNAL. The READWRITE `memory` PROP is
    // driven from QML, so the backend doesn't have to touch it.
    void record(const QString& op, int result);
};
