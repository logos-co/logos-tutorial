{
  description = "Windows builds staged for the tutorials' Windows doc-test leg (logos-windows-ci)";

  # Each input is a repo pinned in tutorial-set.json; CI overrides it with that
  # pin (`tutorial-set.py override-inputs`), so this lock is only a fallback.
  inputs = {
    logos-package.url = "github:logos-co/logos-package";
    logos-logoscore-cli.url = "github:logos-co/logos-logoscore-cli";
    logos-package-manager.url = "github:logos-co/logos-package-manager";
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  # Nix does not run on Windows, so what a spec builds with `nix build -o X` is
  # cross-built here instead, under the same name X: logos-windows-ci stages
  # target X as X/, and the spec's ./X/... paths hold on both legs. Windows has
  # no Nix store, so every target is the portable build.
  outputs = { logos-package, logos-logoscore-cli, logos-package-manager, logos-module-builder, ... }:
    let
      # The modules the tutorials write, built from their committed outputs/.
      module = dir: deps: logos-module-builder.lib.mkLogosModule {
        src = dir;
        configFile = dir + "/metadata.json";
        flakeInputs = { inherit logos-module-builder; } // deps;
      };
      calc_guarded = module ./outputs/logos-calc-guarded/guarded { };
      calc_agent = module ./outputs/logos-calc-guarded/agent { inherit calc_guarded; };
    in {
      packages.x86_64-windows = {
        lgx = logos-package.packages.x86_64-windows.lgx;
        logos = logos-logoscore-cli.packages.x86_64-windows.cli-bundle-dir;
        pm = logos-package-manager.packages.x86_64-windows.cli-portable;
        g-lgx = calc_guarded.packages.x86_64-windows.lgx-portable;
        a-lgx = calc_agent.packages.x86_64-windows.lgx-portable;
      };
    };
}
