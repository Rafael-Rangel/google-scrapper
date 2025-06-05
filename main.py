import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # DON'T CHANGE THIS !!!

from flask import Flask, request, jsonify
import requests
import json
from bs4 import BeautifulSoup
import time
import re
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuração do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///estabelecimentos.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configuração do Firecrawl
FIRECRAWL_API_URL = os.getenv('FIRECRAWL_API_URL', 'http://localhost:3002')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY', 'fc-YOUR_API_KEY')

# Importar modelo após a definição do db
from src.models.estabelecimento import Estabelecimento

@app.route('/api/search', methods=['POST'])
def search():
    """
    Endpoint para iniciar uma busca de estabelecimentos
    
    Parâmetros esperados:
    - tipo: Tipo de estabelecimento (ex: farmácia, supermercado)
    - regiao: Região para busca (ex: Campo Grande, Rio de Janeiro)
    - quantidade: Número máximo de resultados
    - fonte: Fonte de dados (google_maps, paginas_amarelas, etc.)
    - modo: Modo de busca (novo, sobrescrever, juntar)
    """
    data = request.json
    tipo = data.get('tipo')
    regiao = data.get('regiao')
    quantidade = data.get('quantidade', 10)
    fonte = data.get('fonte', 'google_maps')
    modo = data.get('modo', 'novo')  # novo, sobrescrever, juntar
    
    if not tipo or not regiao:
        return jsonify({'error': 'Tipo de estabelecimento e região são obrigatórios'}), 400
    
    # Verificar se já existem resultados para esta busca
    resultados_existentes = Estabelecimento.query.filter_by(
        tipo=tipo, 
        regiao=regiao
    ).all()
    
    if resultados_existentes and modo == 'novo':
        # Se existem resultados e o modo é 'novo', perguntar ao usuário o que fazer
        return jsonify({
            'status': 'confirm',
            'message': 'Já existem resultados para esta busca. O que deseja fazer?',
            'options': ['sobrescrever', 'juntar'],
            'existing_count': len(resultados_existentes)
        }), 200
    
    # Se modo é sobrescrever, remover resultados anteriores
    if modo == 'sobrescrever':
        for item in resultados_existentes:
            db.session.delete(item)
        db.session.commit()
    
    # Construir URL de busca baseada na fonte
    search_url = build_search_url(tipo, regiao, fonte)
    
    # Iniciar crawl via Firecrawl
    try:
        response = requests.post(
            f"{FIRECRAWL_API_URL}/v1/crawl",
            json={
                "url": search_url,
                "limit": quantidade,
                "scrapeOptions": {
                    "formats": ["html"]
                }
            },
            headers={
                'Authorization': f'Bearer {FIRECRAWL_API_KEY}',
                'Content-Type': 'application/json'
            }
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'Erro ao iniciar busca: {response.text}'}), 500
        
        job_data = response.json()
        return jsonify({
            'job_id': job_data.get('id'),
            'status': 'pending',
            'check_url': f"/api/search/{job_data.get('id')}",
            'modo': modo,
            'tipo': tipo,
            'regiao': regiao
        })
        
    except Exception as e:
        return jsonify({'error': f'Erro ao conectar com Firecrawl: {str(e)}'}), 500

@app.route('/api/search/<job_id>', methods=['GET'])
def check_search(job_id):
    """
    Endpoint para verificar o status de uma busca em andamento
    """
    try:
        # Obter parâmetros da requisição
        tipo = request.args.get('tipo')
        regiao = request.args.get('regiao')
        modo = request.args.get('modo', 'novo')
        quantidade = int(request.args.get('quantidade', 10))
        
        response = requests.get(
            f"{FIRECRAWL_API_URL}/v1/crawl/{job_id}",
            headers={
                'Authorization': f'Bearer {FIRECRAWL_API_KEY}',
                'Content-Type': 'application/json'
            }
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'Erro ao verificar status: {response.text}'}), 500
        
        job_data = response.json()
        status = job_data.get('status')
        
        if status == 'completed':
            # Processar os resultados
            novos_estabelecimentos = []
            
            for item in job_data.get('data', []):
                html = item.get('html', '')
                source_url = item.get('metadata', {}).get('sourceURL', '')
                
                # Extrair estabelecimentos do HTML
                estabelecimentos_extraidos = extract_establishments(html, source_url)
                novos_estabelecimentos.extend(estabelecimentos_extraidos)
            
            # Se tipo e região foram fornecidos, salvar no banco de dados
            if tipo and regiao:
                # Obter estabelecimentos existentes se modo for 'juntar'
                estabelecimentos_existentes = []
                if modo == 'juntar':
                    estabelecimentos_existentes = Estabelecimento.query.filter_by(
                        tipo=tipo, 
                        regiao=regiao
                    ).all()
                    
                # Criar um conjunto para rastrear estabelecimentos únicos (por nome e endereço)
                estabelecimentos_unicos = {}
                
                # Adicionar estabelecimentos existentes ao conjunto
                for estab in estabelecimentos_existentes:
                    chave = f"{estab.nome}|{estab.endereco}"
                    estabelecimentos_unicos[chave] = estab.to_dict()
                
                # Adicionar novos estabelecimentos, evitando duplicatas
                for estab in novos_estabelecimentos:
                    chave = f"{estab['nome']}|{estab['endereco']}"
                    if chave not in estabelecimentos_unicos:
                        estabelecimentos_unicos[chave] = estab
                        
                        # Salvar no banco de dados
                        novo_estab = Estabelecimento.from_dict(estab, tipo, regiao)
                        db.session.add(novo_estab)
                
                # Commit das alterações
                db.session.commit()
                
                # Preparar resposta com todos os estabelecimentos únicos
                todos_estabelecimentos = list(estabelecimentos_unicos.values())
                
                return jsonify({
                    'status': 'completed',
                    'total': len(todos_estabelecimentos),
                    'novos': len(novos_estabelecimentos),
                    'existentes': len(estabelecimentos_existentes) if modo == 'juntar' else 0,
                    'estabelecimentos': todos_estabelecimentos[:quantidade]
                })
            else:
                # Se não temos tipo e região, apenas retornar os resultados sem salvar
                return jsonify({
                    'status': 'completed',
                    'total': len(novos_estabelecimentos),
                    'estabelecimentos': novos_estabelecimentos[:quantidade]
                })
        else:
            return jsonify({
                'status': status,
                'message': 'Busca em andamento'
            })
            
    except Exception as e:
        return jsonify({'error': f'Erro ao verificar status: {str(e)}'}), 500

@app.route('/api/sources', methods=['GET'])
def get_sources():
    """
    Endpoint para listar fontes de dados disponíveis
    """
    return jsonify({
        'sources': [
            {
                'id': 'google_maps',
                'name': 'Google Maps',
                'description': 'Busca no Google Maps (pode exigir proxy e 2captcha)'
            },
            {
                'id': 'paginas_amarelas',
                'name': 'Páginas Amarelas',
                'description': 'Diretório brasileiro de empresas e serviços'
            },
            {
                'id': 'apontador',
                'name': 'Apontador',
                'description': 'Guia local de estabelecimentos e serviços'
            }
        ]
    })

def build_search_url(tipo, regiao, fonte):
    """
    Constrói a URL de busca baseada na fonte selecionada
    """
    tipo_encoded = tipo.replace(' ', '+')
    regiao_encoded = regiao.replace(' ', '+')
    
    if fonte == 'google_maps':
        return f"https://www.google.com/maps/search/{tipo_encoded}+{regiao_encoded}"
    elif fonte == 'paginas_amarelas':
        return f"https://www.paginasamarelas.com.br/busca/{tipo_encoded}/{regiao_encoded}"
    elif fonte == 'apontador':
        return f"https://www.apontador.com.br/local/busca/{tipo_encoded}/{regiao_encoded}.html"
    else:
        return f"https://www.google.com/maps/search/{tipo_encoded}+{regiao_encoded}"

def extract_establishments(html, source_url):
    """
    Extrai informações de estabelecimentos do HTML
    
    Esta função precisa ser adaptada para cada fonte de dados,
    pois a estrutura HTML varia entre elas.
    """
    estabelecimentos = []
    soup = BeautifulSoup(html, 'html.parser')
    
    if 'google.com/maps' in source_url:
        # Extração para Google Maps
        # Nota: A estrutura do Google Maps é complexa e pode mudar
        # Esta é uma implementação simplificada
        items = soup.select('div[role="article"]')
        
        for item in items:
            try:
                nome_elem = item.select_one('h3 span')
                endereco_elem = item.select_one('div[role="button"][aria-label*="endereço"]')
                telefone_elem = item.select_one('div[role="button"][aria-label*="telefone"]')
                avaliacao_elem = item.select_one('span[aria-label*="estrelas"]')
                
                nome = nome_elem.text if nome_elem else 'Nome não encontrado'
                endereco = endereco_elem.text if endereco_elem else 'Endereço não encontrado'
                telefone = telefone_elem.text if telefone_elem else 'Telefone não encontrado'
                
                avaliacao = None
                if avaliacao_elem:
                    avaliacao_match = re.search(r'(\d+[.,]?\d*)', avaliacao_elem.get('aria-label', ''))
                    if avaliacao_match:
                        avaliacao = float(avaliacao_match.group(1).replace(',', '.'))
                
                estabelecimentos.append({
                    'nome': nome,
                    'endereco': endereco,
                    'telefone': telefone,
                    'avaliacao': avaliacao,
                    'fonte': 'Google Maps'
                })
            except Exception as e:
                print(f"Erro ao extrair estabelecimento: {str(e)}")
                continue
    
    elif 'paginasamarelas.com.br' in source_url:
        # Extração para Páginas Amarelas
        items = soup.select('.card-empresa')
        
        for item in items:
            try:
                nome_elem = item.select_one('.nome-fantasia')
                endereco_elem = item.select_one('.endereco')
                telefone_elem = item.select_one('.telefone')
                
                nome = nome_elem.text.strip() if nome_elem else 'Nome não encontrado'
                endereco = endereco_elem.text.strip() if endereco_elem else 'Endereço não encontrado'
                telefone = telefone_elem.text.strip() if telefone_elem else 'Telefone não encontrado'
                
                estabelecimentos.append({
                    'nome': nome,
                    'endereco': endereco,
                    'telefone': telefone,
                    'avaliacao': None,
                    'fonte': 'Páginas Amarelas'
                })
            except Exception as e:
                print(f"Erro ao extrair estabelecimento: {str(e)}")
                continue
    
    elif 'apontador.com.br' in source_url:
        # Extração para Apontador
        items = soup.select('.company-card')
        
        for item in items:
            try:
                nome_elem = item.select_one('.company-name')
                endereco_elem = item.select_one('.company-address')
                telefone_elem = item.select_one('.company-phone')
                avaliacao_elem = item.select_one('.company-rating')
                
                nome = nome_elem.text.strip() if nome_elem else 'Nome não encontrado'
                endereco = endereco_elem.text.strip() if endereco_elem else 'Endereço não encontrado'
                telefone = telefone_elem.text.strip() if telefone_elem else 'Telefone não encontrado'
                
                avaliacao = None
                if avaliacao_elem:
                    avaliacao_match = re.search(r'(\d+[.,]?\d*)', avaliacao_elem.text)
                    if avaliacao_match:
                        avaliacao = float(avaliacao_match.group(1).replace(',', '.'))
                
                estabelecimentos.append({
                    'nome': nome,
                    'endereco': endereco,
                    'telefone': telefone,
                    'avaliacao': avaliacao,
                    'fonte': 'Apontador'
                })
            except Exception as e:
                print(f"Erro ao extrair estabelecimento: {str(e)}")
                continue
    
    return estabelecimentos

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
