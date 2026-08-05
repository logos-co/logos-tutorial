{
  description = "Aggregator core module - composes calc_module and showcases LogosModuleContext";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";

    # The module this one depends on. Placeholder path — locked to your
    # real checkout in the build step via `--override-input`.
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, calc_module, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
