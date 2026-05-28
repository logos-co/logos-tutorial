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

# $(CC) and $(CFLAGS) are honored from the environment when set (the Nix
# stdenv exports CC); these are the fallbacks for a plain local build.
CFLAGS ?= -shared -fPIC -O2

shared:
	mkdir -p build
	$(CC) $(CFLAGS) -o build/libcalc.$(EXT) libcalc.c

clean:
	rm -rf build

.PHONY: shared clean
