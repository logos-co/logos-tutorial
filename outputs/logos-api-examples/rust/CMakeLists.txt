cmake_minimum_required(VERSION 3.14)
project(ApiExample LANGUAGES CXX)
include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
logos_module(NAME api_rust)
