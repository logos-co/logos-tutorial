#ifndef CALC_UI_CPP_INTERFACE_H
#define CALC_UI_CPP_INTERFACE_H

#include <QObject>
#include <QString>
#include "interface.h"

class CalcUiCppInterface : public PluginInterface
{
public:
    virtual ~CalcUiCppInterface() = default;
};

#define CalcUiCppInterface_iid "org.logos.CalcUiCppInterface"
Q_DECLARE_INTERFACE(CalcUiCppInterface, CalcUiCppInterface_iid)

#endif // CALC_UI_CPP_INTERFACE_H
