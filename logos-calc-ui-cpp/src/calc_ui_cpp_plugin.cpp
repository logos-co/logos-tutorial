#include "calc_ui_cpp_plugin.h"
#include "logos_api.h"
#include "logos_sdk.h"

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent) : CalcUiCppSimpleSource(parent) {}
CalcUiCppPlugin::~CalcUiCppPlugin() { delete m_logos; }

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    if (m_logos) return;
    m_logosAPI = api;
    m_logos = new LogosModules(api);
    // Register this object as the Remote Objects source so the QML replica
    // can see its properties and call its slots.
    setBackend(this);
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
