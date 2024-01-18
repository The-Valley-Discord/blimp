with (import (import ./pinned-nixpkgs.nix) { });

python311Packages.buildPythonPackage {
  src = builtins.path {
    path = ./.;
    name = "blimp";
  };

  pname = "blimp";
  version = "2.5.2";

  propagatedBuildInputs =
    (with python311Packages; [ discordpy toml setuptools ]);
  format = "pyproject";
}
