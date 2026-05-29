#ifndef CALC_MODULE_INTERFACE_H
#define CALC_MODULE_INTERFACE_H

#include <QObject>
#include <QString>
#include "interface.h"

class CalcModuleInterface : public PluginInterface
{
public:
    virtual ~CalcModuleInterface() = default;

    Q_INVOKABLE virtual int add(int a, int b) = 0;
    Q_INVOKABLE virtual int multiply(int a, int b) = 0;
    Q_INVOKABLE virtual int factorial(int n) = 0;
    Q_INVOKABLE virtual int fibonacci(int n) = 0;
    Q_INVOKABLE virtual QString libVersion() = 0;
};

#define CalcModuleInterface_iid "org.logos.CalcModuleInterface"
Q_DECLARE_INTERFACE(CalcModuleInterface, CalcModuleInterface_iid)

#endif // CALC_MODULE_INTERFACE_H
