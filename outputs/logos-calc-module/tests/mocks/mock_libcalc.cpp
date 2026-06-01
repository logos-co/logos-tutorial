// Link-time replacement for libcalc. Each function records the call
// and returns whatever the active test configured via mockCFunction().
#include <logos_clib_mock.h>

extern "C" {
    #include "lib/libcalc.h"
}

extern "C" int calc_add(int a, int b) {
    LOGOS_CMOCK_RECORD("calc_add");
    return LOGOS_CMOCK_RETURN(int, "calc_add");
}

extern "C" int calc_multiply(int a, int b) {
    LOGOS_CMOCK_RECORD("calc_multiply");
    return LOGOS_CMOCK_RETURN(int, "calc_multiply");
}

extern "C" int calc_factorial(int n) {
    LOGOS_CMOCK_RECORD("calc_factorial");
    return LOGOS_CMOCK_RETURN(int, "calc_factorial");
}

extern "C" int calc_fibonacci(int n) {
    LOGOS_CMOCK_RECORD("calc_fibonacci");
    return LOGOS_CMOCK_RETURN(int, "calc_fibonacci");
}

extern "C" const char* calc_version(void) {
    LOGOS_CMOCK_RECORD("calc_version");
    return LOGOS_CMOCK_RETURN_STRING("calc_version");
}
