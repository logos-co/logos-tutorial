{
  description = "Minimal Rust Logos Module - Example using logos-module-builder";

  # Identical to a C++ module's inputs: the builder provides both the code
  # generator and the logos-rust-sdk source the crate links, so there is no
  # logos-rust-sdk input to keep in sync here.
  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
