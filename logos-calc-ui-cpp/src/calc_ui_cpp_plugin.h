#ifndef CALC_UI_CPP_PLUGIN_H
#define CALC_UI_CPP_PLUGIN_H

#include <QString>
#include <QVariantList>
#include "calc_ui_cpp_interface.h"
#include "LogosViewPluginBase.h"
#include "rep_calc_ui_cpp_source.h"

class LogosAPI;
class LogosModules;

// Inherits CalcUiCppSimpleSource (generated from calc_ui_cpp.rep) so
// enableRemoting() can publish the typed source and QML replicas get
// auto-synced properties + callable slots.
class CalcUiCppPlugin : public CalcUiCppSimpleSource,
                        public CalcUiCppInterface,
                        public CalcUiCppViewPluginBase
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID CalcUiCppInterface_iid FILE "metadata.json")
    Q_INTERFACES(CalcUiCppInterface)

public:
    explicit CalcUiCppPlugin(QObject* parent = nullptr);
    ~CalcUiCppPlugin() override;

    QString name()    const override { return "calc_ui_cpp"; }
    QString version() const override { return "1.0.0"; }

    Q_INVOKABLE void initLogos(LogosAPI* api);

    // Slots from calc_ui_cpp.rep — return values directly. The QML replica
    // receives QRemoteObjectPendingReply; use QtRemoteObjects.watch() in QML to get the value.
    int add(int a, int b) override;
    int multiply(int a, int b) override;
    int factorial(int n) override;
    int fibonacci(int n) override;
    QString libVersion() override;

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    LogosAPI* m_logosAPI = nullptr;
    LogosModules* m_logos = nullptr;
};

#endif // CALC_UI_CPP_PLUGIN_H
