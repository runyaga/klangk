{ pkgs, ... }: {
  languages.dart = {
    enable = true;
    package = pkgs.flutter;
  };
  languages.python = {
    enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
    directory = "./backend";
  };

  packages = with pkgs; [
    docker-client
  ];

  tasks = {
    "bark:flutter-build" = {
      exec = "flutterbuildweb";
      execIfModified = [
        "frontend/lib"
        "frontend/web"
        "frontend/pubspec.yaml"
        "frontend/pubspec.lock"
      ];
    };
    "bark:docker-build" = {
      exec = "dockerbuild";
      execIfModified = [
        "docker/Dockerfile"
        "docker/entrypoint.sh"
        "docker/extensions"
        "docker/tools"
      ];
    };
  };

  processes = {
    backend = {
      exec = ''
        cd $DEVENV_ROOT/backend && uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8997
      '';
      after = [
        "bark:flutter-build"
        "bark:docker-build"
      ];
    };
  };

  dotenv.enable = true;

  scripts.flutterbuildweb.exec = ''
    cd $DEVENV_ROOT
    cd frontend && flutter pub get && flutter build web
    rm -f build/web/flutter_service_worker.js
  '';

  scripts.dockerbuild.exec = ''
    cd $DEVENV_ROOT
    docker build --platform linux/amd64 -t bark-pi docker/
  '';

  scripts.rebuild.exec = ''
    echo "Rebuilding Bark..."
    echo "==> Docker image"
    dockerbuild
    echo "==> Flutter web"
    flutterbuildweb
    echo "==> Done"
  '';

  enterShell = ''
    export BARK_DATA_DIR="''${DEVENV_STATE}/.bark"
    mkdir -p "$BARK_DATA_DIR"
    echo "Bark dev environment ready"
    echo "Run 'rebuild' to rebuild all sofware."
    echo "Run 'devenv processes up' to start backend + frontend"
  '';
}
