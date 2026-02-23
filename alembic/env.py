import sys
from os.path import abspath, dirname, join
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. Point sys.path to your project root so Alembic can find 'app'
sys.path.insert(0, dirname(dirname(abspath(__file__))))

# 2. Import your settings and models
from app.core.config import settings
from app.drivers.database import Base
from app.data_models.sql_models import MediaVault  # Ensure all models are imported

# Alembic config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. Set target_metadata so --autogenerate works
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL  # Use our Pydantic settings URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # 4. Override the sqlalchemy.url from alembic.ini with our secure settings
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()