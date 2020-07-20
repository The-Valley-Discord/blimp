with import (builtins.fetchTarball {
  # nixos-unstable on 2020-07-18
  url = "https://github.com/NixOS/nixpkgs/tarball/d7e20ee25ed8aa1f0f24a9ca77026c6ef217f6ba";
  sha256 = "1ar7prnrmmlqj17g57nqp82hgy5283dxb94akaqrwpbaz7qfwi4y";
}) {};

mkShell {
  buildInputs = [ python3 python3Packages.discordpy python3Packages.black python3Packages.pylint ];
}