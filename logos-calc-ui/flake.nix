{
  description = "Calculator QML UI Plugin for Logos - frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    logos-standalone-app.url = "github:logos-co/logos-standalone-app";
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
  };

  outputs = inputs@{ logos-module-builder, logos-standalone-app, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
      logosStandalone = logos-standalone-app;
    };
}
