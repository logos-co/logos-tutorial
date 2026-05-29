#ifndef EXTERNAL_LIB_PLUGIN_H
#define EXTERNAL_LIB_PLUGIN_H

#include <QObject>
#include <QString>
#include "external_lib_interface.h"
#include "module_config.h"

// Include the external library header
// This would be the actual C header from the external library
// #include "lib/libexample.h"

class LogosAPI;

/**
 * @brief Plugin implementation wrapping an external library
 * 
 * This demonstrates how to wrap a C library in a Logos module.
 */
class ExternalLibPlugin : public QObject, public ExternalLibInterface
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID ExternalLibInterface_iid FILE "metadata.json")
    Q_INTERFACES(ExternalLibInterface PluginInterface)

public:
    explicit ExternalLibPlugin(QObject* parent = nullptr);
    ~ExternalLibPlugin() override;

    // PluginInterface implementation
    QString name() const override { return MODULE_NAME; }
    QString version() const override { return MODULE_VERSION; }
    void initLogos(LogosAPI* api) override;

    // ExternalLibInterface implementation
    Q_INVOKABLE bool initLibrary(const QString& config) override;
    Q_INVOKABLE QString processData(const QString& input) override;
    Q_INVOKABLE void cleanup() override;

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    void* m_libHandle = nullptr;  // Handle to external library context
    bool m_initialized = false;
};

#endif // EXTERNAL_LIB_PLUGIN_H
