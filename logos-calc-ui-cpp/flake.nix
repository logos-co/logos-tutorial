{
  description = "Calculator C++ UI plugin for Logos - QML view with process-isolated backend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/tutorial-v2";
    calc_module.url = "github:logos-co/logos-tutorial/tutorial-v2?dir=logos-calc-module";
  };

  outputs = inputs@{ logos-module-builder, calc_module, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
