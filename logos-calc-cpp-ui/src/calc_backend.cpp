#include "calc_backend.h"

CalcBackend::CalcBackend(LogosAPI* api, QObject* parent)
    : QObject(parent), m_logos(new LogosModules(api)) {}

int     CalcBackend::add(int a, int b)      { return m_logos->calc_module.add(a, b); }
int     CalcBackend::multiply(int a, int b) { return m_logos->calc_module.multiply(a, b); }
int     CalcBackend::factorial(int n)       { return m_logos->calc_module.factorial(n); }
int     CalcBackend::fibonacci(int n)       { return m_logos->calc_module.fibonacci(n); }
QString CalcBackend::libVersion()           { return m_logos->calc_module.libVersion(); }
