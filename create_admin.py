from app import app, db
from models import Administrador

# Criar um contexto de aplicação
with app.app_context():
    # Verificar se já existe um administrador
    admin_existente = Administrador.query.filter_by(email='admin@example.com').first()
    
    if not admin_existente:
        # Criar um novo administrador
        novo_admin = Administrador(
            nome='André',
            email='andrefelippe11@hotmail.com'
        )
        
        # Definir a senha
        novo_admin.set_senha('123456')
        
        # Adicionar ao banco de dados
        db.session.add(novo_admin)
        db.session.commit()
        
        print("Administrador criado com sucesso!")
    else:
        print("Um administrador com este email já existe.")