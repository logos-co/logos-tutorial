{
  description = "Calculator C++ UI plugin for Logos - widget frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/tutorial-v1";
    calc_module.url = "github:logos-co/logos-tutorial/tutorial-v1?dir=logos-calc-module";
  };

  outputs = inputs@{ logos-module-builder, calc_module, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
