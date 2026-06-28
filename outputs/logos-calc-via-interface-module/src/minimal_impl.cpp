#include "minimal_impl.h"

std::string MinimalImpl::greet(const std::string& name)
{
    std::string greeting = "Hello, " + name + "! Greetings from the minimal module.";

    // The generated event body routes the typed payload to every subscriber.
    greeted(greeting);

    return greeting;
}

std::string MinimalImpl::getStatus()
{
    return "Minimal module is running.";
}
