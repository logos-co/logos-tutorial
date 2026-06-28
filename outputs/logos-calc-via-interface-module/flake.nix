{
  description = "Core module that binds a calculator interface at runtime";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/0.2.0";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
