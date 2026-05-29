#include "calc_module_plugin.h"
#include "logos_api.h"
#include <QDebug>

CalcModulePlugin::CalcModulePlugin(QObject* parent)
    : QObject(parent)
{
    qDebug() << "CalcModulePlugin: created";
}

CalcModulePlugin::~CalcModulePlugin()
{
    qDebug() << "CalcModulePlugin: destroyed";
}

void CalcModulePlugin::initLogos(LogosAPI* api)
{
    // IMPORTANT: Assign to the inherited `logosAPI` member, NOT your own class member.
    // `logosAPI` is a public member variable of the `PluginInterface` base class
    // (declared in the SDK's core/interface.h); the Logos host reads it directly to
    // dispatch calls. Storing the pointer in a separate `m_logosAPI` member will NOT work.
    logosAPI = api;
    qDebug() << "CalcModulePlugin: LogosAPI initialized";
}

int CalcModulePlugin::add(int a, int b)
{
    int result = calc_add(a, b);
    qDebug() << "CalcModulePlugin::add" << a << "+" << b << "=" << result;
    return result;
}

int CalcModulePlugin::multiply(int a, int b)
{
    int result = calc_multiply(a, b);
    qDebug() << "CalcModulePlugin::multiply" << a << "*" << b << "=" << result;
    return result;
}

int CalcModulePlugin::factorial(int n)
{
    int result = calc_factorial(n);
    qDebug() << "CalcModulePlugin::factorial" << n << "! =" << result;
    return result;
}

int CalcModulePlugin::fibonacci(int n)
{
    int result = calc_fibonacci(n);
    qDebug() << "CalcModulePlugin::fibonacci fib(" << n << ") =" << result;
    return result;
}

QString CalcModulePlugin::libVersion()
{
    const char* ver = calc_version();
    QString result = QString::fromUtf8(ver);
    qDebug() << "CalcModulePlugin::libVersion" << result;
    return result;
}

void CalcModulePlugin::libVersionNotify()
{
    const char* ver = calc_version();
    QString result = QString::fromUtf8(ver);
    qDebug() << "CalcModulePlugin::libVersionNotify" << result;
    emit eventResponse("versionReady", {result});
}
