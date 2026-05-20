# Tutorial: Scaffolding Modules with logos-dev-boost

This tutorial shows how to use `logos-dev-boost` to scaffold Logos modules that wrap external C libraries. Instead of manually creating `metadata.json`, `CMakeLists.txt`, `flake.nix`, and C++ wrapper code, the scaffold tool generates everything from a directory containing your library's header and source/binary files.

**What you'll build:**

1. A `calc_wrap` module from the tutorial's `libcalc` library (simple case — C source only)
2. A `sqlcipher_wrap` module from the real [sqlcipher](https://github.com/sqlcipher/sqlcipher) library (realistic case — pre-built `.so` + C wrapper)
3. A `sqlcipher_app` full-app (module + UI) wrapping sqlcipher

**What you'll learn:**

- How `--lib-dir` parses a C header and generates a complete Logos module
- The difference between source-only and pre-built library wrapping
- How to write a thin C facade for libraries with complex APIs (opaque pointers, etc.)
- How to verify the generated module actually works end-to-end

## Prerequisites

- **Nix** with flakes enabled (see [Part 1 prerequisites](tutorial-wrapping-c-library.md#prerequisites))
- **logos-dev-boost** available via Nix — no local clone or npm build required. Verify it works:
  ```bash
  nix run 'github:logos-co/logos-dev-boost' -- --help
  ```
  All scaffold commands in this tutorial use `nix run 'github:logos-co/logos-dev-boost' -- ...`.

---

## Part 1: Wrapping libcalc (source-only library)

This is the simplest case — you have a C header and its `.c` source file, no pre-built binaries.

### 1.1 Prepare the library directory

Create a working directory and write a tiny C calculator library — a header plus its implementation:

```bash
mkdir calc-tutorial && cd calc-tutorial
mkdir -p lib
```

Create `lib/libcalc.h`:

```c
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
```

Create `lib/libcalc.c`:

```c
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
```

Your directory should look like:

```
calc-tutorial/
└── lib/
    ├── libcalc.h    # C header with function declarations
    └── libcalc.c    # C implementation
```

### 1.2 Scaffold the module

```bash
nix run 'github:logos-co/logos-dev-boost' -- init calc_wrap --type module --lib-dir ./lib
```

The scaffold:

1. **Parses `libcalc.h`** — extracts all 5 function declarations
2. **Copies `libcalc.h` and `libcalc.c`** into the project's `lib/` directory
3. **Generates `src/calc_wrap_impl.h`** — a C++ class wrapping each C function
4. **Generates `src/calc_wrap_impl.cpp`** — calls through to the C functions
5. **Generates `CMakeLists.txt`** — compiles the C source alongside the module, enables `LANGUAGES C CXX`
6. **Generates `metadata.json`** — declares the external library with `vendor_path`
7. **Generates `flake.nix`** — standard universal module build with `logos-cpp-generator`
8. **Generates unit tests** — one test per wrapped function

Output:

```
Created 10 files in logos-calc-wrap/
  logos-calc-wrap/lib/libcalc.c
  logos-calc-wrap/lib/libcalc.h
  logos-calc-wrap/metadata.json
  logos-calc-wrap/src/calc_wrap_impl.h
  logos-calc-wrap/src/calc_wrap_impl.cpp
  logos-calc-wrap/CMakeLists.txt
  logos-calc-wrap/flake.nix
  logos-calc-wrap/tests/main.cpp
  logos-calc-wrap/tests/test_calc_wrap.cpp
  logos-calc-wrap/tests/CMakeLists.txt
```

### 1.3 Inspect the generated wrapper

The generated `src/calc_wrap_impl.h`:

```cpp
#pragma once
#include <string>
#include <vector>
#include <cstdint>

extern "C" {
    #include "lib/libcalc.h"
}

class CalcWrapImpl {
public:
    CalcWrapImpl();
    ~CalcWrapImpl();

    int64_t add(int64_t a, int64_t b);
    int64_t multiply(int64_t a, int64_t b);
    int64_t factorial(int64_t n);
    int64_t fibonacci(int64_t n);
    std::string version();

private:
    // Private members
};
```

Notice the type mapping:

| C type | C++ type | Why |
|--------|----------|-----|
| `int` | `int64_t` | `logos-cpp-generator` only supports `int64_t`, not `int` |
| `const char*` (return) | `std::string` | Safe C++ string ownership |
| `const char*` (param) | `const std::string&` | Automatic `.c_str()` conversion |

The generated `src/calc_wrap_impl.cpp` calls through to the C functions with the necessary casts:

```cpp
int64_t CalcWrapImpl::add(int64_t a, int64_t b) {
    return static_cast<int64_t>(::calc_add(static_cast<int>(a), static_cast<int>(b)));
}

std::string CalcWrapImpl::version() {
    return std::string(::calc_version());
}
```

The `::` prefix ensures the C function is called (not a same-named method on the class).

### 1.4 Build and test

```bash
cd logos-calc-wrap
git init && git add -A
nix build
```

Install the `lm` module inspector (one-time):

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm-tool
```

Verify the plugin:

```bash
./lm-tool/bin/lm ./result/lib/calc_wrap_plugin.so
```

Expected output:

```
Plugin Metadata:
================
Name:         calc_wrap
Version:      1.0.0
Type:         core

Plugin Methods:
===============
int add(int a, int b)
int multiply(int a, int b)
int factorial(int n)
int fibonacci(int n)
QString version()
```

Run the unit tests:

```bash
nix build .#unit-tests -L
```

```
PASS  add_works        0ms
PASS  multiply_works   0ms
PASS  factorial_works  0ms
PASS  fibonacci_works  0ms
PASS  version_works    0ms

── Results: 5 passed (0ms) ──────
```

### 1.5 How the generated CMakeLists works

```cmake
cmake_minimum_required(VERSION 3.14)
project(LogosCalcWrapPlugin LANGUAGES C CXX)  # C enabled for libcalc.c

logos_module(
    NAME calc_wrap
    SOURCES
        src/calc_wrap_impl.h
        src/calc_wrap_impl.cpp
        generated_code/calc_wrap_qt_glue.h
        generated_code/calc_wrap_dispatch.cpp
        lib/libcalc.c                          # C source compiled directly
    INCLUDE_DIRS
        ${CMAKE_CURRENT_SOURCE_DIR}/generated_code
        ${CMAKE_CURRENT_SOURCE_DIR}/lib        # So #include "lib/libcalc.h" works
)
```

When the library is source-only (`.c` + `.h`, no `.so`/`.a`), the scaffold compiles the C source directly as part of the Qt plugin. The C functions are statically linked into the final `calc_wrap_plugin.so`.

---

## Part 2: Wrapping sqlcipher (pre-built library)

Real-world libraries like sqlcipher have complex APIs with opaque pointer types (`sqlite3*`), dozens of functions, and their own build systems. The scaffold can't auto-wrap these directly, but the workflow is straightforward:

1. Build the library to get `.so` + headers
2. Write a thin C facade that hides the complexity
3. Point `--lib-dir` at the facade

### 2.1 Build sqlcipher

Use nix to build sqlcipher from nixpkgs:

```bash
nix build nixpkgs#sqlcipher -o /tmp/sqlcipher-built
```

This produces:

```
/tmp/sqlcipher-built/
├── lib/
│   ├── libsqlcipher.so          # The shared library
│   ├── libsqlcipher.a           # Static archive
│   └── ...
└── include/sqlcipher/
    ├── sqlite3.h                # 14,000-line public API header (362 functions)
    └── sqlite3ext.h
```

You could point `--lib-dir` at this directly, but `sqlite3.h` has 362 functions — far too many to wrap as a module. And functions like `sqlite3_open(const char*, sqlite3**)` use opaque pointer types that the scaffold's C parser can't map to C++ automatically.

### 2.2 Write a thin C facade

Create a directory with just what the module needs — a focused header and a small wrapper that manages the `sqlite3*` handle internally:

```bash
mkdir -p /tmp/sqlcipher-lib
cp /tmp/sqlcipher-built/lib/libsqlcipher.so /tmp/sqlcipher-lib/
cp /tmp/sqlcipher-built/lib/libsqlcipher.a  /tmp/sqlcipher-lib/
```

Create `/tmp/sqlcipher-lib/libsqlcipher.h`:

```c
#ifndef LIBSQLCIPHER_H
#define LIBSQLCIPHER_H

#ifdef __cplusplus
extern "C" {
#endif

/* Thin wrapper over sqlcipher's sqlite3 API.
   Manages a single database handle internally. */

/** Open an encrypted database. Returns 0 on success. */
int sc_open(const char* filename, const char* key);

/** Close the current database. */
void sc_close(void);

/** Execute a SQL statement (CREATE, INSERT, UPDATE, DELETE). Returns 0 on success. */
int sc_exec(const char* sql);

/** Query a single string value via SELECT. Caller must NOT free. */
const char* sc_query_string(const char* sql);

/** Query a single integer value via SELECT. */
int sc_query_int(const char* sql);

/** Re-key the database. Returns 0 on success. */
int sc_rekey(const char* new_key);

/** Get the last error message. */
const char* sc_errmsg(void);

/** Return the sqlcipher/sqlite version string. */
const char* sc_version(void);

/** Return the number of rows changed by the last statement. */
int sc_changes(void);

#ifdef __cplusplus
}
#endif

#endif /* LIBSQLCIPHER_H */
```

This header exposes 9 functions using only simple C types (`int`, `const char*`, `void`). All the `sqlite3*` pointer management is hidden inside the implementation.

Create `/tmp/sqlcipher-lib/libsqlcipher.c`:

```c
#include "libsqlcipher.h"
#include <string.h>
#include <stdlib.h>

/* Forward-declare sqlite3 types and functions.
   These symbols resolve at link time against libsqlcipher.so. */
typedef struct sqlite3 sqlite3;
#define SQLITE_OK 0

extern int sqlite3_open(const char* filename, sqlite3** ppDb);
extern int sqlite3_close(sqlite3*);
extern int sqlite3_exec(sqlite3*, const char* sql,
    int (*callback)(void*, int, char**, char**), void* arg, char** errmsg);
extern int sqlite3_key(sqlite3* db, const void* pKey, int nKey);
extern int sqlite3_rekey(sqlite3* db, const void* pKey, int nKey);
extern const char* sqlite3_errmsg(sqlite3*);
extern const char* sqlite3_libversion(void);
extern int sqlite3_changes(sqlite3*);

static sqlite3* g_db = NULL;
static char g_result_buf[4096];

int sc_open(const char* filename, const char* key) {
    if (g_db) sc_close();
    int rc = sqlite3_open(filename, &g_db);
    if (rc != SQLITE_OK) return rc;
    if (key && strlen(key) > 0) {
        rc = sqlite3_key(g_db, key, (int)strlen(key));
    }
    return rc;
}

void sc_close(void) {
    if (g_db) {
        sqlite3_close(g_db);
        g_db = NULL;
    }
}

int sc_exec(const char* sql) {
    if (!g_db) return -1;
    return sqlite3_exec(g_db, sql, NULL, NULL, NULL);
}

static int query_string_cb(void* data, int ncols, char** vals, char** names) {
    (void)data; (void)names;
    if (ncols > 0 && vals[0]) {
        strncpy(g_result_buf, vals[0], sizeof(g_result_buf) - 1);
        g_result_buf[sizeof(g_result_buf) - 1] = '\0';
    }
    return 0;
}

const char* sc_query_string(const char* sql) {
    if (!g_db) return "";
    g_result_buf[0] = '\0';
    sqlite3_exec(g_db, sql, query_string_cb, NULL, NULL);
    return g_result_buf;
}

static int query_int_val = 0;
static int query_int_cb(void* data, int ncols, char** vals, char** names) {
    (void)data; (void)names;
    if (ncols > 0 && vals[0]) {
        query_int_val = atoi(vals[0]);
    }
    return 0;
}

int sc_query_int(const char* sql) {
    if (!g_db) return -1;
    query_int_val = 0;
    sqlite3_exec(g_db, sql, query_int_cb, NULL, NULL);
    return query_int_val;
}

int sc_rekey(const char* new_key) {
    if (!g_db || !new_key) return -1;
    return sqlite3_rekey(g_db, new_key, (int)strlen(new_key));
}

const char* sc_errmsg(void) {
    if (!g_db) return "no database open";
    return sqlite3_errmsg(g_db);
}

const char* sc_version(void) {
    return sqlite3_libversion();
}

int sc_changes(void) {
    if (!g_db) return 0;
    return sqlite3_changes(g_db);
}
```

The key technique: forward-declare `sqlite3` types and functions instead of `#include <sqlite3.h>`. This makes the wrapper self-contained — it compiles with just a C compiler, and the `sqlite3_*` symbols resolve at link time against `libsqlcipher.so`.

Your lib directory should look like:

```
/tmp/sqlcipher-lib/
├── libsqlcipher.h     # Your simplified C API (9 functions)
├── libsqlcipher.c     # Wrapper implementation (forward-declares sqlite3)
├── libsqlcipher.so    # Pre-built sqlcipher (from nix build)
└── libsqlcipher.a     # Pre-built sqlcipher static archive
```

### 2.3 Scaffold the module

```bash
nix run 'github:logos-co/logos-dev-boost' -- init sqlcipher_wrap --type module --lib-dir /tmp/sqlcipher-lib
```

Output:

```
Created 12 files in logos-sqlcipher-wrap/
  logos-sqlcipher-wrap/lib/libsqlcipher.a
  logos-sqlcipher-wrap/lib/libsqlcipher.c
  logos-sqlcipher-wrap/lib/libsqlcipher.h
  logos-sqlcipher-wrap/lib/libsqlcipher.so
  logos-sqlcipher-wrap/metadata.json
  logos-sqlcipher-wrap/src/sqlcipher_wrap_impl.h
  logos-sqlcipher-wrap/src/sqlcipher_wrap_impl.cpp
  logos-sqlcipher-wrap/CMakeLists.txt
  logos-sqlcipher-wrap/flake.nix
  logos-sqlcipher-wrap/tests/main.cpp
  logos-sqlcipher-wrap/tests/test_sqlcipher_wrap.cpp
  logos-sqlcipher-wrap/tests/CMakeLists.txt
```

When the scaffold detects both `.c` source and `.so`/`.a` binaries, the generated CMakeLists does both:

```cmake
logos_module(
    NAME sqlcipher_wrap
    SOURCES
        ...
        lib/libsqlcipher.c          # Compile the wrapper
    INCLUDE_DIRS
        ...
        ${CMAKE_CURRENT_SOURCE_DIR}/lib
    EXTERNAL_LIBS
        sqlcipher                    # Link against libsqlcipher.so
)
```

The wrapper `.c` is compiled as part of the plugin, and `libsqlcipher.so` is linked in to provide the `sqlite3_*` symbols.

### 2.4 Build

```bash
cd logos-sqlcipher-wrap
git init && git add -A
nix build
```

Verify:

```bash
./lm-tool/bin/lm ./result/lib/sqlcipher_wrap_plugin.so
```

```
Plugin Metadata:
================
Name:         sqlcipher_wrap
Version:      1.0.0
Type:         core

Plugin Methods:
===============
int sc_open(QString filename, QString key)
void sc_close()
int sc_exec(QString sql)
QString sc_query_string(QString sql)
int sc_query_int(QString sql)
int sc_rekey(QString new_key)
QString sc_errmsg()
QString sc_version()
int sc_changes()
```

All 9 methods exposed with correct Qt types.

### 2.5 Write real integration tests

The auto-generated tests are smoke tests (call each method once). Replace `tests/test_sqlcipher_wrap.cpp` with real database operations:

```cpp
#include <logos_test.h>
#include "../src/sqlcipher_wrap_impl.h"
#include <cstdio>

LOGOS_TEST(version_returns_string) {
    SqlcipherWrapImpl impl;
    std::string ver = impl.sc_version();
    LOGOS_ASSERT(ver.size() > 0);
}

LOGOS_TEST(open_close_succeeds) {
    SqlcipherWrapImpl impl;
    int64_t rc = impl.sc_open("/tmp/test_sc_open.db", "secret");
    LOGOS_ASSERT_EQ(rc, (int64_t)0);
    impl.sc_close();
    std::remove("/tmp/test_sc_open.db");
}

LOGOS_TEST(create_table_and_insert) {
    SqlcipherWrapImpl impl;
    int64_t rc = impl.sc_open("/tmp/test_sc_crud.db", "mykey");
    LOGOS_ASSERT_EQ(rc, (int64_t)0);

    rc = impl.sc_exec("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)");
    LOGOS_ASSERT_EQ(rc, (int64_t)0);

    rc = impl.sc_exec("INSERT INTO users (name, age) VALUES ('Alice', 30)");
    LOGOS_ASSERT_EQ(rc, (int64_t)0);
    LOGOS_ASSERT_EQ(impl.sc_changes(), (int64_t)1);

    rc = impl.sc_exec("INSERT INTO users (name, age) VALUES ('Bob', 25)");
    LOGOS_ASSERT_EQ(rc, (int64_t)0);

    impl.sc_close();
    std::remove("/tmp/test_sc_crud.db");
}

LOGOS_TEST(query_string_returns_value) {
    SqlcipherWrapImpl impl;
    impl.sc_open("/tmp/test_sc_qstr.db", "pass");
    impl.sc_exec("CREATE TABLE kv (key TEXT, val TEXT)");
    impl.sc_exec("INSERT INTO kv VALUES ('greeting', 'hello world')");

    std::string val = impl.sc_query_string("SELECT val FROM kv WHERE key='greeting'");
    LOGOS_ASSERT_EQ(val, std::string("hello world"));

    impl.sc_close();
    std::remove("/tmp/test_sc_qstr.db");
}

LOGOS_TEST(query_int_returns_value) {
    SqlcipherWrapImpl impl;
    impl.sc_open("/tmp/test_sc_qint.db", "pass");
    impl.sc_exec("CREATE TABLE nums (n INTEGER)");
    impl.sc_exec("INSERT INTO nums VALUES (42)");
    impl.sc_exec("INSERT INTO nums VALUES (8)");

    int64_t count = impl.sc_query_int("SELECT COUNT(*) FROM nums");
    LOGOS_ASSERT_EQ(count, (int64_t)2);

    int64_t sum = impl.sc_query_int("SELECT SUM(n) FROM nums");
    LOGOS_ASSERT_EQ(sum, (int64_t)50);

    impl.sc_close();
    std::remove("/tmp/test_sc_qint.db");
}

LOGOS_TEST(errmsg_after_bad_sql) {
    SqlcipherWrapImpl impl;
    impl.sc_open("/tmp/test_sc_err.db", "pass");
    impl.sc_exec("THIS IS NOT VALID SQL");
    std::string err = impl.sc_errmsg();
    LOGOS_ASSERT(err.size() > 0);
    LOGOS_ASSERT(err.find("error") != std::string::npos || err.find("near") != std::string::npos);

    impl.sc_close();
    std::remove("/tmp/test_sc_err.db");
}

LOGOS_TEST(encrypted_db_unreadable_without_key) {
    SqlcipherWrapImpl impl;
    impl.sc_open("/tmp/test_sc_enc.db", "secretkey");
    impl.sc_exec("CREATE TABLE data (val TEXT)");
    impl.sc_exec("INSERT INTO data VALUES ('sensitive')");
    impl.sc_close();

    // Re-open with correct key — should work
    int64_t rc = impl.sc_open("/tmp/test_sc_enc.db", "secretkey");
    LOGOS_ASSERT_EQ(rc, (int64_t)0);
    std::string val = impl.sc_query_string("SELECT val FROM data");
    LOGOS_ASSERT_EQ(val, std::string("sensitive"));
    impl.sc_close();

    // Re-open with wrong key — query should fail
    impl.sc_open("/tmp/test_sc_enc.db", "wrongkey");
    int64_t bad_rc = impl.sc_exec("SELECT * FROM data");
    LOGOS_ASSERT(bad_rc != 0);
    impl.sc_close();

    std::remove("/tmp/test_sc_enc.db");
}
```

### 2.6 Run the tests

```bash
nix build .#unit-tests -L
```

```
PASS  version_returns_string               0ms
PASS  open_close_succeeds                  6ms
PASS  create_table_and_insert             58ms
PASS  query_string_returns_value          59ms
PASS  query_int_returns_value             60ms
PASS  errmsg_after_bad_sql                 0ms
PASS  encrypted_db_unreadable_without_key 177ms

── Results: 7 passed (360ms) ──────
```

The encryption test proves sqlcipher is actually working — writing encrypted data, reading it back with the correct key, and correctly rejecting access with a wrong key (`hmac check failed`).

---

## Part 3: Full-app scaffold (module + UI)

The `--type full-app` scaffold creates both a backend module and a QML UI app that calls it.

### 3.1 Scaffold

```bash
nix run 'github:logos-co/logos-dev-boost' -- init sqlcipher_app --type full-app --lib-dir /tmp/sqlcipher-lib
```

This creates two sub-projects:

```
logos-sqlcipher-app/
├── sqlcipher_app-module/     # Universal C++ module wrapping sqlcipher
│   ├── lib/                  # libsqlcipher.h, .c, .so, .a
│   ├── src/                  # sqlcipher_app_impl.h/.cpp
│   ├── metadata.json
│   ├── CMakeLists.txt
│   ├── flake.nix
│   └── tests/
├── sqlcipher_app-ui/         # QML + C++ backend UI
│   ├── src/
│   │   ├── sqlcipher_app_ui.rep    # Qt Remote Objects interface
│   │   ├── sqlcipher_app_ui_plugin.h/.cpp
│   │   └── qml/Main.qml
│   ├── metadata.json         # dependencies: ["sqlcipher_app"]
│   ├── CMakeLists.txt
│   └── flake.nix             # includes module as path: input
├── project.json
└── .gitignore
```

The scaffold automatically:

- Generates the `.rep` file with slots matching the library's functions
- Generates the UI plugin calling the backend module via `LogosAPIClient`
- Generates a QML view with input fields and a button for the first method
- Wires the UI's `flake.nix` to depend on the module

### 3.2 Build

```bash
cd logos-sqlcipher-app
git init && git add -A

# Build module first
cd sqlcipher_app-module
nix build

# Build UI (uses module via path: input from parent git repo)
cd ../sqlcipher_app-ui
nix build
```

Both produce plugin `.so` files ready for loading in `logoscore` or basecamp.

---

## How the scaffold decides what to generate

| Input directory contains | Scaffold behavior |
|--------------------------|-------------------|
| `.h` + `.c` only | Compiles `.c` as CMake source (`LANGUAGES C CXX`) |
| `.h` + `.so`/`.a` only | Links pre-built library (`EXTERNAL_LIBS`) |
| `.h` + `.c` + `.so`/`.a` | Both — compiles `.c` wrapper AND links `.so` |
| Multiple `.h` files | Prefers `lib*.h`, then directory-name match, skips internal headers |
| Multiple `.c` files | Only copies the `.c` matching the chosen header basename |

## C type mapping reference

The scaffold maps C types to the types supported by `logos-cpp-generator`:

| C type | C++ param type | C++ return type | Call wrapper |
|--------|---------------|-----------------|--------------|
| `int`, `int32_t` | `int64_t` | `int64_t` | `static_cast<int>(param)` |
| `long`, `int64_t` | `int64_t` | `int64_t` | direct |
| `unsigned int`, `uint32_t` | `uint64_t` | `uint64_t` | `static_cast<unsigned int>(param)` |
| `const char*` | `const std::string&` | `std::string` | `param.c_str()` / `std::string(result)` |
| `double`, `float` | `double` | `double` | direct |
| `bool` | `bool` | `bool` | direct |
| `void` | — | `void` | direct |

> **Why `int64_t` instead of `int`?** The Logos `logos-cpp-generator` tool only supports `int64_t` for integer types. The scaffold inserts `static_cast<int>()` calls to narrow back to `int` when calling the original C functions.

## Tips for wrapping real-world libraries

1. **Write a C facade.** Most libraries use opaque pointers, complex structs, or callback-heavy APIs. Write a thin `.c`/`.h` that exposes only the operations you need using simple types (`int`, `const char*`, `void`).

2. **Forward-declare, don't include.** If your facade calls into the library's internal API, forward-declare the types and functions instead of `#include`-ing the library's headers. This keeps the facade self-contained and avoids header dependency chains.

3. **Pre-build the library.** Use `nix build nixpkgs#libname` or the library's own build system. Place the `.so`/`.a` in your lib directory alongside the facade.

4. **One header per library.** The scaffold picks one `.h` file to parse. If your library has multiple headers, create a single facade header that declares everything the module should expose.

5. **Test the facade first.** Before scaffolding, compile the facade standalone to verify it links correctly:
   ```bash
   gcc -shared -fPIC -o test.so libwrapper.c -L. -lthelib
   ```
