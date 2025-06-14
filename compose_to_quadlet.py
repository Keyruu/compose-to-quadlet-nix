#!/usr/bin/env python3
"""
Convert Docker Compose files to quadlet-nix configurations.
"""

import yaml
import argparse
import sys
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

class ComposeToQuadletConverter:
    def __init__(self):
        self.variables = {}
        self.networks = set()
        self.volumes = {}
        
    def convert(self, compose_file: str, output_file: str, project_name: str = None) -> str:
        """Convert a Docker Compose file to quadlet-nix format."""
        
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        if not compose_data:
            raise ValueError("Empty or invalid compose file")
        
        # Extract project name
        if not project_name:
            project_name = compose_data.get('name', Path(compose_file).parent.name)
        
        # Extract services
        services = compose_data.get('services', {})
        volumes = compose_data.get('volumes', {})
        
        # Process volumes
        self._process_volumes(volumes, project_name)
        
        # Extract variables and dependencies
        self._extract_variables(services)
        dependencies = self._extract_dependencies(services)
        
        # Generate Nix configuration
        nix_config = self._generate_nix_config(services, project_name, dependencies)
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(nix_config)
        
        return nix_config
    
    def _process_volumes(self, volumes: Dict, project_name: str):
        """Process Docker Compose volumes."""
        for volume_name, volume_config in volumes.items():
            if isinstance(volume_config, dict) and volume_config.get('external'):
                # External volume - use as is
                self.volumes[volume_name] = volume_name
            else:
                # Named volume - create path
                self.volumes[volume_name] = f"${{STACK_PATH}}/{volume_name}"
    
    def _extract_variables(self, services: Dict):
        """Extract environment variables that should become Nix variables."""
        env_vars = set()
        
        for service_name, service_config in services.items():
            # Extract from image tags
            image = service_config.get('image', '')
            env_vars.update(self._find_env_vars(image))
            
            # Extract from volumes
            volumes = service_config.get('volumes', [])
            for volume in volumes:
                if isinstance(volume, str):
                    env_vars.update(self._find_env_vars(volume))
            
            # Extract from environment
            environment = service_config.get('environment', {})
            if isinstance(environment, dict):
                for value in environment.values():
                    if isinstance(value, str):
                        env_vars.update(self._find_env_vars(value))
        
        # Create variable definitions
        for var in env_vars:
            if var not in self.variables:
                self.variables[var] = self._suggest_variable_value(var)
    
    def _find_env_vars(self, text: str) -> set:
        """Find environment variables in text (${VAR} format)."""
        return set(re.findall(r'\$\{([^}]+)(?::-[^}]*)?\}', text))
    
    def _suggest_variable_value(self, var_name: str) -> str:
        """Suggest a value for a variable based on its name."""
        suggestions = {
            'IMMICH_VERSION': '"v1.125.7"',
            'UPLOAD_LOCATION': '"/main/immich"',
            'DB_DATA_LOCATION': '"${STACK_PATH}/pgdata"',
            'STACK_PATH': '"/etc/stacks/immich"',
            'DB_PASSWORD': 'config.sops.secrets.dbPassword.path',
            'DB_USERNAME': '"postgres"',
            'DB_DATABASE_NAME': '"immich"',
        }
        
        return suggestions.get(var_name, f'"{var_name.lower()}"')
    
    def _extract_dependencies(self, services: Dict) -> Dict[str, List[str]]:
        """Extract service dependencies."""
        dependencies = {}
        
        for service_name, service_config in services.items():
            deps = service_config.get('depends_on', [])
            if isinstance(deps, dict):
                deps = list(deps.keys())
            elif isinstance(deps, list):
                pass
            else:
                deps = []
            
            dependencies[service_name] = deps
        
        return dependencies
    
    def _generate_nix_config(self, services: Dict, project_name: str, dependencies: Dict) -> str:
        """Generate the complete Nix configuration."""
        
        # Generate let bindings
        let_bindings = []
        for var, value in self.variables.items():
            let_bindings.append(f'      {var} = {value};')
        
        # Add standard bindings
        let_bindings.extend([
            f'      STACK_PATH = "/etc/stacks/{project_name}";',
            '      inherit (config.virtualisation.quadlet) networks;'
        ])
        
        # Generate network
        self.networks.add(project_name)
        
        # Generate containers
        containers = []
        for service_name, service_config in services.items():
            container_config = self._generate_container_config(
                service_name, service_config, dependencies.get(service_name, []), project_name
            )
            containers.append(container_config)
        
        # Assemble final configuration
        config_parts = [
            '  virtualisation.quadlet =',
            '    let',
            '\n'.join(let_bindings),
            '    in',
            '    {',
            f'      networks.{project_name}.networkConfig.driver = "bridge";',
            '      containers = {',
            '\n'.join(containers),
            '      };',
            '    };'
        ]
        
        return '\n'.join(config_parts)
    
    def _generate_container_config(self, service_name: str, service_config: Dict, 
                                 deps: List[str], project_name: str) -> str:
        """Generate configuration for a single container."""
        
        lines = [f'        {service_name} = {{']
        
        # Container configuration
        lines.append('          containerConfig = {')
        
        # Image
        image = service_config.get('image', '')
        if image:
            # Replace environment variables
            image = self._replace_env_vars(image)
            lines.append(f'            image = "{image}";')
        
        # Ports
        ports = service_config.get('ports', [])
        if ports:
            port_lines = ['            publishPorts = [']
            for port in ports:
                # Convert port format
                if isinstance(port, str) and ':' in port:
                    # Add localhost binding by default
                    if not port.startswith('127.0.0.1:') and not port.startswith('0.0.0.0:'):
                        port = f'127.0.0.1:{port}'
                    port_lines.append(f'              "{port}"')
                else:
                    port_lines.append(f'              "{port}"')
            port_lines.append('            ];')
            lines.extend(port_lines)
        
        # Volumes
        volumes = service_config.get('volumes', [])
        if volumes:
            volume_lines = ['            volumes = [']
            for volume in volumes:
                volume_str = self._convert_volume(volume)
                volume_lines.append(f'              "{volume_str}"')
            volume_lines.append('            ];')
            lines.extend(volume_lines)
        
        # Environment files
        env_file = service_config.get('env_file')
        if env_file:
            lines.append('            environmentFiles = [ config.sops.secrets.envFile.path ];')
        
        # Environment variables
        environment = service_config.get('environment', {})
        if environment:
            if isinstance(environment, dict):
                lines.append('            environments = {')
                for key, value in environment.items():
                    if isinstance(value, str):
                        value = self._replace_env_vars(value)
                        lines.append(f'              {key} = "{value}";')
                    else:
                        lines.append(f'              {key} = "{value}";')
                lines.append('            };')
        
        # Health check
        healthcheck = service_config.get('healthcheck', {})
        if healthcheck and not healthcheck.get('disable'):
            test = healthcheck.get('test')
            if test:
                if isinstance(test, list):
                    test = ' '.join(test[1:])  # Skip CMD/CMD-SHELL
                lines.append(f'            healthCmd = "{test}";')
        
        # Network
        lines.append(f'            networks = [ networks.{project_name}.ref ];')
        
        # Labels (add update monitoring by default)
        lines.extend([
            '            labels = [',
            '              "wud.tag.include=^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"',
            '            ];'
        ])
        
        lines.append('          };')
        
        # Service configuration
        restart = service_config.get('restart')
        if restart:
            lines.extend([
                '          serviceConfig = {',
                f'            Restart = "{restart}";',
                '          };'
            ])
        
        # Unit configuration (dependencies)
        if deps:
            dep_services = [f'              "{dep}.service"' for dep in deps]
            lines.extend([
                '          unitConfig = {',
                '            After = [',
                '\n'.join(dep_services),
                '            ];',
                '            Requires = [',
                '\n'.join(dep_services),
                '            ];',
                '          };'
            ])
        
        lines.append('        };')
        lines.append('')
        
        return '\n'.join(lines)
    
    def _replace_env_vars(self, text: str) -> str:
        """Replace environment variables with Nix variable references."""
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if len(match.groups()) > 1 else None
            
            if var_name in self.variables:
                return f'${{{var_name}}}'
            elif default_value:
                return default_value
            else:
                return f'${{{var_name}}}'
        
        # Handle ${VAR:-default} format
        text = re.sub(r'\$\{([^}]+):-([^}]+)\}', replace_var, text)
        # Handle ${VAR} format
        text = re.sub(r'\$\{([^}]+)\}', replace_var, text)
        
        return text
    
    def _convert_volume(self, volume: str) -> str:
        """Convert a Docker Compose volume to quadlet format."""
        if isinstance(volume, dict):
            # Long format - not implemented yet
            return str(volume)
        
        # Handle named volumes
        for vol_name in self.volumes:
            if volume.startswith(f'{vol_name}:'):
                volume = volume.replace(f'{vol_name}:', f'{self.volumes[vol_name]}:', 1)
                break
        
        # Replace environment variables
        volume = self._replace_env_vars(volume)
        
        # Add :z flag for SELinux if writing to container
        if ':' in volume and not volume.endswith(':ro') and not volume.endswith(':z'):
            parts = volume.split(':')
            if len(parts) == 2 and not parts[0].startswith('/dev') and not parts[0].startswith('/etc'):
                volume += ':z'
        
        return volume


def main():
    parser = argparse.ArgumentParser(description='Convert Docker Compose to quadlet-nix')
    parser.add_argument('compose_file', help='Path to docker-compose.yml file')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('-n', '--name', help='Project name (default: directory name)')
    
    args = parser.parse_args()
    
    if not Path(args.compose_file).exists():
        print(f"Error: {args.compose_file} not found", file=sys.stderr)
        sys.exit(1)
    
    converter = ComposeToQuadletConverter()
    
    try:
        result = converter.convert(args.compose_file, args.output, args.name)
        
        if not args.output:
            print(result)
        else:
            print(f"Converted {args.compose_file} to {args.output}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()