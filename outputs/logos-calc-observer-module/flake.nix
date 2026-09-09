{
  description = "calc_observer - optional dependencies and the module registry";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    modules_state.url = "github:logos-co/logos-modules-state-module";
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
