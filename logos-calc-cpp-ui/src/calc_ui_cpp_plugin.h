#ifndef CALC_UI_CPP_PLUGIN_H
#define CALC_UI_CPP_PLUGIN_H

#include <QObject>
#include <QWidget>
#include <IComponent.h>

class LogosAPI;

class CalcUiCppPlugin : public QObject, public IComponent
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID IComponent_iid FILE "metadata.json")
    Q_INTERFACES(IComponent)

public:
    explicit CalcUiCppPlugin(QObject* parent = nullptr);
    ~CalcUiCppPlugin() override;

    Q_INVOKABLE QWidget* createWidget(LogosAPI* logosAPI = nullptr) override;
    void destroyWidget(QWidget* widget) override;
};

#endif // CALC_UI_CPP_PLUGIN_H
