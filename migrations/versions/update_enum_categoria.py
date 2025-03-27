"""update_enum_categoria

Revision ID: update_enum_categoria
Revises: c371506f518c
Create Date: 2023-03-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'update_enum_categoria'
down_revision = 'c371506f518c'
branch_labels = None
depends_on = None


def upgrade():
    # Criar um tipo temporário com os novos valores
    op.execute("ALTER TYPE categoriaenum ADD VALUE 'POS_DOUTORANDO' AFTER 'DOUTORANDO'")


def downgrade():
    # Não há uma maneira direta de remover valores de um Enum no PostgreSQL
    # Seria necessário recriar o tipo sem o valor desejado e atualizar todas as tabelas
    pass 