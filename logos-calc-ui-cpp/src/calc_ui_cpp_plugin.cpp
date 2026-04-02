#include "calc_ui_cpp_plugin.h"
#include "logos_api.h"
#include "logos_sdk.h"

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent) : QObject(parent) {}
CalcUiCppPlugin::~CalcUiCppPlugin() { delete m_logos; }

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
    m_logos = new LogosModules(api);
}

int CalcUiCppPlugin::add(int a, int b)
{
    return m_logos->calc_module.add(a, b);
}

int CalcUiCppPlugin::multiply(int a, int b)
{
    return m_logos->calc_module.multiply(a, b);
}

int CalcUiCppPlugin::factorial(int n)
{
    return m_logos->calc_module.factorial(n);
}

int CalcUiCppPlugin::fibonacci(int n)
{
    return m_logos->calc_module.fibonacci(n);
}

QString CalcUiCppPlugin::libVersion()
{
    return m_logos->calc_module.libVersion();
}
