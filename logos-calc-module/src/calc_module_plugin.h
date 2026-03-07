#ifndef CALC_MODULE_PLUGIN_H
#define CALC_MODULE_PLUGIN_H

#include <QObject>
#include <QString>
#include "calc_module_interface.h"

// Include the C library header
#include "lib/libcalc.h"

class LogosAPI;

class CalcModulePlugin : public QObject, public CalcModuleInterface
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID CalcModuleInterface_iid FILE "metadata.json")
    Q_INTERFACES(CalcModuleInterface PluginInterface)

public:
    explicit CalcModulePlugin(QObject* parent = nullptr);
    ~CalcModulePlugin() override;

    // PluginInterface — required by every module
    QString name() const override { return "calc_module"; }
    QString version() const override { return "1.0.0"; }

    // Called by the Logos host when the module is loaded.
    // NOT marked override — it is invoked reflectively via QMetaObject.
    Q_INVOKABLE void initLogos(LogosAPI* api);

    // CalcModuleInterface — each wraps a libcalc C function
    Q_INVOKABLE int add(int a, int b) override;
    Q_INVOKABLE int multiply(int a, int b) override;
    Q_INVOKABLE int factorial(int n) override;
    Q_INVOKABLE int fibonacci(int n) override;
    Q_INVOKABLE QString libVersion() override;

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

};

#endif // CALC_MODULE_PLUGIN_H
