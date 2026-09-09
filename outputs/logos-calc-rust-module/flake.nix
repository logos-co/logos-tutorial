{
  description = "calc_rust - a Logos module written in Rust";

  # Identical to a C++ module's inputs: the builder provides both the code
  # generator and the logos-rust-sdk source the crate links, so there is no
  # logos-rust-sdk input to keep in sync here.
  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
