{
  description = "Convert Docker Compose files to quadlet-nix configurations";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        compose-to-quadlet-nix = pkgs.python3Packages.buildPythonApplication {
          pname = "compose-to-quadlet-nix";
          version = "0.1.0";
          
          src = ./.;
          
          propagatedBuildInputs = with pkgs.python3Packages; [
            pyyaml
          ];
          
          doCheck = false;
          
          meta = with pkgs.lib; {
            description = "Convert Docker Compose files to quadlet-nix configurations";
            homepage = "https://github.com/Keyruu/compose-to-quadlet-nix";
            license = licenses.mit;
            maintainers = [ ];
          };
        };
      in
      {
        packages = {
          default = compose-to-quadlet-nix;
          compose-to-quadlet-nix = compose-to-quadlet-nix;
        };

        apps = {
          default = {
            type = "app";
            program = "${compose-to-quadlet-nix}/bin/compose_to_quadlet.py";
          };
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python3
            python3Packages.pyyaml
            python3Packages.black
            python3Packages.isort
            python3Packages.flake8
          ];
        };
      });
}