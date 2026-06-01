#include <logos_test.h>
#include "calc_module_impl.h"

LOGOS_TEST(add_forwards_to_calc_add) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_add").returns(8);

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.add(3, 5), 8);
    LOGOS_ASSERT(t.cFunctionCalled("calc_add"));
}

LOGOS_TEST(multiply_forwards_to_calc_multiply) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_multiply").returns(42);

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.multiply(6, 7), 42);
    LOGOS_ASSERT(t.cFunctionCalled("calc_multiply"));
}

LOGOS_TEST(factorial_returns_mocked_value) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_factorial").returns(120);

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.factorial(5), 120);
}

LOGOS_TEST(libVersion_converts_cstring_to_string) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_version").returns("1.0.0");

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.libVersion(), std::string("1.0.0"));
}
