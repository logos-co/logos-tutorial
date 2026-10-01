{
  description = "Windows builds staged for the tutorials' Windows doc-test leg (logos-windows-ci)";

  # Each input is a repo pinned in tutorial-set.json; CI overrides it with that
  # pin (`tutorial-set.py override-inputs`), so this lock is only a fallback.
  inputs.logos-package.url = "github:logos-co/logos-package";

  # Nix does not run on Windows, so the tools a spec builds with `nix build -o X`
  # are cross-built here instead, under the same name X: logos-windows-ci stages
  # target X as X/, and the spec's ./X/bin/... paths hold on both legs.
  outputs = { logos-package, ... }: {
    packages.x86_64-windows = {
      lgx = logos-package.packages.x86_64-windows.lgx;
    };
  };
}
