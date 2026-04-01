#include "calc_ui_cpp_plugin.h"
#include "calc_backend.h"
#include "logos_api.h"
#include <QDebug>
#include <QDir>
#include <QQuickWidget>
#include <QQmlContext>
#include <QUrl>

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent) : QObject(parent) {}
CalcUiCppPlugin::~CalcUiCppPlugin() {}

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
}

QWidget* CalcUiCppPlugin::createWidget(LogosAPI* logosAPI)
{
    auto* backend = new CalcBackend(logosAPI);

    auto* quickWidget = new QQuickWidget();
    quickWidget->setResizeMode(QQuickWidget::SizeRootObjectToView);
    quickWidget->rootContext()->setContextProperty("backend", backend);

    // Dev mode: set QML_PATH to the directory containing Main.qml to load
    // from the filesystem without rebuilding. Example: export QML_PATH=$PWD/src/qml
    QString devSource = qgetenv("QML_PATH");
    QUrl qmlUrl = devSource.isEmpty()
        ? QUrl("qrc:/src/qml/Main.qml")
        : QUrl::fromLocalFile(QDir(devSource).filePath("Main.qml"));

    quickWidget->setSource(qmlUrl);

    if (quickWidget->status() == QQuickWidget::Error) {
        qWarning() << "CalcUiCppPlugin: failed to load QML";
        for (const auto& e : quickWidget->errors())
            qWarning() << e.toString();
    }

    return quickWidget;
}

void CalcUiCppPlugin::destroyWidget(QWidget* widget)
{
    delete widget;
}
