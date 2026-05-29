#include "external_lib_plugin.h"
#include "logos_api.h"
#include <QDebug>

// External library C API declarations
// In a real module, these would come from the library's header file
// extern "C" {
//     void* example_init(const char* config);
//     const char* example_process(void* handle, const char* input);
//     void example_cleanup(void* handle);
//     void example_free_string(const char* str);
// }

ExternalLibPlugin::ExternalLibPlugin(QObject* parent)
    : QObject(parent)
{
    qDebug() << "ExternalLibPlugin: Constructor called";
}

ExternalLibPlugin::~ExternalLibPlugin()
{
    qDebug() << "ExternalLibPlugin: Destructor called";
    cleanup();
}

void ExternalLibPlugin::initLogos(LogosAPI* api)
{
    qDebug() << "ExternalLibPlugin: initLogos called";
    // Assign to the inherited `logosAPI` member from PluginInterface — the host
    // reads it directly to dispatch calls; a separate member won't be seen.
    logosAPI = api;
    
    emit eventResponse("initialized", QVariantList() << name() << version());
}

bool ExternalLibPlugin::initLibrary(const QString& config)
{
    qDebug() << "ExternalLibPlugin: initLibrary called with config:" << config;
    
    if (m_initialized) {
        qWarning() << "ExternalLibPlugin: Library already initialized";
        return true;
    }
    
    // In a real module, you would call the external library's init function:
    // m_libHandle = example_init(config.toUtf8().constData());
    // if (!m_libHandle) {
    //     emit eventResponse("error", QVariantList() << "Failed to initialize external library");
    //     return false;
    // }
    
    // For this template, we just simulate success
    m_libHandle = reinterpret_cast<void*>(1);  // Placeholder
    m_initialized = true;
    
    emit eventResponse("library_initialized", QVariantList() << config);
    return true;
}

QString ExternalLibPlugin::processData(const QString& input)
{
    qDebug() << "ExternalLibPlugin: processData called with input:" << input;
    
    if (!m_initialized) {
        qWarning() << "ExternalLibPlugin: Library not initialized";
        return QString();
    }
    
    // In a real module, you would call the external library:
    // const char* result = example_process(m_libHandle, input.toUtf8().constData());
    // QString output = QString::fromUtf8(result);
    // example_free_string(result);  // Don't forget to free memory!
    // return output;
    
    // For this template, we return a placeholder result
    QString output = QString("Processed: %1").arg(input);
    
    emit eventResponse("data_processed", QVariantList() << input << output);
    return output;
}

void ExternalLibPlugin::cleanup()
{
    qDebug() << "ExternalLibPlugin: cleanup called";
    
    if (!m_initialized) {
        return;
    }
    
    // In a real module, you would cleanup the external library:
    // if (m_libHandle) {
    //     example_cleanup(m_libHandle);
    //     m_libHandle = nullptr;
    // }
    
    m_libHandle = nullptr;
    m_initialized = false;
    
    emit eventResponse("library_cleanup", QVariantList());
}
