{
  inputs.logos-module-builder.url = "github:logos-co/logos-module-builder";
  inputs.logos-rust-sdk.url = "github:logos-co/logos-rust-sdk";
  inputs.logos-module-builder.inputs.logos-rust-sdk.follows = "logos-rust-sdk";
  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
