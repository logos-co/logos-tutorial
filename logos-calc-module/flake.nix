{
  description = "Calculator module - wraps libcalc C library for Logos";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/tutorial-v2";

    # The C library source, built from source by Nix (see metadata.json's
    # build_command). flake = false means "just give me the source tree".
    calc-src = {
      url = "path:./lib";
      flake = false;
    };
  };

  outputs = inputs@{ logos-module-builder, calc-src, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;

      # Hand the C source to the builder. The attribute name (calc) must match
      # the external_libraries[].name in metadata.json.
      externalLibInputs = {
        calc = calc-src;
      };
    };
}
