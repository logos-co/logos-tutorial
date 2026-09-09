{
  description = "calc_fanout - drives a concurrent worker from a single-threaded module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_slow.url = "path:/path/to/slow-worker";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
