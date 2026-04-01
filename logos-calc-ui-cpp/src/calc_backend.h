#ifndef CALC_BACKEND_H
#define CALC_BACKEND_H

#include <QObject>
#include <QString>
#include "logos_sdk.h"   // generated at build time from metadata.json dependencies

class LogosAPI;

class CalcBackend : public QObject
{
    Q_OBJECT

public:
    explicit CalcBackend(LogosAPI* api, QObject* parent = nullptr);

    Q_INVOKABLE int     add(int a, int b);
    Q_INVOKABLE int     multiply(int a, int b);
    Q_INVOKABLE int     factorial(int n);
    Q_INVOKABLE int     fibonacci(int n);
    Q_INVOKABLE QString libVersion();

private:
    LogosModules* m_logos;   // generated umbrella wrapper
};

#endif // CALC_BACKEND_H
