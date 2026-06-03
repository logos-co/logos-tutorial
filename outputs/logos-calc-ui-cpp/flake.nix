{
  description = "Calculator C++ UI plugin for Logos - QML view with process-isolated backend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/tutorial-v3";

    # Points at your local calc_module checkout. This is a placeholder —
    # you lock it to your actual path in the next step with
    # `nix flake update --override-input` (see "Lock and build" below).
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, calc_module, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
