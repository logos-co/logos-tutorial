{
  description = "Calculator C++ UI plugin for Logos - QML view with process-isolated backend for calc_module";

  inputs = {
    logos-app-builder.url = "github:logos-co/logos-app-builder";
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
  };

  outputs = inputs@{ logos-app-builder, calc_module, ... }:
    logos-app-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
