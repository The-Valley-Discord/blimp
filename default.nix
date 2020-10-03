with import (builtins.fetchTarball {
  # nixos-unstable on 2020-07-18
  url =
    "https://github.com/NixOS/nixpkgs/tarball/d7e20ee25ed8aa1f0f24a9ca77026c6ef217f6ba";
  sha256 = "1ar7prnrmmlqj17g57nqp82hgy5283dxb94akaqrwpbaz7qfwi4y";
}) { };

poetry2nix.mkPoetryApplication {
  projectDir = ./.;

  # default cleaning of non-source files, but also ignore config and database
  src = lib.cleanSourceWith {
    filter = name: type:
      let baseName = baseNameOf (toString name);
      in !(baseName == "blimp.cfg" || baseName == "blimp.db");

    src = poetry2nix.cleanPythonSources { src = ./.; };
  };
}
