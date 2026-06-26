#include "calc_ui_cpp_backend.h"

// Generated umbrella: LogosModules (behind modules()) from
// metadata.json#dependencies — typed wrappers + typed event accessors.
#include "logos_sdk.h"

int CalcUiCppBackend::add(int a, int b)
{
    int result = modules().calc_module.add(a, b);
    record("add", result);
    return result;
}

int CalcUiCppBackend::multiply(int a, int b)
{
    int result = modules().calc_module.multiply(a, b);
    record("multiply", result);
    return result;
}

int CalcUiCppBackend::factorial(int n)
{
    int result = modules().calc_module.factorial(n);
    record("factorial", result);
    return result;
}

int CalcUiCppBackend::fibonacci(int n)
{
    int result = modules().calc_module.fibonacci(n);
    record("fibonacci", result);
    return result;
}

QString CalcUiCppBackend::libVersion()
{
    // A UI plugin is Qt-typed: modules().calc_module's wrapper returns QString
    // (api-style qt), matching the .rep slot — no conversion needed.
    return modules().calc_module.libVersion();
}

void CalcUiCppBackend::record(const QString& op, int result)
{
    // PROP: bump the slot-driven counter. setComputeCount() is the
    // generated setter; Qt Remote Objects syncs the new value to every
    // replica, so the view's "Computations" label updates with no polling.
    setComputeCount(computeCount() + 1);

    // SIGNAL: a backend → view push, distinct from the return value the
    // QML side gets via logos.watch(). `computed` is declared on the
    // generated SimpleSource, so we just emit it; the typed replica
    // re-emits it and the view's Connections block catches it.
    emit computed(op, result);
}

void CalcUiCppBackend::announceVersion()
{
    // Fire-and-forget call into calc_module: it looks up the library
    // version and emits it as a `versionReady` event. We don't read a
    // return value here — the event comes back through the subscription
    // armed in onContextReady() below.
    modules().calc_module.libVersionNotify();
}

void CalcUiCppBackend::onContextReady()
{
    // Typed module-event subscription. `versionReady` is calc_module's
    // event (Part 1's `logos_events:` block); the generated wrapper
    // exposes it as on<Event> + a Qt-typed callback (QString, because a
    // UI plugin is api-style qt). Push each payload into the versionEvent
    // PROP — Qt Remote Objects then auto-syncs it to the QML replica.
    modules().calc_module.onVersionReady([this](const QString& version) {
        setVersionEvent(version);
    });
}
