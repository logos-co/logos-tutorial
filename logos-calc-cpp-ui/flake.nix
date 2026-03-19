{
  description = "Calculator C++ UI plugin for Logos - widget frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    nixpkgs.follows = "logos-module-builder/nixpkgs";

    logos-standalone-app.url = "github:logos-co/logos-standalone-app";
    logos-standalone-app.inputs.logos-liblogos.inputs.nixpkgs.follows =
      "logos-module-builder/nixpkgs";

    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
  };

  outputs = { self, logos-module-builder, logos-standalone-app, nixpkgs, calc_module }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
      moduleOutputs = logos-module-builder.lib.mkLogosModule {
        src = ./.;
        configFile = ./module.yaml;
        moduleInputs = { inherit calc_module; };
      };
    in
      moduleOutputs // {
        apps = forAllSystems (system:
          let
            pkgs = import nixpkgs { inherit system; };
            standalone = logos-standalone-app.packages.${system}.default;
            plugin = moduleOutputs.packages.${system}.default;
            pluginDir = pkgs.runCommand "calc-ui-cpp-plugin-dir" {} ''
              mkdir -p $out/icons
              cp ${plugin}/lib/*_plugin.*  $out/
              cp ${./metadata.json} $out/metadata.json
              cp ${./icons/calc.png} $out/icons/calc.png
            '';
            run = pkgs.writeShellScript "run-calc-ui-cpp-standalone" ''
              exec ${standalone}/bin/logos-standalone-app "${pluginDir}" "$@"
            '';
          in { default = { type = "app"; program = "${run}"; }; }
        );
      };
}
