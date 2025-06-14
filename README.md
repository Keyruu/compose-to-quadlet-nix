# Compose to quadlet-nix Converter

A tool to automatically convert Docker Compose files to [quadlet-nix](https://github.com/jordanisaacs/quadlet-nix) configurations.

## Features

- ✅ **Service conversion**: Maps Docker Compose services to quadlet containers
- ✅ **Environment variables**: Extracts and converts env vars to Nix `let` bindings
- ✅ **Dependencies**: Converts `depends_on` to proper systemd unit dependencies
- ✅ **Networks**: Creates bridge networks automatically
- ✅ **Volumes**: Handles both named volumes and bind mounts
- ✅ **Health checks**: Converts Docker health checks to quadlet format
- ✅ **Port mapping**: Converts port mappings (defaults to localhost binding)
- ✅ **Labels**: Adds sensible defaults like update monitoring
- ⚠️ **Partial**: Profiles, secrets, configs (manual adjustment needed)

## Installation

### With Nix (recommended)

```bash
# Use directly with nix run
nix run github:Keyruu/compose-to-quadlet-nix -- docker-compose.yml

# Or install to your profile
nix profile install github:Keyruu/compose-to-quadlet-nix
```

### With Python

```bash
git clone https://github.com/Keyruu/compose-to-quadlet-nix.git
cd compose-to-quadlet-nix
pip install -r requirements.txt
chmod +x compose_to_quadlet.py
```

## Usage

### Basic Usage

```bash
# Convert to stdout
./compose_to_quadlet.py docker-compose.yml

# Convert to file
./compose_to_quadlet.py docker-compose.yml -o output.nix

# Specify project name
./compose_to_quadlet.py docker-compose.yml -n myproject
```

### Integration with your NixOS configuration

After conversion, you'll need to:

1. **Add the generated config** to your NixOS configuration
2. **Configure secrets** (for environment files)
3. **Adjust paths** as needed
4. **Review and customize** the generated configuration

Example integration:

```nix
# In your NixOS configuration
{ config, lib, pkgs, ... }:

{
  # Enable quadlet
  virtualisation.podman.enable = true;
  virtualisation.quadlet.enable = true;
  
  # Configure secrets (using sops-nix as example)
  sops.secrets.immichEnv = {
    sopsFile = ./secrets/immich.yaml;
    owner = "root";
    group = "root";
  };
  
  # Include the generated configuration
  imports = [
    ./generated-immich.nix
  ];
}
```

## Example

Given this `docker-compose.yml`:

```yaml
name: immich
services:
  immich-server:
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-release}
    ports:
      - '2283:2283'
    volumes:
      - ${UPLOAD_LOCATION}:/usr/src/app/upload
    env_file:
      - .env
    depends_on:
      - redis
```

The tool generates:

```nix
virtualisation.quadlet =
  let
    IMMICH_VERSION = "v1.125.7";
    UPLOAD_LOCATION = "/main/immich";
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
          ];
          Requires = [
            "redis.service"
          ];
        };
      };
    };
  };
```

## Configuration Customization

After generation, you'll typically want to customize:

1. **Variable values**: Adjust paths and versions in the `let` bindings
2. **Secrets management**: Configure proper secret paths
3. **Port bindings**: Change from localhost to public if needed
4. **SELinux labels**: Adjust volume mount labels (:z, :Z, :ro)
5. **Resource limits**: Add memory/CPU limits
6. **Additional labels**: Add monitoring or backup labels

## Known Limitations

- **Profiles**: Docker Compose profiles are not supported
- **Secrets/Configs**: Converted to comments for manual handling  
- **Advanced networking**: Complex network configs need manual adjustment
- **Build contexts**: Only supports pre-built images
- **External networks**: Require manual network creation

## Contributing

Pull requests welcome! Areas for improvement:

- Support for more Docker Compose features
- Better variable name suggestions
- Template system for common services
- Integration tests with actual compose files

## License

MIT License - see LICENSE file for details.