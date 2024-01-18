with (import (import ./pinned-nixpkgs.nix) { });

mkShell {
  inputsFrom = [ (import ./default.nix) ];
  packages = [ python311Packages.black python311Packages.pylint ];
}
