#ifndef LIBCALC_H
#define LIBCALC_H

#ifdef __cplusplus
extern "C" {
#endif

/** Add two integers. */
int calc_add(int a, int b);

/** Multiply two integers. */
int calc_multiply(int a, int b);

/** Compute factorial of n (n must be >= 0). Returns -1 on error. */
int calc_factorial(int n);

/** Compute the nth Fibonacci number (n must be >= 0). Returns -1 on error. */
int calc_fibonacci(int n);

/** Return the library version string. Caller must NOT free. */
const char* calc_version(void);

#ifdef __cplusplus
}
#endif

#endif /* LIBCALC_H */
