{
  description = "calc_agent - the peer calc_guarded admits";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_guarded.url = "path:/path/to/guarded";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
