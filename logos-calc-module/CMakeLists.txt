cmake_minimum_required(VERSION 3.14)
project(CalcModulePlugin LANGUAGES CXX)

# Include the Logos Module CMake helper (provided by logos-module-builder)
if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

# Define the module with its external library dependency
logos_module(
    NAME calc_module
    SOURCES
        src/calc_module_interface.h
        src/calc_module_plugin.h
        src/calc_module_plugin.cpp
    EXTERNAL_LIBS
        calc
)
