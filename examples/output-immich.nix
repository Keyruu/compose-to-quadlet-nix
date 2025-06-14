  virtualisation.quadlet =
    let
      IMMICH_VERSION = "v1.125.7";
      UPLOAD_LOCATION = "/main/immich";
      DB_DATA_LOCATION = "${STACK_PATH}/pgdata";
      DB_PASSWORD = "config.sops.secrets.dbPassword.path";
      DB_USERNAME = "postgres";
      DB_DATABASE_NAME = "immich";
      STACK_PATH = "/etc/stacks/immich";
      inherit (config.virtualisation.quadlet) networks;
    in
    {
      networks.immich.networkConfig.driver = "bridge";
      containers = {
        immich-server = {
          containerConfig = {
            image = "ghcr.io/immich-app/immich-server:${IMMICH_VERSION}";
            publishPorts = [
              "127.0.0.1:2283:2283"
            ];
            volumes = [
              "/etc/localtime:/etc/localtime:ro"
              "${UPLOAD_LOCATION}:/usr/src/app/upload:z"
            ];
            environmentFiles = [ config.sops.secrets.envFile.path ];
            networks = [ networks.immich.ref ];
            labels = [
              "wud.tag.include=^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"
            ];
          };
          serviceConfig = {
            Restart = "always";
          };
          unitConfig = {
            After = [
              "redis.service"
              "database.service"
            ];
            Requires = [
              "redis.service"
              "database.service"
            ];
          };
        };

        immich-machine-learning = {
          containerConfig = {
            image = "ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION}";
            volumes = [
              "${STACK_PATH}/model-cache:/cache:z"
            ];
            environmentFiles = [ config.sops.secrets.envFile.path ];
            networks = [ networks.immich.ref ];
            labels = [
              "wud.tag.include=^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"
            ];
          };
          serviceConfig = {
            Restart = "always";
          };
        };

        redis = {
          containerConfig = {
            image = "docker.io/valkey/valkey:8-bookworm@sha256:a19bebed6a91bd5e6e2106fef015f9602a3392deeb7c9ed47548378dcee3dfc2";
            healthCmd = "redis-cli ping || exit 1";
            networks = [ networks.immich.ref ];
            labels = [
              "wud.tag.include=^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"
            ];
          };
          serviceConfig = {
            Restart = "always";
          };
        };

        database = {
          containerConfig = {
            image = "ghcr.io/immich-app/postgres:14-vectorchord0.4.1-pgvectors0.2.0";
            environments = {
              POSTGRES_PASSWORD = "${DB_PASSWORD}";
              POSTGRES_USER = "${DB_USERNAME}";
              POSTGRES_DB = "${DB_DATABASE_NAME}";
              POSTGRES_INITDB_ARGS = "--data-checksums";
            };
            volumes = [
              "${DB_DATA_LOCATION}:/var/lib/postgresql/data:z"
            ];
            networks = [ networks.immich.ref ];
            labels = [
              "wud.tag.include=^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"
            ];
          };
          serviceConfig = {
            Restart = "always";
          };
        };

      };
    };