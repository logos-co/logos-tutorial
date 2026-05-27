cmake_minimum_required(VERSION 3.14)
project(CalcModulePlugin LANGUAGES CXX C)

# Include the Logos Module CMake helper (provided by logos-module-builder)
if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

# Build the external C library as a static library
add_library(calc STATIC lib/libcalc.c)
target_include_directories(calc PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/lib)

# Define the module with its statically-linked library dependency
logos_module(
    NAME calc_module
    SOURCES
        src/calc_module_interface.h
        src/calc_module_plugin.h
        src/calc_module_plugin.cpp
    LINK_TARGETS
        calc
)
