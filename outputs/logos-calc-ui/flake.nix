{
  description = "Calculator QML UI Plugin for Logos - frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";

    # Points at your local calc_module checkout. This is a placeholder —
    # you lock it to your actual path in the next step with
    # `nix flake update --override-input` (see "Test with nix run" below).
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
