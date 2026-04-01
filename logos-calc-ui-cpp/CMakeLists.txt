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
        src/calc_backend.h
        src/calc_backend.cpp
    INCLUDE_DIRS
        ${CMAKE_CURRENT_SOURCE_DIR}/interfaces
)

find_package(Qt6 REQUIRED COMPONENTS Widgets Quick QuickWidgets)
target_link_libraries(calc_ui_cpp_module_plugin PRIVATE
    Qt6::Widgets
    Qt6::Quick
    Qt6::QuickWidgets
)

qt_add_resources(calc_ui_cpp_module_plugin "qml_resources"
    PREFIX "/"
    FILES
        src/qml/Main.qml
)
