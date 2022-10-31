with (import (import ./pinned-nixpkgs.nix) { });

python310Packages.buildPythonPackage {
  src = builtins.path {
    path = ./.;
    name = "blimp";
  };

  pname = "blimp";
  version = "2.5.0";

  propagatedBuildInputs =
    (with python310Packages; [ discordpy toml setuptools ]);
  format = "pyproject";
}
