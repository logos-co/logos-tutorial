#ifndef CALC_UI_CPP_PLUGIN_H
#define CALC_UI_CPP_PLUGIN_H

#include <QObject>
#include <QString>
#include <QVariantList>
#include "calc_ui_cpp_interface.h"

class LogosAPI;
class LogosModules;

class CalcUiCppPlugin : public QObject, public CalcUiCppInterface
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID CalcUiCppInterface_iid FILE "metadata.json")
    Q_INTERFACES(CalcUiCppInterface PluginInterface)

public:
    explicit CalcUiCppPlugin(QObject* parent = nullptr);
    ~CalcUiCppPlugin() override;

    QString name()    const override { return "calc_ui_cpp"; }
    QString version() const override { return "1.0.0"; }

    Q_INVOKABLE void initLogos(LogosAPI* api);

    Q_INVOKABLE int add(int a, int b);
    Q_INVOKABLE int multiply(int a, int b);
    Q_INVOKABLE int factorial(int n);
    Q_INVOKABLE int fibonacci(int n);
    Q_INVOKABLE QString libVersion();

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    LogosAPI* m_logosAPI = nullptr;
    LogosModules* m_logos = nullptr;
};

#endif // CALC_UI_CPP_PLUGIN_H
