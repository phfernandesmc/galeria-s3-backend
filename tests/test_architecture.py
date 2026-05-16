"""Architecture Tests - Validação de separação de módulos e imports.

Verifica que a Clean Architecture é respeitada: dependências unidirecionais,
sem imports circulares, e cada módulo importa apenas dos módulos permitidos.

Usa AST parsing para inspecionar imports sem executar os módulos,
evitando problemas com variáveis de ambiente e side effects.

Validates: Requirements 13.2, 13.3, 13.4, 13.5, 13.6
"""

import ast
from pathlib import Path

import pytest

# Diretório raiz do pacote app/
APP_DIR = Path(__file__).parent.parent / "app"

# Módulos esperados na estrutura do projeto
EXPECTED_MODULES = [
    "__init__.py",
    "config.py",
    "models.py",
    "validators.py",
    "s3_service.py",
    "database.py",
    "router.py",
]


def _get_internal_imports(filepath: Path) -> set[str]:
    """Extrai todos os imports de módulos internos (app.*) de um arquivo Python via AST.

    Retorna um set com os nomes dos módulos internos importados.
    Exemplo: {'app.config', 'app.models'}
    """
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))

    internal_imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app"):
                    # Extrai o módulo de nível superior: app.config -> app.config
                    parts = alias.name.split(".")
                    if len(parts) >= 2:
                        internal_imports.add(f"{parts[0]}.{parts[1]}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app"):
                parts = node.module.split(".")
                if len(parts) >= 2:
                    internal_imports.add(f"{parts[0]}.{parts[1]}")

    return internal_imports


class TestModuleExistence:
    """Verifica que todos os módulos esperados existem no path app/."""

    @pytest.mark.parametrize("module_name", EXPECTED_MODULES)
    def test_module_exists(self, module_name: str):
        """Cada módulo esperado deve existir em app/."""
        module_path = APP_DIR / module_name
        assert module_path.exists(), (
            f"Módulo esperado não encontrado: app/{module_name}"
        )


class TestModelsModuleImports:
    """Validates: Requirement 13.6 - models.py não importa de nenhum módulo interno."""

    def test_models_has_no_internal_imports(self):
        """models.py não deve importar de nenhum módulo app.* interno."""
        models_path = APP_DIR / "models.py"
        internal_imports = _get_internal_imports(models_path)

        assert internal_imports == set(), (
            f"models.py não deve importar de módulos internos, "
            f"mas importa de: {sorted(internal_imports)}"
        )


class TestValidatorsModuleImports:
    """Validates: Requirement 13.5 - validators.py importa apenas de config e models."""

    ALLOWED_IMPORTS = {"app.config", "app.models"}

    def test_validators_imports_only_allowed_modules(self):
        """validators.py deve importar apenas de app.config e app.models."""
        validators_path = APP_DIR / "validators.py"
        internal_imports = _get_internal_imports(validators_path)

        disallowed = internal_imports - self.ALLOWED_IMPORTS
        assert disallowed == set(), (
            f"validators.py importa de módulos não permitidos: {sorted(disallowed)}. "
            f"Apenas {sorted(self.ALLOWED_IMPORTS)} são permitidos."
        )


class TestS3ServiceModuleImports:
    """Validates: Requirement 13.3 - s3_service.py importa apenas de config e models."""

    ALLOWED_IMPORTS = {"app.config", "app.models"}

    def test_s3_service_imports_only_allowed_modules(self):
        """s3_service.py deve importar apenas de app.config e app.models."""
        s3_path = APP_DIR / "s3_service.py"
        internal_imports = _get_internal_imports(s3_path)

        disallowed = internal_imports - self.ALLOWED_IMPORTS
        assert disallowed == set(), (
            f"s3_service.py importa de módulos não permitidos: {sorted(disallowed)}. "
            f"Apenas {sorted(self.ALLOWED_IMPORTS)} são permitidos."
        )


class TestDatabaseModuleImports:
    """Validates: Requirement 13.4 - database.py importa apenas de config e models."""

    ALLOWED_IMPORTS = {"app.config", "app.models"}

    def test_database_imports_only_allowed_modules(self):
        """database.py deve importar apenas de app.config e app.models."""
        db_path = APP_DIR / "database.py"
        internal_imports = _get_internal_imports(db_path)

        disallowed = internal_imports - self.ALLOWED_IMPORTS
        assert disallowed == set(), (
            f"database.py importa de módulos não permitidos: {sorted(disallowed)}. "
            f"Apenas {sorted(self.ALLOWED_IMPORTS)} são permitidos."
        )


class TestRouterModuleImports:
    """Validates: Requirement 13.2 - router.py importa de validators, s3_service, database e models."""

    ALLOWED_IMPORTS = {
        "app.validators",
        "app.s3_service",
        "app.database",
        "app.models",
    }

    def test_router_imports_only_allowed_modules(self):
        """router.py deve importar apenas de validators, s3_service, database e models (sem circular)."""
        router_path = APP_DIR / "router.py"
        internal_imports = _get_internal_imports(router_path)

        disallowed = internal_imports - self.ALLOWED_IMPORTS
        assert disallowed == set(), (
            f"router.py importa de módulos não permitidos: {sorted(disallowed)}. "
            f"Apenas {sorted(self.ALLOWED_IMPORTS)} são permitidos."
        )

    def test_router_does_not_import_config_directly(self):
        """router.py não deve importar diretamente de app.config (usa via outros módulos)."""
        router_path = APP_DIR / "router.py"
        internal_imports = _get_internal_imports(router_path)

        assert "app.config" not in internal_imports, (
            "router.py não deve importar diretamente de app.config. "
            "Configuração deve ser acessada via módulos de serviço."
        )

    def test_no_circular_dependency_router_to_router(self):
        """Nenhum módulo importado pelo router deve importar de volta do router."""
        router_path = APP_DIR / "router.py"
        router_imports = _get_internal_imports(router_path)

        for module_name in router_imports:
            # Converte app.validators -> validators.py
            filename = module_name.replace("app.", "") + ".py"
            module_path = APP_DIR / filename

            if module_path.exists():
                module_imports = _get_internal_imports(module_path)
                assert "app.router" not in module_imports, (
                    f"Dependência circular detectada: router.py importa {module_name}, "
                    f"que por sua vez importa app.router"
                )
