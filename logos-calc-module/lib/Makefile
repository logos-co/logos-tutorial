# Builds libcalc as a shared library. Invoked by the Nix build via the
# `build_command` in metadata.json ("make shared"), and usable standalone for
# a quick local sanity check.

# Pick the platform-correct shared-library extension.
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  EXT := dylib
else
  EXT := so
endif

# Extra optimization/compile flags — overridable from the environment (the Nix
# stdenv exports CC, and may set CFLAGS/LDFLAGS). The shared-library flags
# (-shared -fPIC) are passed literally on the recipe line below, NOT via
# CFLAGS, so an env-provided CFLAGS can't accidentally drop them and turn this
# into a plain executable named libcalc.so/.dylib.
CFLAGS ?= -O2

shared:
	mkdir -p build
	$(CC) -shared -fPIC $(CFLAGS) $(LDFLAGS) -o build/libcalc.$(EXT) libcalc.c

clean:
	rm -rf build

.PHONY: shared clean
