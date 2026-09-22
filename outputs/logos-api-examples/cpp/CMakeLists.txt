cmake_minimum_required(VERSION 3.14)
project(ApiExample LANGUAGES CXX)
include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
logos_module(NAME api_cpp SOURCES src/api_cpp_impl.h src/api_cpp_impl.cpp)
