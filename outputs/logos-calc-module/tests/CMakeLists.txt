cmake_minimum_required(VERSION 3.14)
project(CalcModuleTests LANGUAGES CXX)

include(LogosTest)

logos_test(
    NAME calc_module_tests
    MODULE_SOURCES
        ../src/calc_module_impl.cpp
        mocks/calc_module_events_stub.cpp
    TEST_SOURCES
        main.cpp
        test_calc.cpp
    MOCK_C_SOURCES
        mocks/mock_libcalc.cpp
)
