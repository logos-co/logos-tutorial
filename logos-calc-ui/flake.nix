{
  description = "Calculator QML UI Plugin for Logos - frontend for calc_module";

  inputs = {
    logos-app-builder.url = "github:logos-co/logos-app-builder";
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
  };

  outputs = inputs@{ logos-app-builder, ... }:
    logos-app-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
