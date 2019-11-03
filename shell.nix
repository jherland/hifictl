# Run nix-shell without arguments to enter an environment with all the
# following stuff in place.

with import <nixpkgs> {};

stdenv.mkDerivation {
  name = "hifictl-environment";
  buildInputs = [
    # Python requirements (enough to get a virtualenv going).
    python37
    pipenv

    # System requirements.
    socat
    readline
  ];
  src = null;
  shellHook = ''
    # Allow the use of wheels.
    SOURCE_DATE_EPOCH=$(date +%s)

    # Augment the dynamic linker path
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${readline}/lib

    # Prevent "ModuleNotFoundError: No module named 'pip._internal.main'"
    export PYTHONPATH=$(pipenv --venv)/lib/python3.7/site-packages/:$PYTHONPATH

    # Install Pipfile dependencies
    ${pipenv}/bin/pipenv install
    ${pipenv}/bin/pipenv shell
  '';
}
