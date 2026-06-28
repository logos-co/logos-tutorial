#pragma once

#include <string>
#include "logos_module_context.h"

/**
 * @brief A minimal universal Logos module.
 *
 * In the universal authoring model you write only this implementation class.
 * Its public methods ARE the module's API — callable by other modules and from
 * the CLI (`logoscore -c`). The Qt plugin glue (the `*Plugin`/`*Interface`
 * classes, `Q_PLUGIN_METADATA`, `initLogos` wiring) is generated from this
 * header by `logos-module-builder`.
 *
 * Deriving `LogosModuleContext` gives you:
 *   - `modules()` — typed callers for anything in `metadata.json#dependencies`
 *   - typed event subscriptions (`modules().dep.on<Event>(...)`)
 *   - `onContextReady()` — override it to run once the module is wired
 *
 * Module code is Qt-free: use `std::string` and friends, not `QString`.
 */
class MinimalImpl : public LogosModuleContext
{
public:
    /// Returns a greeting and announces it as a typed `greeted` event.
    std::string greet(const std::string& name);

    /// Returns a short status string.
    std::string getStatus();

logos_events:
    /// Emitted by greet() with the greeting it produced. Other modules
    /// subscribe with `modules().minimal.onGreeted(...)`.
    void greeted(const std::string& greeting);
};
