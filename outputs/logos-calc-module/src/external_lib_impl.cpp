#include "external_lib_impl.h"

// External library C API declarations.
// In a real module these come from the library's header file:
// extern "C" {
//     void* example_init(const char* config);
//     const char* example_process(void* handle, const char* input);
//     void example_cleanup(void* handle);
//     void example_free_string(const char* str);
// }

ExternalLibImpl::~ExternalLibImpl()
{
    cleanup();
}

bool ExternalLibImpl::initLibrary(const std::string& config)
{
    if (m_initialized) {
        return true;
    }

    // In a real module you would call the external library's init function:
    // m_libHandle = example_init(config.c_str());
    // if (!m_libHandle) return false;
    (void)config;

    // For this template we just simulate success.
    m_libHandle = reinterpret_cast<void*>(1);  // Placeholder
    m_initialized = true;
    return true;
}

std::string ExternalLibImpl::processData(const std::string& input)
{
    if (!m_initialized) {
        return std::string();
    }

    // In a real module you would call the external library:
    // const char* result = example_process(m_libHandle, input.c_str());
    // std::string output(result);
    // example_free_string(result);   // don't forget to free!
    // return output;

    // For this template we return a placeholder result.
    return "Processed: " + input;
}

void ExternalLibImpl::cleanup()
{
    if (!m_initialized) {
        return;
    }

    // In a real module you would release the external library:
    // if (m_libHandle) { example_cleanup(m_libHandle); m_libHandle = nullptr; }

    m_libHandle = nullptr;
    m_initialized = false;
}
