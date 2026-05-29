#ifndef EXTERNAL_LIB_INTERFACE_H
#define EXTERNAL_LIB_INTERFACE_H

#include <QObject>
#include <QString>
#include "interface.h"

/**
 * @brief Interface for the External Library module
 * 
 * This interface wraps an external C library and exposes it
 * to the Logos ecosystem.
 */
class ExternalLibInterface : public PluginInterface
{
public:
    virtual ~ExternalLibInterface() = default;
    
    /**
     * @brief Initialize the external library
     * @param config Configuration string
     * @return true if initialization succeeded
     */
    Q_INVOKABLE virtual bool initLibrary(const QString& config) = 0;
    
    /**
     * @brief Call a function in the external library
     * @param input Input data
     * @return Output data
     */
    Q_INVOKABLE virtual QString processData(const QString& input) = 0;
    
    /**
     * @brief Cleanup the external library
     */
    Q_INVOKABLE virtual void cleanup() = 0;
};

#define ExternalLibInterface_iid "org.logos.ExternalLibInterface"
Q_DECLARE_INTERFACE(ExternalLibInterface, ExternalLibInterface_iid)

#endif // EXTERNAL_LIB_INTERFACE_H
