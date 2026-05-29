{
  description = "Calculator QML UI Plugin for Logos - frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";

    # Option A: point to a remote repo (for CI or when calc_module is published)
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";

    # Option B: point to your local checkout (for local development)
    # calc_module.url = "path:../logos-calc-module";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
