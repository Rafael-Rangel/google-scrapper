from datetime import datetime
from src.main import db

class Estabelecimento(db.Model):
    __tablename__ = 'estabelecimentos'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    telefone = db.Column(db.String(50))
    avaliacao = db.Column(db.Float)
    fonte = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(100), nullable=False)
    regiao = db.Column(db.String(100), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'endereco': self.endereco,
            'telefone': self.telefone,
            'avaliacao': self.avaliacao,
            'fonte': self.fonte,
            'tipo': self.tipo,
            'regiao': self.regiao,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None
        }
    
    @staticmethod
    def from_dict(data, tipo, regiao):
        return Estabelecimento(
            nome=data.get('nome', 'Nome não disponível'),
            endereco=data.get('endereco', 'Endereço não disponível'),
            telefone=data.get('telefone', 'Telefone não disponível'),
            avaliacao=data.get('avaliacao'),
            fonte=data.get('fonte', 'Desconhecida'),
            tipo=tipo,
            regiao=regiao
        )
