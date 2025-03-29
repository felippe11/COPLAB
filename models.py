from extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import enum

# Enum for member categories
class CategoriaEnum(enum.Enum):
    GRADUANDO = "Graduando"
    MESTRANDO = "Mestrando"
    DOUTORANDO = "Doutorando"
    POS_DOUTORANDO = "Pós-Doutorando"
    PROFESSOR = "Professor"

# Enum para semestre
class SemestreEnum(enum.Enum):
    PRIMEIRO = "Primeiro Semestre"
    SEGUNDO = "Segundo Semestre"

# Dictionary of values per category
VALORES_CATEGORIA = {
    CategoriaEnum.GRADUANDO: 15.00,
    CategoriaEnum.MESTRANDO: 20.00,
    CategoriaEnum.DOUTORANDO: 25.00,
    CategoriaEnum.POS_DOUTORANDO: 30.00,
    CategoriaEnum.PROFESSOR: 35.00
}

# Modelo para Integrante
class Integrante(db.Model):
    __tablename__ = 'integrantes'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.Enum(CategoriaEnum), nullable=False)
    valor_mensal = db.Column(db.Float, nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)
    
    # Relacionamento com pagamentos
    pagamentos = db.relationship('Pagamento', backref='integrante', lazy=True)
    
    def __init__(self, nome, categoria):
        self.nome = nome
        self.categoria = categoria
        self.valor_mensal = VALORES_CATEGORIA[categoria]
    
    def __repr__(self):
        return f'<Integrante {self.nome}> - {self.categoria.value}'

# Enum para status de pagamento
class StatusPagamentoEnum(enum.Enum):
    PENDENTE = "Pendente"
    AGUARDANDO_VALIDACAO = "Aguardando Validação"
    VALIDADO = "Validado"
    REJEITADO = "Rejeitado"

# Modelo para Pagamento
class Pagamento(db.Model):
    __tablename__ = 'pagamentos'
    
    id = db.Column(db.Integer, primary_key=True)
    integrante_id = db.Column(db.Integer, db.ForeignKey('integrantes.id'), nullable=False)
    mes_referencia = db.Column(db.Integer, nullable=False)  # 1-12 para meses do ano
    ano_referencia = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(StatusPagamentoEnum), default=StatusPagamentoEnum.PENDENTE)
    data_pagamento = db.Column(db.DateTime, nullable=True)  # Data em que o pagamento foi realizado
    data_validacao = db.Column(db.DateTime, nullable=True)  # Data em que o pagamento foi validado
    comprovante_path = db.Column(db.String(255), nullable=True)  # Caminho para o arquivo de comprovante
    observacao = db.Column(db.Text, nullable=True)  # Observações sobre o pagamento
    pontos = db.Column(db.Integer, nullable=True)  # Pontos para o ranking semestral
    
    def __repr__(self):
        return f'<Pagamento {self.integrante.nome} - {self.mes_referencia}/{self.ano_referencia} - {self.status.value}>'

# Modelo para Administrador
class Administrador(db.Model):
    __tablename__ = 'administradores'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    senha_hash = db.Column(db.Text)
    
    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
        
    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
    
    def __repr__(self):
        return f'<Administrador {self.nome}>'

# Modelo para Premiação (Ranking mensal)
class Premiacao(db.Model):
    __tablename__ = 'premiacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    integrante_id = db.Column(db.Integer, db.ForeignKey('integrantes.id'), nullable=False)
    mes_referencia = db.Column(db.Integer, nullable=False)  # 1-12 para meses do ano
    ano_referencia = db.Column(db.Integer, nullable=False)
    posicao = db.Column(db.Integer, nullable=False)  # 1, 2, 3 para o pódio
    data_premiacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com integrante
    integrante = db.relationship('Integrante', backref='premiacoes')
    
    def __repr__(self):
        return f'<Premiacao {self.integrante.nome} - {self.posicao}º lugar - {self.mes_referencia}/{self.ano_referencia}>'


# Modelo para Ranking Semestral
class RankingSemestral(db.Model):
    __tablename__ = 'ranking_semestral'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    integrante_id = db.Column(db.Integer, db.ForeignKey('integrantes.id'), nullable=False)
    semestre = db.Column(db.Enum(SemestreEnum), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    pontos = db.Column(db.Integer, nullable=False, default=0)  # Pontos acumulados no semestre
    
    # Relacionamento com integrante
    integrante = db.relationship('Integrante', backref='ranking_semestral')
    
    def __repr__(self):
        return f'<RankingSemestral {self.integrante.nome} - {self.semestre.value}/{self.ano} - {self.pontos} pontos>'

# Modelo para Premiação Semestral
class PremiacaoSemestral(db.Model):
    __tablename__ = 'premiacoes_semestrais'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    integrante_id = db.Column(db.Integer, db.ForeignKey('integrantes.id'), nullable=False)
    semestre = db.Column(db.Enum(SemestreEnum), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    posicao = db.Column(db.Integer, nullable=False)  # 1, 2, 3 para o pódio
    data_premiacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com integrante
    integrante = db.relationship('Integrante', backref='premiacoes_semestrais')
    
    def __repr__(self):
        return f'<PremiacaoSemestral {self.integrante.nome} - {self.posicao}º lugar - {self.semestre.value}/{self.ano}>'

# Modelo para Gastos
class Gasto(db.Model):
    __tablename__ = 'gastos'
    
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(255), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_gasto = db.Column(db.DateTime, default=datetime.utcnow)
    comprovante_path = db.Column(db.String(255), nullable=True)
    administrador_id = db.Column(db.Integer, db.ForeignKey('administradores.id'), nullable=True)
    
    # Relacionamento com administrador
    administrador = db.relationship('Administrador', backref='gastos')
    
    def __repr__(self):
        return f'<Gasto {self.descricao} - R$ {self.valor:.2f} - {self.data_gasto.strftime("%d/%m/%Y")}>'

# Modelo para Configurações do Sistema
class ConfiguracaoSistema(db.Model):
    __tablename__ = 'configuracoes'
    
    id = db.Column(db.Integer, primary_key=True)
    pontuacao_primeiro_colocado = db.Column(db.Integer, nullable=False, default=100)
    reducao_pontos_por_posicao = db.Column(db.Integer, nullable=False, default=10)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)
    administrador_id = db.Column(db.Integer, db.ForeignKey('administradores.id'), nullable=True)
    
    # Relacionamento com administrador
    administrador = db.relationship('Administrador', backref='configuracoes')
    
    def __repr__(self):
        return f'<ConfiguracaoSistema pontuacao_primeiro={self.pontuacao_primeiro_colocado}, reducao={self.reducao_pontos_por_posicao}>'