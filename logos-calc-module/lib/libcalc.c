#include "libcalc.h"

int calc_add(int a, int b)
{
    return a + b;
}

int calc_multiply(int a, int b)
{
    return a * b;
}

int calc_factorial(int n)
{
    if (n < 0) return -1;
    if (n <= 1) return 1;
    int result = 1;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

int calc_fibonacci(int n)
{
    if (n < 0) return -1;
    if (n == 0) return 0;
    if (n == 1) return 1;
    int a = 0, b = 1;
    for (int i = 2; i <= n; i++) {
        int tmp = a + b;
        a = b;
        b = tmp;
    }
    return b;
}

const char* calc_version(void)
{
    return "1.0.0";
}
