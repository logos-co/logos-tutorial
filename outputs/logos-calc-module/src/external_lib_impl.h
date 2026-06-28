#pragma once

#include <string>
#include "logos_module_context.h"

// Include the external library header here. This would be the actual C header
// from the library you are wrapping:
// #include "lib/libexample.h"

/**
 * @brief A universal Logos module that wraps an external C/C++ library.
 *
 * You write only this implementation class — its public methods are the
 * module's API. The Qt plugin glue is generated from this header. Deriving
 * `LogosModuleContext` gives `modules()` (typed callers for dependencies),
 * typed event subscriptions, and `onContextReady()`.
 *
 * Module code is Qt-free: use `std::string`, not `QString`.
 */
class ExternalLibImpl : public LogosModuleContext
{
public:
    ~ExternalLibImpl();

    /// Initialize the external library. Returns true on success.
    bool initLibrary(const std::string& config);

    /// Call into the external library and return its result.
    std::string processData(const std::string& input);

    /// Release the external library's resources.
    void cleanup();

private:
    void* m_libHandle = nullptr;  // Handle to the external library context
    bool m_initialized = false;
};
