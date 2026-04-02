cmake_minimum_required(VERSION 3.14)
project(CalcUiCppPlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found. Set LOGOS_MODULE_BUILDER_ROOT.")
endif()

logos_module(
    NAME calc_ui_cpp
    SOURCES
        src/calc_ui_cpp_interface.h
        src/calc_ui_cpp_plugin.h
        src/calc_ui_cpp_plugin.cpp
)
