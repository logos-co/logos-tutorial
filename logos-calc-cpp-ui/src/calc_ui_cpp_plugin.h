#ifndef CALC_UI_CPP_PLUGIN_H
#define CALC_UI_CPP_PLUGIN_H

#include <QObject>
#include <QWidget>
#include <QVariantList>
#include <IComponent.h>
#include "calc_ui_cpp_interface.h"

class CalcUiCppPlugin : public QObject, public CalcUiCppInterface, public IComponent
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID IComponent_iid FILE "metadata.json")
    Q_INTERFACES(CalcUiCppInterface PluginInterface IComponent)

public:
    explicit CalcUiCppPlugin(QObject* parent = nullptr);
    ~CalcUiCppPlugin() override;

    QString name()    const override { return "calc_ui_cpp"; }
    QString version() const override { return "1.0.0"; }

    Q_INVOKABLE void initLogos(LogosAPI* api);

    Q_INVOKABLE QWidget* createWidget(LogosAPI* logosAPI = nullptr);
    Q_INVOKABLE void destroyWidget(QWidget* widget);

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    LogosAPI* m_logosAPI = nullptr;
};

#endif // CALC_UI_CPP_PLUGIN_H
