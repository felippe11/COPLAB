from flask import render_template, redirect, url_for, flash, request, jsonify, send_from_directory, make_response
from extensions import db
from utils import allowed_file
from models import Integrante, Pagamento, Administrador, Premiacao, CategoriaEnum, StatusPagamentoEnum, VALORES_CATEGORIA, Gasto, SemestreEnum, RankingSemestral, PremiacaoSemestral, ConfiguracaoSistema
from datetime import datetime
import os
import uuid
import csv
import io
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import calendar
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Usar o backend não interativo

def register_routes(app):

    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}

    # Função auxiliar para gerar nome único para arquivo
    def gerar_nome_arquivo(filename):
        ext = filename.rsplit('.', 1)[1].lower()
        novo_nome = f"{uuid.uuid4().hex}.{ext}"
        return novo_nome

    # Função para obter as configurações de pontuação do sistema
    def obter_configuracoes_pontuacao():
        # Buscar configuração no banco de dados
        config = ConfiguracaoSistema.query.first()
        
        # Se não existir, criar com valores padrão
        if not config:
            config = ConfiguracaoSistema(
                pontuacao_primeiro_colocado=100,
                reducao_pontos_por_posicao=10
            )
            db.session.add(config)
            db.session.commit()
            
        return config

    # Função para gerar gráfico de saldo vs gastos e entradas
    def gerar_grafico_saldo_gastos(mes=None, semestre=None, ano=None):
        # Criar diretório para gráficos se não existir
        graphs_dir = os.path.join(app.static_folder, 'graphs')
        os.makedirs(graphs_dir, exist_ok=True)
        
        # Se não foi especificado mês ou semestre, usar mês atual
        data_atual = datetime.now()
        if mes is None and semestre is None:
            mes = data_atual.month
        if ano is None:
            ano = data_atual.year
            
        # Preparar arrays para dados
        labels_meses = []
        saldos = []
        gastos_mensais = []
        entradas_mensais = []
        
        # Determinar quais meses buscar
        meses_para_buscar = []
        if mes is not None:
            # Se for filtro mensal, buscar apenas o mês específico
            meses_para_buscar = [(mes, ano)]
            titulo = f"Entradas, Gastos e Saldo - {mes}/{ano}"
            nome_arquivo = f'financeiro_{mes}_{ano}.png'
        else:
            # Se for filtro semestral, buscar todos os meses do semestre
            if semestre == SemestreEnum.PRIMEIRO:
                meses_para_buscar = [(m, ano) for m in range(1, 7)]  # Janeiro a Junho
                titulo = f"Entradas, Gastos e Saldo - 1º Semestre/{ano}"
            else:
                meses_para_buscar = [(m, ano) for m in range(7, 13)]  # Julho a Dezembro
                titulo = f"Entradas, Gastos e Saldo - 2º Semestre/{ano}"
            nome_arquivo = f'financeiro_semestre_{semestre.name}_{ano}.png'
            
        # Coletar dados dos meses determinados
        for mes_ref, ano_ref in meses_para_buscar:
            # Obter pagamentos do mês
            pagamentos_mes = Pagamento.query.filter_by(
                mes_referencia=mes_ref,
                ano_referencia=ano_ref,
                status=StatusPagamentoEnum.VALIDADO
            ).all()
            
            # Obter gastos do mês
            primeiro_dia = datetime(ano_ref, mes_ref, 1)
            if mes_ref == 12:
                ultimo_dia = datetime(ano_ref + 1, 1, 1)
            else:
                ultimo_dia = datetime(ano_ref, mes_ref + 1, 1)
                
            gastos_mes = Gasto.query.filter(
                Gasto.data_gasto >= primeiro_dia,
                Gasto.data_gasto < ultimo_dia
            ).all()
            
            # Calcular valores
            total_arrecadado_mes = sum(pagamento.valor for pagamento in pagamentos_mes)
            total_gastos_mes = sum(gasto.valor for gasto in gastos_mes)
            saldo_liquido_mes = total_arrecadado_mes - total_gastos_mes
            
            # Adicionar aos arrays apenas se houver movimentação neste mês
            if total_arrecadado_mes > 0 or total_gastos_mes > 0 or saldo_liquido_mes != 0:
                labels_meses.append(f"{mes_ref}/{ano_ref}")
                gastos_mensais.append(total_gastos_mes)
                entradas_mensais.append(total_arrecadado_mes)
                saldos.append(saldo_liquido_mes)
        
        # Se não houver dados para mostrar, criar gráfico com mensagem informativa
        if not labels_meses:
            plt.figure(figsize=(12, 6))
            plt.rcParams.update({'font.size': 12})
            plt.title(titulo, fontsize=18)
            plt.figtext(0.5, 0.5, "Não há movimentações financeiras registradas neste período", 
                     horizontalalignment='center', verticalalignment='center', fontsize=14)
            
            grafico_path = os.path.join(graphs_dir, nome_arquivo)
            plt.savefig(grafico_path, bbox_inches='tight', dpi=120)
            plt.close()
            
            return nome_arquivo
        
        # Criar o gráfico
        plt.figure(figsize=(12, 6))
        
        # Configurar fonte padrão maior para todo o gráfico
        plt.rcParams.update({'font.size': 12})
        
        # Plotar barras para saldo, gastos e entradas
        bar_width = 0.25
        index = range(len(labels_meses))
        
        # Criar as barras com valores sobre elas
        entradas = plt.bar([i - bar_width for i in index], entradas_mensais, bar_width, label='Entrada de Pagamentos', color='green', alpha=0.7)
        gastos = plt.bar([i for i in index], gastos_mensais, bar_width, label='Gastos', color='red', alpha=0.7)
        saldos_bar = plt.bar([i + bar_width for i in index], saldos, bar_width, label='Saldo em Caixa', color='blue', alpha=0.7)
        
        # Adicionar valores sobre ou sob as barras, dependendo se são positivos ou negativos
        def adicionar_valores_barras(barras, valores):
            for barra, valor in zip(barras, valores):
                altura = barra.get_height()
                # Definir a posição vertical com base no sinal do valor
                if valor >= 0:
                    # Valores positivos: posicionados acima da barra
                    y_pos = altura + 5
                    va = 'bottom'
                else:
                    # Valores negativos: posicionados abaixo da barra
                    y_pos = altura - 15  # Deslocar um pouco mais para baixo
                    va = 'top'
                
                plt.text(barra.get_x() + barra.get_width()/2., y_pos,
                        f'R$ {valor:.0f}', ha='center', va=va, fontsize=10, fontweight='bold')
        
        adicionar_valores_barras(entradas, entradas_mensais)
        adicionar_valores_barras(gastos, gastos_mensais)
        adicionar_valores_barras(saldos_bar, saldos)
        
        # Configurar o gráfico com fontes maiores
        plt.xlabel('Mês/Ano', fontsize=14)
        plt.ylabel('Valor (R$)', fontsize=14)
        plt.title(titulo, fontsize=18)
        plt.xticks(index, labels_meses, fontsize=12)
        plt.yticks(fontsize=12)
        plt.legend(fontsize=12)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Ajustar layout
        plt.tight_layout()
        
        # Salvar o gráfico com qualidade maior
        grafico_path = os.path.join(graphs_dir, nome_arquivo)
        plt.savefig(grafico_path, bbox_inches='tight', dpi=120)
        plt.close()
        
        # Retornar o nome do arquivo para uso no template
        return nome_arquivo
        
    # API para obter o gráfico financeiro
    @app.route('/api/grafico_financeiro')
    def api_grafico_financeiro():
        # Obter parâmetros da URL
        mes = request.args.get('mes')
        semestre = request.args.get('semestre')
        ano = request.args.get('ano', datetime.now().year)
        
        # Validar e converter parâmetros
        if ano and ano.isdigit():
            ano = int(ano)
        else:
            ano = datetime.now().year
            
        if mes and mes.isdigit() and 1 <= int(mes) <= 12:
            mes = int(mes)
            semestre = None
            grafico = gerar_grafico_saldo_gastos(mes=mes, ano=ano)
        elif semestre and semestre in ['PRIMEIRO', 'SEGUNDO']:
            mes = None
            semestre = SemestreEnum[semestre]
            grafico = gerar_grafico_saldo_gastos(semestre=semestre, ano=ano)
        else:
            # Default: mês atual
            mes = datetime.now().month
            semestre = None
            grafico = gerar_grafico_saldo_gastos(mes=mes, ano=ano)
            
        return jsonify({
            'grafico': grafico,
            'mes': mes,
            'semestre': semestre.name if semestre else None,
            'ano': ano
        })

    # Rota para o dashboard principal
    @app.route('/')
    def index():
        # Obter saldo total em caixa
        pagamentos_validados = Pagamento.query.filter_by(status=StatusPagamentoEnum.VALIDADO).all()
        total_arrecadado = sum(pagamento.valor for pagamento in pagamentos_validados)
            
        # Obter total de gastos
        gastos = Gasto.query.all()
        total_gastos = sum(gasto.valor for gasto in gastos)
            
        # Calcular saldo líquido
        saldo_total = total_arrecadado - total_gastos
        
        # Obter mês e ano atual para o ranking
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        
        # Obter ranking do mês atual (completo, sem limite)
        ranking = obter_ranking_mensal(mes_atual, ano_atual, limite=None)
        
        # Determinar semestre atual
        semestre_atual = SemestreEnum.PRIMEIRO if 1 <= mes_atual <= 6 else SemestreEnum.SEGUNDO
        
        # Obter ranking semestral atual (completo, sem limite)
        ranking_semestral = obter_ranking_semestral(semestre_atual, ano_atual, limite=None)
        
        # Obter configurações de pontuação
        config_pontuacao = obter_configuracoes_pontuacao()
        
        # Gerar gráfico de saldo vs gastos para o mês atual
        grafico_nome = gerar_grafico_saldo_gastos(mes=mes_atual, ano=ano_atual)
        
        # Gerar gráfico de pontuação dos integrantes para o mês atual
        grafico_pontuacao = gerar_grafico_pontuacao(mes=mes_atual, ano=ano_atual)
        
        return render_template('index.html', 
                            saldo_total=saldo_total, 
                            total_arrecadado=total_arrecadado,
                            total_gastos=total_gastos,
                            ranking=ranking, 
                            ranking_semestral=ranking_semestral,
                            mes_atual=mes_atual, 
                            ano_atual=ano_atual,
                            valores_categoria=VALORES_CATEGORIA,
                            categorias=CategoriaEnum,
                            grafico_nome=grafico_nome,
                            grafico_pontuacao=grafico_pontuacao,
                            semestre_atual=semestre_atual,
                            config_pontuacao=config_pontuacao)

    # Função para obter ranking mensal
    def obter_ranking_mensal(mes, ano, limite=3):
        # Buscar pagamentos validados do mês/ano especificado
        pagamentos = Pagamento.query.filter_by(
            mes_referencia=mes,
            ano_referencia=ano,
            status=StatusPagamentoEnum.VALIDADO
        ).all()
        
        # Ordenar pagamentos por data de pagamento (do mais antigo para o mais recente)
        pagamentos.sort(key=lambda p: p.data_pagamento)
        
        # Obter configurações de pontuação
        config = obter_configuracoes_pontuacao()
        pontuacao_primeiro = config.pontuacao_primeiro_colocado
        reducao_pontos = config.reducao_pontos_por_posicao
        pontuacao_minima = config.pontuacao_minima
        
        # Lista para armazenar pagamentos após recálculo
        pagamentos_processados = []
        
        for i, pagamento in enumerate(pagamentos):
            # Calcular pontuação com base na posição (0-indexado)
            pontuacao = max(pontuacao_minima, pontuacao_primeiro - (i * reducao_pontos))
            
            # Atualizar a pontuação no objeto pagamento
            pagamento.pontos = pontuacao
            
            # Adicionar à lista de processados
            pagamentos_processados.append(pagamento)
            
        # Criar lista de integrantes com suas posições
        ranking = []
        for i, pagamento in enumerate(pagamentos_processados[:limite] if limite else pagamentos_processados):
            ranking.append({
                'posicao': i + 1,
                'integrante': pagamento.integrante,
                'data_pagamento': pagamento.data_pagamento,
                'pontos': pagamento.pontos
            })
        
        # Atualizar pontuações no banco de dados
        db.session.commit()
        
        return ranking
        
    # Função para obter ranking semestral
    def obter_ranking_semestral(semestre, ano, limite=None):
        # Determinar quais meses estão no semestre
        if semestre == SemestreEnum.PRIMEIRO:
            meses = range(1, 7)  # Janeiro a Junho
        else:
            meses = range(7, 13)  # Julho a Dezembro
        
        # Obter todos os integrantes ativos
        integrantes = Integrante.query.filter_by(ativo=True).all()
        
        # Obter configurações de pontuação
        config = obter_configuracoes_pontuacao()
        pontuacao_primeiro = config.pontuacao_primeiro_colocado
        reducao_pontos = config.reducao_pontos_por_posicao
        pontuacao_minima = config.pontuacao_minima
        
        # Dicionário para armazenar a pontuação acumulada por integrante
        pontuacoes = {}
        
        # Para cada mês no semestre, buscar os pagamentos e acumular pontos
        for mes in meses:
            # Buscar pagamentos validados do mês
            pagamentos = Pagamento.query.filter_by(
                mes_referencia=mes,
                ano_referencia=ano,
                status=StatusPagamentoEnum.VALIDADO
            ).order_by(Pagamento.data_pagamento).all()
            
            # Recalcular pontuação para este mês baseada na ordem
            for i, pagamento in enumerate(pagamentos):
                # Calcular pontuação (primeiro colocado recebe pontuação máxima, depois vai diminuindo)
                pontuacao = max(pontuacao_minima, pontuacao_primeiro - (i * reducao_pontos))
                
                # Atualizar pontuação no objeto pagamento
                pagamento.pontos = pontuacao
                
                # Acumular pontos por integrante
                integrante_id = pagamento.integrante_id
                if integrante_id in pontuacoes:
                    pontuacoes[integrante_id] += pontuacao
                else:
                    pontuacoes[integrante_id] = pontuacao
        
        # Salvar alterações nos pagamentos
        db.session.commit()
        
        # Atualizar a tabela de ranking semestral com as pontuações calculadas
        for integrante_id, pontos in pontuacoes.items():
            # Buscar ou criar registro
            ranking = RankingSemestral.query.filter_by(
                integrante_id=integrante_id,
                semestre=semestre,
                ano=ano
            ).first()
            
            if not ranking:
                # Criar novo registro
                ranking = RankingSemestral(
                    integrante_id=integrante_id,
                    semestre=semestre,
                    ano=ano,
                    pontos=pontos
                )
                db.session.add(ranking)
            else:
                # Atualizar pontuação
                ranking.pontos = pontos
        
        # Salvar alterações
        db.session.commit()
        
        # Buscar todos os rankings semestrais já atualizados
        rankings = RankingSemestral.query.filter_by(
            semestre=semestre,
            ano=ano
        ).order_by(RankingSemestral.pontos.desc()).all()
        
        # Criar lista de integrantes com suas posições
        ranking_semestral = []
        for i, ranking in enumerate(rankings[:limite] if limite else rankings):
            ranking_semestral.append({
                'posicao': i + 1,
                'integrante': ranking.integrante,
                'pontos': ranking.pontos
            })
            
        return ranking_semestral
        
    # Função para atualizar o ranking semestral
    def atualizar_ranking_semestral(integrante_id, mes, ano, pontos=None, recalculo=False):
        # Determinar o semestre com base no mês
        if 1 <= mes <= 6:
            semestre = SemestreEnum.PRIMEIRO
        else:
            semestre = SemestreEnum.SEGUNDO
            
        # Como agora calculamos a pontuação semestral somando os pontos de todos os meses,
        # vamos simplesmente recalcular o ranking semestral completo
        obter_ranking_semestral(semestre, ano)
        
        return True

    # Função para recalcular pontuações de todos os pagamentos
    def recalcular_pontuacoes():
        # Buscar todos os meses e anos distintos onde existem pagamentos validados
        meses_anos = db.session.query(
            Pagamento.mes_referencia, 
            Pagamento.ano_referencia
        ).filter_by(
            status=StatusPagamentoEnum.VALIDADO
        ).distinct().all()
        
        # Obter configurações de pontuação
        config = obter_configuracoes_pontuacao()
        pontuacao_primeiro = config.pontuacao_primeiro_colocado
        reducao_pontos = config.reducao_pontos_por_posicao
        
        # Pontuação mínima é 10% da pontuação do primeiro colocado
        pontuacao_minima = max(10, int(pontuacao_primeiro * 0.1))
        
        # Para cada mês/ano, recalcular as pontuações com base na ordem de pagamento
        for mes, ano in meses_anos:
            # Obter pagamentos validados do mês/ano
            pagamentos = Pagamento.query.filter_by(
                mes_referencia=mes,
                ano_referencia=ano,
                status=StatusPagamentoEnum.VALIDADO
            ).order_by(Pagamento.data_pagamento).all()
            
            # Recalcular pontuações baseadas na ordem
            for i, pagamento in enumerate(pagamentos):
                # Calcular pontuação (primeiro recebe pontuação máxima, depois vai diminuindo)
                pontuacao = max(pontuacao_minima, pontuacao_primeiro - (i * reducao_pontos))
                
                # Atualizar pontuação
                pagamento.pontos = pontuacao
        
        # Salvar alterações nos pagamentos
        db.session.commit()
        
        # Recalcular rankings semestrais para todos os semestres que têm pagamentos
        semestres_anos = set()
        for mes, ano in meses_anos:
            if 1 <= mes <= 6:
                semestres_anos.add((SemestreEnum.PRIMEIRO, ano))
            else:
                semestres_anos.add((SemestreEnum.SEGUNDO, ano))
        
        # Atualizar cada ranking semestral
        for semestre, ano in semestres_anos:
            obter_ranking_semestral(semestre, ano)
        
        return True

    # Rota para busca de integrantes
    @app.route('/buscar_integrante')
    def buscar_integrante():
        return render_template('buscar_integrante.html')

    # API para busca dinâmica de integrantes
    @app.route('/api/integrantes')
    def api_integrantes():
        termo_busca = request.args.get('termo', '')
    
        # Search active members matching the search term
        integrantes = Integrante.query.filter(
            Integrante.nome.ilike(f'%{termo_busca}%'),
            Integrante.ativo == True
        ).all()
    
        # Format result
        resultado = [{
            'id': integrante.id,
            'nome': integrante.nome,
            'categoria': integrante.categoria.value,
            'valor_mensal': integrante.valor_mensal
        } for integrante in integrantes]
    
        return jsonify(resultado)
        
    # API para obter o ranking mensal
    @app.route('/api/ranking_mensal')
    def api_ranking_mensal():
        # Obter parâmetros
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)
        
        # Validar parâmetros
        if not mes or not ano:
            return jsonify({'error': 'Parâmetros inválidos'}), 400
            
        # Obter ranking
        ranking_lista = obter_ranking_mensal(mes, ano, limite=None)
        
        # Formatar resultado para JSON
        resultado = {
            'ranking': [{
                'posicao': item['posicao'],
                'integrante': {
                    'id': item['integrante'].id,
                    'nome': item['integrante'].nome,
                    'categoria': item['integrante'].categoria.value
                },
                'data_pagamento': item['data_pagamento'].isoformat(),
                'pontos': item['pontos']
            } for item in ranking_lista]
        }
        
        return jsonify(resultado)
        
    # API para obter o ranking semestral
    @app.route('/api/ranking_semestral')
    def api_ranking_semestral():
        # Obter parâmetros
        semestre_str = request.args.get('semestre', '')
        ano = request.args.get('ano', type=int)
        
        # Converter string do semestre para enum
        if semestre_str == 'PRIMEIRO':
            semestre = SemestreEnum.PRIMEIRO
        elif semestre_str == 'SEGUNDO':
            semestre = SemestreEnum.SEGUNDO
        else:
            return jsonify({'error': 'Semestre inválido'}), 400
            
        # Validar parâmetros
        if not ano:
            return jsonify({'error': 'Parâmetros inválidos'}), 400
            
        # Obter ranking
        ranking_lista = obter_ranking_semestral(semestre, ano, limite=None)
        
        # Formatar resultado para JSON
        resultado = {
            'ranking': [{
                'posicao': item['posicao'],
                'integrante': {
                    'id': item['integrante'].id,
                    'nome': item['integrante'].nome,
                    'categoria': item['integrante'].categoria.value
                },
                'pontos': item['pontos']
            } for item in ranking_lista]
        }
        
        return jsonify(resultado)
    
    # API para obter o gráfico de pontuação
    @app.route('/api/grafico_pontuacao')
    def api_grafico_pontuacao():
        # Obter parâmetros da URL
        mes = request.args.get('mes')
        semestre = request.args.get('semestre')
        ano = request.args.get('ano', datetime.now().year)
        
        # Validar e converter parâmetros
        if ano and ano.isdigit():
            ano = int(ano)
        else:
            ano = datetime.now().year
            
        if mes and mes.isdigit() and 1 <= int(mes) <= 12:
            mes = int(mes)
            semestre = None
            grafico = gerar_grafico_pontuacao(mes=mes, ano=ano)
        elif semestre and semestre in ['PRIMEIRO', 'SEGUNDO']:
            mes = None
            semestre = SemestreEnum[semestre]
            grafico = gerar_grafico_pontuacao(semestre=semestre, ano=ano)
        else:
            # Default: mês atual
            mes = datetime.now().month
            semestre = None
            grafico = gerar_grafico_pontuacao(mes=mes, ano=ano)
            
        return jsonify({
            'grafico': grafico,
            'mes': mes,
            'semestre': semestre.name if semestre else None,
            'ano': ano
        })

    # Rota para exibir detalhes do integrante e pagamentos pendentes
    @app.route('/integrante/<int:integrante_id>')
    def detalhes_integrante(integrante_id):
        integrante = Integrante.query.get_or_404(integrante_id)
        
        # Obter mês e ano atual
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        
        # Verificar pagamentos pendentes (mês atual e anteriores)
        pagamentos_pendentes = []
        
        # Verificar mês atual
        pagamento_mes_atual = Pagamento.query.filter_by(
            integrante_id=integrante_id,
            mes_referencia=mes_atual,
            ano_referencia=ano_atual
        ).first()
        
        if not pagamento_mes_atual or pagamento_mes_atual.status == StatusPagamentoEnum.PENDENTE:
            pagamentos_pendentes.append({
                'mes': mes_atual,
                'ano': ano_atual,
                'nome_mes': calendar.month_name[mes_atual]
            })
        
        # Verificar meses anteriores (até 12 meses atrás)
        for i in range(1, 12):
            mes_anterior = mes_atual - i
            ano_anterior = ano_atual
            
            if mes_anterior <= 0:
                mes_anterior += 12
                ano_anterior -= 1
            
            pagamento_anterior = Pagamento.query.filter_by(
                integrante_id=integrante_id,
                mes_referencia=mes_anterior,
                ano_referencia=ano_anterior
            ).first()
            
            if not pagamento_anterior or pagamento_anterior.status == StatusPagamentoEnum.PENDENTE:
                pagamentos_pendentes.append({
                    'mes': mes_anterior,
                    'ano': ano_anterior,
                    'nome_mes': calendar.month_name[mes_anterior]
                })
        
        return render_template('detalhes_integrante.html', 
                               integrante=integrante, 
                               pagamentos_pendentes=pagamentos_pendentes)

    # Rota para envio de comprovante de pagamento
    @app.route('/enviar_comprovante/<int:integrante_id>', methods=['GET', 'POST'])
    def enviar_comprovante(integrante_id):
        integrante = Integrante.query.get_or_404(integrante_id)
        
        if request.method == 'POST':
            # Verificar se o mês e ano foram fornecidos
            mes = request.form.get('mes')
            ano = request.form.get('ano')
            
            if not mes or not ano:
                flash('Mês e ano são obrigatórios', 'danger')
                return redirect(url_for('detalhes_integrante', integrante_id=integrante_id))
            
            # Verificar se o arquivo foi enviado
            if 'comprovante' not in request.files:
                flash('Nenhum arquivo enviado', 'danger')
                return redirect(url_for('detalhes_integrante', integrante_id=integrante_id))
            
            arquivo = request.files['comprovante']
            
            if arquivo.filename == '':
                flash('Nenhum arquivo selecionado', 'danger')
                return redirect(url_for('detalhes_integrante', integrante_id=integrante_id))
            
            if arquivo and allowed_file(arquivo.filename):
                # Gerar nome único para o arquivo
                nome_arquivo = gerar_nome_arquivo(arquivo.filename)
                caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                
                # Salvar arquivo
                arquivo.save(caminho_arquivo)
                
                # Verificar se já existe um pagamento para este mês/ano
                pagamento = Pagamento.query.filter_by(
                    integrante_id=integrante_id,
                    mes_referencia=int(mes),
                    ano_referencia=int(ano)
                ).first()
                
                if pagamento:
                    # Atualizar pagamento existente
                    pagamento.status = StatusPagamentoEnum.AGUARDANDO_VALIDACAO
                    pagamento.data_pagamento = datetime.utcnow()
                    pagamento.comprovante_path = nome_arquivo
                else:
                    # Criar novo pagamento
                    pagamento = Pagamento(
                        integrante_id=integrante_id,
                        mes_referencia=int(mes),
                        ano_referencia=int(ano),
                        valor=integrante.valor_mensal,
                        status=StatusPagamentoEnum.AGUARDANDO_VALIDACAO,
                        data_pagamento=datetime.utcnow(),
                        comprovante_path=nome_arquivo
                    )
                    db.session.add(pagamento)
                
                db.session.commit()
                flash('Comprovante enviado com sucesso! Aguardando validação.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Tipo de arquivo não permitido', 'danger')
                return redirect(url_for('detalhes_integrante', integrante_id=integrante_id))
        
        return render_template('enviar_comprovante.html', integrante=integrante)

    # Rota para acessar comprovantes
    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # Rota para login do administrador
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if request.method == 'POST':
            email = request.form.get('email')
            senha = request.form.get('senha')
            
            admin = Administrador.query.filter_by(email=email).first()
            
            if admin and admin.verificar_senha(senha):
                # Aqui seria implementado um sistema de sessão
                # Por simplicidade, vamos usar um cookie
                response = redirect(url_for('admin_dashboard'))
                response.set_cookie('admin_id', str(admin.id), max_age=3600)  # 1 hora
                return response
            else:
                flash('Email ou senha inválidos', 'danger')
        
        return render_template('admin/login.html')

    # Middleware para verificar se o administrador está logado
    def admin_required(view_func):
        def wrapped_view(*args, **kwargs):
            admin_id = request.cookies.get('admin_id')
            if not admin_id:
                return redirect(url_for('admin_login'))
            
            admin = Administrador.query.get(admin_id)
            if not admin:
                return redirect(url_for('admin_login'))
            
            return view_func(*args, **kwargs)
        
        # Preservar o nome da função original para o Flask
        wrapped_view.__name__ = view_func.__name__
        return wrapped_view

    # Rota para o dashboard do administrador
    @app.route('/admin/dashboard')
    @admin_required
    def admin_dashboard():
        # Obter estatísticas gerais
        total_integrantes = Integrante.query.filter_by(ativo=True).count()
        pagamentos_pendentes = Pagamento.query.filter_by(status=StatusPagamentoEnum.AGUARDANDO_VALIDACAO).count()
        
        # Obter total arrecadado
        pagamentos_validados = Pagamento.query.filter_by(status=StatusPagamentoEnum.VALIDADO).all()
        total_arrecadado = sum(pagamento.valor for pagamento in pagamentos_validados)
            
        # Obter total de gastos
        gastos = Gasto.query.all()
        total_gastos = sum(gasto.valor for gasto in gastos)
            
        # Calcular saldo líquido
        saldo_total = total_arrecadado - total_gastos
            
        # Obter mês atual
        mes_atual = datetime.now().month
        mes_atual_nome = calendar.month_name[mes_atual]
            
        # Obter pagamentos aguardando validação
        pagamentos_aguardando = Pagamento.query.filter_by(status=StatusPagamentoEnum.AGUARDANDO_VALIDACAO).all()
            
        # Obter gastos recentes (últimos 5)
        gastos_recentes = Gasto.query.order_by(Gasto.data_gasto.desc()).limit(5).all()
        
        # Obter configurações de pontuação
        config_pontuacao = obter_configuracoes_pontuacao()
        
        return render_template('admin/dashboard.html', 
                               total_integrantes=total_integrantes,
                               pagamentos_pendentes=pagamentos_pendentes,
                                saldo_total=saldo_total,
                                total_arrecadado=total_arrecadado,
                                total_gastos=total_gastos,
                                mes_atual_nome=mes_atual_nome,
                                pagamentos_aguardando=pagamentos_aguardando,
                                gastos_recentes=gastos_recentes,
                                config_pontuacao=config_pontuacao)

    # Rota para recalcular pontuações de todos os pagamentos
    @app.route('/admin/recalcular-pontuacoes', methods=['POST'])
    @admin_required
    def admin_recalcular_pontuacoes():
        try:
            # Executar recálculo de pontuações
            recalcular_pontuacoes()
            flash('Pontuações recalculadas com sucesso! O ranking semestral agora mostra a soma dos pontos de todos os meses.', 'success')
        except Exception as e:
            flash(f'Erro ao recalcular pontuações: {str(e)}', 'danger')
            
        return redirect(url_for('admin_dashboard'))
        
    # Rota para salvar configurações de pontuação
    @app.route('/admin/configurar-pontuacao', methods=['POST'])
    @admin_required
    def admin_configurar_pontuacao():
        admin_id = request.cookies.get('admin_id')
        
        try:
            # Obter valores do formulário
            pontuacao_primeiro = request.form.get('pontuacao_primeiro', 100, type=int)
            reducao_pontos = request.form.get('reducao_pontos', 10, type=int)
            pontuacao_minima = request.form.get('pontuacao_minima', 10, type=int)
            
            # Validar valores
            if pontuacao_primeiro < 10 or pontuacao_primeiro > 1000:
                flash('A pontuação do primeiro colocado deve estar entre 10 e 1000.', 'danger')
                return redirect(url_for('admin_dashboard'))
                
            if reducao_pontos < 1 or reducao_pontos > pontuacao_primeiro:
                flash('A redução de pontos deve estar entre 1 e a pontuação do primeiro colocado.', 'danger')
                return redirect(url_for('admin_dashboard'))
                
            if pontuacao_minima < 1 or pontuacao_minima > pontuacao_primeiro:
                flash('A pontuação mínima deve estar entre 1 e a pontuação do primeiro colocado.', 'danger')
                return redirect(url_for('admin_dashboard'))
            
            # Buscar configuração existente ou criar nova
            config = ConfiguracaoSistema.query.first()
            if not config:
                config = ConfiguracaoSistema()
                db.session.add(config)
            
            # Atualizar configuração
            config.pontuacao_primeiro_colocado = pontuacao_primeiro
            config.reducao_pontos_por_posicao = reducao_pontos
            config.pontuacao_minima = pontuacao_minima
            config.data_atualizacao = datetime.utcnow()
            config.administrador_id = admin_id
            
            db.session.commit()
            
            # Perguntar se deseja recalcular pontuações
            recalcular = request.form.get('recalcular', 'false')
            if recalcular == 'true':
                recalcular_pontuacoes()
                flash('Configurações salvas e pontuações recalculadas com sucesso!', 'success')
            else:
                flash('Configurações de pontuação salvas com sucesso! As novas configurações serão aplicadas a novos pagamentos validados.', 'success')
                
        except Exception as e:
            flash(f'Erro ao salvar configurações: {str(e)}', 'danger')
            
        return redirect(url_for('admin_dashboard'))

    # Rota para gerenciamento de integrantes
    @app.route('/admin/integrantes')
    @admin_required
    def admin_integrantes():
        integrantes = Integrante.query.all()
        return render_template('admin/integrantes.html', 
                                integrantes=integrantes, 
                                valores_categoria=VALORES_CATEGORIA,
                                categorias=CategoriaEnum)

    # Rota para adicionar novo integrante
    @app.route('/admin/integrantes/adicionar', methods=['GET', 'POST'])
    @admin_required
    def admin_adicionar_integrante():
        if request.method == 'POST':
            nome = request.form.get('nome')
            categoria_str = request.form.get('categoria')
            
            if not nome or not categoria_str:
                flash('Nome e categoria são obrigatórios', 'danger')
                return redirect(url_for('admin_adicionar_integrante'))
            
            try:
                categoria = CategoriaEnum[categoria_str.upper()]
                
                # Criar novo integrante
                integrante = Integrante(nome=nome, categoria=categoria)
                db.session.add(integrante)
                db.session.commit()
                
                flash('Integrante adicionado com sucesso!', 'success')
                return redirect(url_for('admin_integrantes'))
            except KeyError:
                flash('Categoria inválida', 'danger')
                return redirect(url_for('admin_adicionar_integrante'))
        
        categorias = [categoria.value for categoria in CategoriaEnum]
        return render_template('admin/adicionar_integrante.html', categorias=categorias)

    # Rota para editar integrante
    @app.route('/admin/integrantes/editar/<int:integrante_id>', methods=['GET', 'POST'])
    @admin_required
    def admin_editar_integrante(integrante_id):
        integrante = Integrante.query.get_or_404(integrante_id)
        
        if request.method == 'POST':
            nome = request.form.get('nome')
            categoria_str = request.form.get('categoria')
            
            if not nome or not categoria_str:
                flash('Nome e categoria são obrigatórios', 'danger')
                return redirect(url_for('admin_editar_integrante', integrante_id=integrante_id))
            
            try:
                categoria = CategoriaEnum[categoria_str.upper()]
                
                # Atualizar integrante
                integrante.nome = nome
                integrante.categoria = categoria
                integrante.valor_mensal = VALORES_CATEGORIA[categoria]

                
                db.session.commit()
                
                flash('Integrante atualizado com sucesso!', 'success')
                return redirect(url_for('admin_integrantes'))
            except KeyError:
                flash('Categoria inválida', 'danger')
                return redirect(url_for('admin_editar_integrante', integrante_id=integrante_id))
        
        categorias = [categoria.value for categoria in CategoriaEnum]
        return render_template('admin/editar_integrante.html', integrante=integrante, categorias=categorias)

    # Rota para ativar integrante
    @app.route('/admin/ativar_integrante/<int:integrante_id>', methods=['POST'])
    @admin_required
    def admin_ativar_integrante(integrante_id):
        integrante = Integrante.query.get_or_404(integrante_id)
        
        # Alterar o status para ativo
        integrante.ativo = True
        
        db.session.commit()
        flash('Integrante ativado com sucesso!', 'success')
        return redirect(url_for('admin_integrantes'))

    # Rota para desativar integrante
    @app.route('/admin/desativar_integrante/<int:integrante_id>', methods=['POST'])
    @admin_required
    def admin_desativar_integrante(integrante_id):
        integrante = Integrante.query.get_or_404(integrante_id)
        
        # Alterar o status para inativo
        integrante.ativo = False
        
        db.session.commit()
        flash('Integrante desativado com sucesso!', 'warning')
        return redirect(url_for('admin_integrantes'))
        
    # Rota para excluir integrante
    @app.route('/admin/excluir_integrante/<int:integrante_id>', methods=['POST'])
    @admin_required
    def admin_excluir_integrante(integrante_id):
        integrante = Integrante.query.get_or_404(integrante_id)
        
        try:
            # Excluir o integrante do banco de dados
            db.session.delete(integrante)
            db.session.commit()
            flash('Integrante excluído com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao excluir integrante: {str(e)}', 'danger')
            
        return redirect(url_for('admin_integrantes'))

    # Rota para validação de pagamentos
    @app.route('/admin/pagamentos/pendentes')
    @admin_required
    def admin_pagamentos_pendentes():
        pagamentos = Pagamento.query.filter_by(status=StatusPagamentoEnum.AGUARDANDO_VALIDACAO).all()
        return render_template('admin/pagamentos_pendentes.html', pagamentos=pagamentos)

    # Rota para validar ou rejeitar pagamento
    @app.route('/admin/pagamentos/validar/<int:pagamento_id>', methods=['POST'])
    @admin_required
    def admin_validar_pagamento(pagamento_id):
        pagamento = Pagamento.query.get_or_404(pagamento_id)
        acao = request.form.get('acao')
        observacao = request.form.get('observacao', '')
        
        if acao == 'validar':
            pagamento.status = StatusPagamentoEnum.VALIDADO
            pagamento.data_validacao = datetime.utcnow()
            pagamento.observacao = observacao
            
            # Salvar para confirmar a validação
            db.session.commit()
            
            # Obter mês e ano do pagamento
            mes = pagamento.mes_referencia
            ano = pagamento.ano_referencia
            
            # Recalcular o ranking mensal para atualizar as pontuações 
            # com base na ordem de pagamento
            ranking = obter_ranking_mensal(mes, ano, limite=None)
            
            # A pontuação já foi atualizada pelo obter_ranking_mensal
            pontos = pagamento.pontos
            
            # Atualizar ranking semestral
            atualizar_ranking_semestral(pagamento.integrante_id, mes, ano, pontos)
            
            # Verificar se já existe premiação para este mês/ano
            premiacao_existente = Premiacao.query.filter_by(
                mes_referencia=mes,
                ano_referencia=ano,
                posicao=1  # Primeiro lugar
            ).first()
            
            if not premiacao_existente:
                # Buscar o primeiro colocado do ranking
                if ranking and len(ranking) > 0:
                    primeiro_colocado = ranking[0]
                    # Criar premiação para o primeiro colocado
                    premiacao = Premiacao(
                        integrante_id=primeiro_colocado['integrante'].id,
                        mes_referencia=mes,
                        ano_referencia=ano,
                        posicao=1
                    )
                    db.session.add(premiacao)
                    db.session.commit()
            
            flash('Pagamento validado com sucesso! As pontuações foram atualizadas com base na ordem de pagamento.', 'success')
        elif acao == 'rejeitar':
            pagamento.status = StatusPagamentoEnum.REJEITADO
            pagamento.observacao = observacao
            db.session.commit()
            flash('Pagamento rejeitado!', 'warning')
        
        return redirect(url_for('admin_dashboard'))

    # Rota para relatórios financeiros
    @app.route('/admin/relatorios')
    @admin_required
    def admin_relatorios():
        # Verificar se é uma solicitação de exportação
        formato = request.args.get('formato', '')
        if formato in ['csv', 'pdf']:
            # Obter parâmetros de filtro
            mes_inicio = request.args.get('mes_inicio', datetime.now().month, type=int)
            ano_inicio = request.args.get('ano_inicio', datetime.now().year, type=int)
            mes_fim = request.args.get('mes_fim', datetime.now().month, type=int)
            ano_fim = request.args.get('ano_fim', datetime.now().year, type=int)
            categoria = request.args.get('categoria', '')
            status = request.args.get('status', '')
            
            # Obter filtros específicos para a tabela de pagamentos
            mes_filtro = request.args.get('mes_filtro', '', type=str)
            ano_filtro = request.args.get('ano_filtro', '', type=str)
            
            # Iniciar consulta base para pagamentos
            query = Pagamento.query
            
            # Aplicar filtros
            if mes_inicio and ano_inicio and mes_fim and ano_fim:
                # Converter datas para comparação
                data_inicio = datetime(ano_inicio, mes_inicio, 1)
                if mes_fim == 12:
                    data_fim = datetime(ano_fim + 1, 1, 1)
                else:
                    data_fim = datetime(ano_fim, mes_fim + 1, 1)
                
                # Filtrar por período
                query = query.filter(
                    ((Pagamento.ano_referencia > ano_inicio) | 
                    ((Pagamento.ano_referencia == ano_inicio) & (Pagamento.mes_referencia >= mes_inicio))) &
                    ((Pagamento.ano_referencia < ano_fim) | 
                    ((Pagamento.ano_referencia == ano_fim) & (Pagamento.mes_referencia <= mes_fim)))
                )
            
            # Aplicar filtros específicos de mês e ano (filtros da tabela)
            if mes_filtro:
                query = query.filter(Pagamento.mes_referencia == int(mes_filtro))
                
            if ano_filtro:
                query = query.filter(Pagamento.ano_referencia == int(ano_filtro))
            
            # Filtrar por categoria
            if categoria:
                try:
                    categoria_enum = CategoriaEnum[categoria]
                    query = query.join(Integrante).filter(Integrante.categoria == categoria_enum)
                except:
                    pass
            
            # Filtrar por status
            if status:
                try:
                    status_enum = StatusPagamentoEnum[status]
                    query = query.filter(Pagamento.status == status_enum)
                except:
                    pass
            
            # Obter todos os pagamentos (sem paginação)
            pagamentos = query.order_by(Pagamento.ano_referencia.desc(), 
                                    Pagamento.mes_referencia.desc()).all()
            
            # Obter gastos (saídas)
            gastos_query = Gasto.query
            
            # Aplicar filtros de mês e ano para gastos
            if mes_filtro or ano_filtro:
                if mes_filtro:
                    mes = int(mes_filtro)
                    # Filtrar gastos pelo mês
                    gastos_query = gastos_query.filter(db.extract('month', Gasto.data_gasto) == mes)
                
                if ano_filtro:
                    ano = int(ano_filtro)
                    # Filtrar gastos pelo ano
                    gastos_query = gastos_query.filter(db.extract('year', Gasto.data_gasto) == ano)
            
            # Obter todos os gastos
            gastos = gastos_query.order_by(Gasto.data_gasto.desc()).all()
            
            # Preparar lista combinada de transações (pagamentos e gastos)
            transacoes = []
            
            # Adicionar pagamentos como entradas (valor positivo)
            for p in pagamentos:
                transacoes.append({
                    'id': p.id,
                    'tipo': 'entrada',
                    'descricao': f'Pagamento de {p.integrante.nome}',
                    'integrante': p.integrante.nome,
                    'categoria': p.integrante.categoria.value,
                    'mes_ano': f'{p.mes_referencia}/{p.ano_referencia}',
                    'valor': p.valor,
                    'status': p.status.value,
                    'data': p.data_pagamento,
                    'comprovante_path': p.comprovante_path,
                    'integrante_id': p.integrante.id,
                    'pagamento_id': p.id,
                    'gasto_id': None
                })
            
            # Adicionar gastos como saídas (valor negativo)
            for g in gastos:
                # Extrair mês e ano da data do gasto
                mes = g.data_gasto.month
                ano = g.data_gasto.year
                
                transacoes.append({
                    'id': g.id,
                    'tipo': 'saida',
                    'descricao': g.descricao,
                    'integrante': g.administrador.nome if g.administrador else 'N/A',
                    'categoria': 'Gasto',
                    'mes_ano': f'{mes}/{ano}',
                    'valor': g.valor,
                    'status': 'Validado',
                    'data': g.data_gasto,
                    'comprovante_path': g.comprovante_path,
                    'integrante_id': None,
                    'pagamento_id': None,
                    'gasto_id': g.id
                })
            
            # Ordenar transações por data (mais recentes primeiro)
            transacoes.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)
            
            # Gerar nome do arquivo com base nos filtros
            nome_arquivo = 'relatorio'
            if mes_filtro and ano_filtro:
                nome_arquivo = f'relatorio_{mes_filtro}_{ano_filtro}'
            elif mes_filtro:
                nome_arquivo = f'relatorio_mes_{mes_filtro}'
            elif ano_filtro:
                nome_arquivo = f'relatorio_ano_{ano_filtro}'
            
            # Exportar para CSV
            if formato == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Escrever cabeçalho
                writer.writerow(['ID', 'Tipo', 'Descrição', 'Responsável', 'Categoria', 'Mês/Ano', 'Valor', 'Status', 'Data'])
                
                # Escrever dados
                for t in transacoes:
                    writer.writerow([
                        t['id'],
                        'Entrada' if t['tipo'] == 'entrada' else 'Saída',
                        t['descricao'],
                        t['integrante'],
                        t['categoria'],
                        t['mes_ano'],
                        t['valor'],
                        t['status'],
                        t['data'].strftime('%d/%m/%Y %H:%M') if t['data'] else '-'
                    ])
                
                # Criar resposta
                output.seek(0)
                response = make_response(output.getvalue())
                response.headers['Content-Disposition'] = f'attachment; filename={nome_arquivo}.csv'
                response.headers['Content-type'] = 'text/csv'
                return response
            
            # Exportar para PDF
            elif formato == 'pdf':
                # Criar buffer para o PDF
                buffer = io.BytesIO()
                
                # Configurar documento PDF
                doc = SimpleDocTemplate(buffer, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []
                
                # Título do relatório
                titulo = 'Relatório de Entradas e Saídas'
                if mes_filtro and ano_filtro:
                    mes_nome = calendar.month_name[int(mes_filtro)]
                    titulo = f'Relatório de Entradas e Saídas - {mes_nome}/{ano_filtro}'
                elif mes_filtro:
                    mes_nome = calendar.month_name[int(mes_filtro)]
                    titulo = f'Relatório de Entradas e Saídas - {mes_nome}'
                elif ano_filtro:
                    titulo = f'Relatório de Entradas e Saídas - {ano_filtro}'
                
                elements.append(Paragraph(titulo, styles['Heading1']))
                elements.append(Spacer(1, 0.25*inch))
                
                # Dados da tabela
                data = [['ID', 'Tipo', 'Descrição', 'Responsável', 'Categoria', 'Mês/Ano', 'Valor', 'Status', 'Data']]
                
                for t in transacoes:
                    data.append([
                        str(t['id']),
                        'Entrada' if t['tipo'] == 'entrada' else 'Saída',
                        t['descricao'],
                        t['integrante'],
                        t['categoria'],
                        t['mes_ano'],
                        f'R$ {t["valor"]:.2f}',
                        t['status'],
                        t['data'].strftime('%d/%m/%Y %H:%M') if t['data'] else '-'
                    ])
                
                # Criar tabela
                table = Table(data)
                
                # Estilo da tabela
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ])
                
                # Adicionar cores para diferenciar entradas e saídas
                for i, row in enumerate(data[1:], 1):
                    if row[1] == 'Entrada':
                        style.add('BACKGROUND', (0, i), (-1, i), colors.lightgreen)
                    else:  # Saída
                        style.add('BACKGROUND', (0, i), (-1, i), colors.lightcoral)
                
                table.setStyle(style)
                elements.append(table)
                
                # Construir PDF
                doc.build(elements)
                
                # Preparar resposta
                buffer.seek(0)
                response = make_response(buffer.getvalue())
                response.headers['Content-Disposition'] = f'attachment; filename={nome_arquivo}.pdf'
                response.headers['Content-type'] = 'application/pdf'
                return response
        else:
            # Obter parâmetros de filtro
            mes_inicio = request.args.get('mes_inicio', datetime.now().month, type=int)
            ano_inicio = request.args.get('ano_inicio', datetime.now().year, type=int)
            mes_fim = request.args.get('mes_fim', datetime.now().month, type=int)
            ano_fim = request.args.get('ano_fim', datetime.now().year, type=int)
            categoria = request.args.get('categoria', '')
            status = request.args.get('status', '')
            
            # Obter filtros específicos para a tabela de pagamentos
            mes_filtro = request.args.get('mes_filtro', '', type=str)
            ano_filtro = request.args.get('ano_filtro', '', type=str)
            
            # Construir objeto de filtros
            filtros = {
                'mes_inicio': mes_inicio,
                'ano_inicio': ano_inicio,
                'mes_fim': mes_fim,
                'ano_fim': ano_fim,
                'categoria': categoria,
                'status': status,
                'mes_filtro': int(mes_filtro) if mes_filtro else None,
                'ano_filtro': int(ano_filtro) if ano_filtro else None
            }
            
            # Configurar paginação
            pagina = request.args.get('pagina', 1, type=int)
            por_pagina = 10
            
            # Iniciar consulta base para pagamentos
            query = Pagamento.query
            
            # Aplicar filtros
            if mes_inicio and ano_inicio and mes_fim and ano_fim:
                # Converter datas para comparação
                data_inicio = datetime(ano_inicio, mes_inicio, 1)
                if mes_fim == 12:
                    data_fim = datetime(ano_fim + 1, 1, 1)
                else:
                    data_fim = datetime(ano_fim, mes_fim + 1, 1)
                
                # Filtrar por período
                query = query.filter(
                    ((Pagamento.ano_referencia > ano_inicio) | 
                    ((Pagamento.ano_referencia == ano_inicio) & (Pagamento.mes_referencia >= mes_inicio))) &
                    ((Pagamento.ano_referencia < ano_fim) | 
                    ((Pagamento.ano_referencia == ano_fim) & (Pagamento.mes_referencia <= mes_fim)))
                )
            
            # Aplicar filtros específicos de mês e ano (filtros da tabela)
            if filtros['mes_filtro']:
                query = query.filter(Pagamento.mes_referencia == filtros['mes_filtro'])
                
            if filtros['ano_filtro']:
                query = query.filter(Pagamento.ano_referencia == filtros['ano_filtro'])
            
            # Filtrar por categoria
            if categoria:
                try:
                    categoria_enum = CategoriaEnum[categoria]
                    query = query.join(Integrante).filter(Integrante.categoria == categoria_enum)
                except:
                    pass
            
            # Filtrar por status
            if status:
                try:
                    status_enum = StatusPagamentoEnum[status]
                    query = query.filter(Pagamento.status == status_enum)
                except:
                    pass
            
            # Obter pagamentos paginados
            pagamentos = query.order_by(Pagamento.ano_referencia.desc(), 
                                    Pagamento.mes_referencia.desc()).paginate(
                page=pagina, per_page=por_pagina, error_out=False)
                
            # Obter gastos (saídas)
            gastos_query = Gasto.query
            
            # Aplicar filtros de mês e ano para gastos
            if filtros['mes_filtro'] or filtros['ano_filtro']:
                if filtros['mes_filtro']:
                    mes = filtros['mes_filtro']
                    # Filtrar gastos pelo mês
                    gastos_query = gastos_query.filter(db.extract('month', Gasto.data_gasto) == mes)
                
                if filtros['ano_filtro']:
                    ano = filtros['ano_filtro']
                    # Filtrar gastos pelo ano
                    gastos_query = gastos_query.filter(db.extract('year', Gasto.data_gasto) == ano)
            
            # Obter gastos paginados
            gastos = gastos_query.order_by(Gasto.data_gasto.desc()).all()
            
            # Calcular resumo financeiro
            total_arrecadado = sum(p.valor for p in query.filter(Pagamento.status == StatusPagamentoEnum.VALIDADO).all())
            total_pendente = sum(p.valor for p in query.filter(Pagamento.status.in_([StatusPagamentoEnum.PENDENTE, StatusPagamentoEnum.AGUARDANDO_VALIDACAO])).all())
            pagamentos_validados = query.filter(Pagamento.status == StatusPagamentoEnum.VALIDADO).count()
            pagamentos_pendentes = query.filter(Pagamento.status.in_([StatusPagamentoEnum.PENDENTE, StatusPagamentoEnum.AGUARDANDO_VALIDACAO])).count()
            
            # Calcular total de gastos
            total_gastos = sum(g.valor for g in gastos)
            
            # Estatísticas por categoria
            estatisticas_categoria = []
            for categoria in CategoriaEnum:
                integrantes = Integrante.query.filter_by(categoria=categoria).count()
                pagamentos_cat = query.join(Integrante).filter(Integrante.categoria == categoria, 
                                                            Pagamento.status == StatusPagamentoEnum.VALIDADO).all()
                total_cat = sum(p.valor for p in pagamentos_cat)
                
                estatisticas_categoria.append({
                    'nome': categoria.value,
                    'integrantes': integrantes,
                    'pagamentos': len(pagamentos_cat),
                    'total': total_cat
                })
            
            # Resumo
            resumo = {
                'total_arrecadado': total_arrecadado,
                'total_pendente': total_pendente,
                'pagamentos_validados': pagamentos_validados,
                'pagamentos_pendentes': pagamentos_pendentes,
                'total_integrantes': Integrante.query.count(),
                'total_pagamentos': query.count(),
                'total_gastos': total_gastos
            }
            
            # Preparar lista combinada de transações (pagamentos e gastos)
            transacoes = []
            
            # Adicionar pagamentos como entradas (valor positivo)
            for p in pagamentos.items:
                transacoes.append({
                    'id': p.id,
                    'tipo': 'entrada',
                    'descricao': f'Pagamento de {p.integrante.nome}',
                    'integrante': p.integrante.nome,
                    'categoria': p.integrante.categoria.value,
                    'mes_ano': f'{p.mes_referencia}/{p.ano_referencia}',
                    'valor': p.valor,
                    'status': p.status.value,
                    'data': p.data_pagamento,
                    'comprovante_path': p.comprovante_path,
                    'integrante_id': p.integrante.id,
                    'pagamento_id': p.id,
                    'gasto_id': None
                })
            
            # Adicionar gastos como saídas (valor negativo)
            for g in gastos:
                # Extrair mês e ano da data do gasto
                mes = g.data_gasto.month
                ano = g.data_gasto.year
                
                transacoes.append({
                    'id': g.id,
                    'tipo': 'saida',
                    'descricao': g.descricao,
                    'integrante': g.administrador.nome if g.administrador else 'N/A',
                    'categoria': 'Gasto',
                    'mes_ano': f'{mes}/{ano}',
                    'valor': g.valor,
                    'status': 'Validado',
                    'data': g.data_gasto,
                    'comprovante_path': g.comprovante_path,
                    'integrante_id': None,
                    'pagamento_id': None,
                    'gasto_id': g.id
                })
            
            # Ordenar transações por data (mais recentes primeiro)
            transacoes.sort(key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)
            
            return render_template('admin/relatorios.html', 
                                filtros=filtros,
                                pagamentos=pagamentos.items,
                                transacoes=transacoes,
                                pagina=pagina,
                                paginas=pagamentos.pages,
                                resumo=resumo,
                                estatisticas_categoria=estatisticas_categoria)

    # Rota para rejeitar pagamento diretamente da página de relatórios
    @app.route('/admin/pagamentos/rejeitar/<int:pagamento_id>', methods=['POST'])
    @admin_required
    def admin_rejeitar_pagamento(pagamento_id):
        pagamento = Pagamento.query.get_or_404(pagamento_id)
        observacao = request.form.get('observacao', '')
        
        # Atualizar status para rejeitado
        pagamento.status = StatusPagamentoEnum.REJEITADO
        pagamento.observacao = observacao
        
        db.session.commit()
        flash('Pagamento rejeitado com sucesso!', 'warning')
        
        # Redirecionar de volta para a página de relatórios
        return redirect(url_for('admin_relatorios'))

    # Rota para logout do administrador
    @app.route('/admin/logout')
    def admin_logout():
        response = redirect(url_for('index'))
        response.delete_cookie('admin_id')
        return response

    @app.route('/ranking/completo')
    def ranking_completo():
        # Obter mês e ano atual
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        
        # Obter parâmetros da URL
        mes_selecionado = request.args.get('mes', mes_atual, type=int)
        ano_selecionado = request.args.get('ano', ano_atual, type=int)
        
        # Get full ranking for selected month
        ranking = obter_ranking_mensal(mes_selecionado, ano_selecionado, limite=None)  # No limit to get all rankings
        
        return render_template('ranking_completo.html',
                            ranking=ranking,
                            mes_atual=mes_atual, 
                            ano_atual=ano_atual,
                            mes_selecionado=mes_selecionado,
                            ano_selecionado=ano_selecionado)

    @app.route('/ranking/semestral')
    def ranking_semestral():
        # Obter ano atual
        ano_atual = datetime.now().year
        mes_atual = datetime.now().month
        
        # Determinar semestre atual
        if 1 <= mes_atual <= 6:
            semestre_atual = SemestreEnum.PRIMEIRO
        else:
            semestre_atual = SemestreEnum.SEGUNDO
        
        # Obter parâmetros da URL
        semestre_selecionado_str = request.args.get('semestre', '')
        if semestre_selecionado_str == 'primeiro':
            semestre_selecionado = SemestreEnum.PRIMEIRO
        elif semestre_selecionado_str == 'segundo':
            semestre_selecionado = SemestreEnum.SEGUNDO
        else:
            semestre_selecionado = semestre_atual
            
        ano_selecionado = request.args.get('ano', ano_atual, type=int)
        
        # Obter ranking semestral
        ranking = obter_ranking_semestral(semestre_selecionado, ano_selecionado)
        
        # Verificar se existe premiação semestral
        premiacao = PremiacaoSemestral.query.filter_by(
            semestre=semestre_selecionado,
            ano=ano_selecionado,
            posicao=1  # Primeiro lugar
        ).first()
        
        return render_template('ranking_semestral.html',
                            ranking=ranking,
                            semestre_atual=semestre_atual,
                            ano_atual=ano_atual,
                            semestre_selecionado=semestre_selecionado,
                            ano_selecionado=ano_selecionado,
                            premiacao_existente=premiacao is not None)

    @app.route('/admin/ranking')
    @admin_required
    def admin_ranking():
        # Obter mês e ano atual
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        
        # Obter parâmetros da URL
        mes_selecionado = request.args.get('mes', mes_atual, type=int)
        ano_selecionado = request.args.get('ano', ano_atual, type=int)
        
        # Obter ranking para o mês/ano selecionado
        ranking = obter_ranking_mensal(mes_selecionado, ano_selecionado, limite=None)
        
        # Obter premiações já registradas
        premiacoes = Premiacao.query.filter_by(
            mes_referencia=mes_selecionado,
            ano_referencia=ano_selecionado
        ).all()
        
        return render_template('admin/ranking.html', 
                            ranking=ranking,
                            premiacoes=premiacoes,
                            mes_selecionado=mes_selecionado, 
                            ano_selecionado=ano_selecionado,
                            mes_atual=mes_atual,
                            ano_atual=ano_atual)

    @app.route('/admin/ranking/semestral')
    @admin_required
    def admin_ranking_semestral():
        # Obter ano atual e mês atual
        ano_atual = datetime.now().year
        mes_atual = datetime.now().month
        
        # Determinar semestre atual
        if 1 <= mes_atual <= 6:
            semestre_atual = SemestreEnum.PRIMEIRO
        else:
            semestre_atual = SemestreEnum.SEGUNDO
        
        # Obter parâmetros da URL
        semestre_selecionado_str = request.args.get('semestre', '')
        if semestre_selecionado_str == 'primeiro':
            semestre_selecionado = SemestreEnum.PRIMEIRO
        elif semestre_selecionado_str == 'segundo':
            semestre_selecionado = SemestreEnum.SEGUNDO
        else:
            semestre_selecionado = semestre_atual
            
        ano_selecionado = request.args.get('ano', ano_atual, type=int)
        
        # Obter ranking semestral
        ranking = obter_ranking_semestral(semestre_selecionado, ano_selecionado)
        
        # Obter premiações semestrais já registradas
        premiacoes = PremiacaoSemestral.query.filter_by(
            semestre=semestre_selecionado,
            ano=ano_selecionado
        ).all()
        
        return render_template('admin/ranking_semestral.html', 
                            ranking=ranking,
                            premiacoes=premiacoes,
                            semestre_atual=semestre_atual,
                            ano_atual=ano_atual,
                            semestre_selecionado=semestre_selecionado,
                            ano_selecionado=ano_selecionado)

    # Rota para visualização de gastos
    @app.route('/admin/gastos')
    @admin_required
    def admin_gastos():
        # Obter o valor do parâmetro 'pagina' da query string (padrão: 1)
        pagina = request.args.get('pagina', 1, type=int)
        
        # Obter gastos paginados
        gastos_paginados = Gasto.query.order_by(Gasto.data_gasto.desc()).paginate(
            page=pagina, per_page=10, error_out=False)
        
        gastos = gastos_paginados.items
        
        # Calcular total de gastos
        total_gastos = db.session.query(db.func.sum(Gasto.valor)).scalar() or 0
        
        return render_template('admin/gastos.html', 
                            gastos=gastos,
                            pagina=pagina,
                            paginas=gastos_paginados.pages,
                            total_gastos=total_gastos)

    # Rota para adicionar novo gasto
    @app.route('/admin/gastos/adicionar', methods=['GET', 'POST'])
    @admin_required
    def admin_adicionar_gasto():
        admin_id = request.cookies.get('admin_id')
        
        if request.method == 'POST':
            descricao = request.form.get('descricao')
            valor = request.form.get('valor')
            
            if not descricao or not valor:
                flash('Descrição e valor são obrigatórios', 'danger')
                return redirect(url_for('admin_adicionar_gasto'))
            
            try:
                valor = float(valor.replace(',', '.'))
                
                # Verificar se foi enviado um comprovante
                comprovante_path = None
                if 'comprovante' in request.files and request.files['comprovante'].filename != '':
                    # Gerar nome único para o arquivo
                    comprovante = request.files['comprovante']
                    nome_arquivo = gerar_nome_arquivo(comprovante.filename)
                    caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                    comprovante.save(caminho_arquivo)
                    comprovante_path = nome_arquivo
                    arquivo = request.files['comprovante']
                    
                    if allowed_file(arquivo.filename):
                        # Gerar nome único para o arquivo
                        nome_arquivo = gerar_nome_arquivo(arquivo.filename)
                        caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                        
                        # Salvar arquivo
                        arquivo.save(caminho_arquivo)
                        comprovante_path = nome_arquivo
                    else:
                        flash('Tipo de arquivo não permitido', 'danger')
                        return redirect(url_for('admin_adicionar_gasto'))
                
                # Criar novo gasto
                gasto = Gasto(
                    descricao=descricao,
                    valor=valor,
                    data_gasto=datetime.utcnow(),
                    comprovante_path=comprovante_path,
                    administrador_id=admin_id
                )
                
                db.session.add(gasto)
                db.session.commit()
                
                flash('Gasto registrado com sucesso!', 'success')
                return redirect(url_for('admin_gastos'))
            except ValueError:
                flash('Valor inválido', 'danger')
                return redirect(url_for('admin_adicionar_gasto'))
        
        return render_template('admin/adicionar_gasto.html')

    # Rota para excluir gasto
    @app.route('/admin/gastos/excluir/<int:gasto_id>', methods=['POST'])
    @admin_required
    def admin_excluir_gasto(gasto_id):
        gasto = Gasto.query.get_or_404(gasto_id)
        
        # Se houver comprovante, excluir o arquivo
        if gasto.comprovante_path:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], gasto.comprovante_path))
            except:
                # Arquivo já pode ter sido excluído ou movido
                pass
        
        db.session.delete(gasto)
        db.session.commit()
        
        flash('Gasto excluído com sucesso!', 'success')
        return redirect(url_for('admin_gastos'))

    # Função para gerar gráfico de pontuação dos integrantes
    def gerar_grafico_pontuacao(mes=None, semestre=None, ano=None):
        # Criar diretório para gráficos se não existir
        graphs_dir = os.path.join(app.static_folder, 'graphs')
        os.makedirs(graphs_dir, exist_ok=True)
        
        # Se não foi especificado mês ou semestre, usar mês atual
        data_atual = datetime.now()
        if mes is None and semestre is None:
            mes = data_atual.month
        if ano is None:
            ano = data_atual.year
            
        # Obter configurações de pontuação
        config = obter_configuracoes_pontuacao()
        pontuacao_primeiro = config.pontuacao_primeiro_colocado
        reducao_pontos = config.reducao_pontos_por_posicao
            
        # Nome do arquivo e título do gráfico dependem do filtro
        if mes is not None:
            # Filtro por mês - forçar recálculo das pontuações
            # Obter ranking com pontuações baseadas na ordem
            rankings = obter_ranking_mensal(mes, ano, limite=None)
            periodo = f"{mes}/{ano}"
            titulo = f"Pontuação por Ordem de Pagamento - {periodo}"
            
            # Texto explicativo
            subtitulo = f"Primeiro a pagar = {pontuacao_primeiro} pontos, com redução de {reducao_pontos} pontos por posição"
            
            # Limites do eixo Y para gráfico mensal - agora dinâmico
            ylim_min = 0
            # Calcular o máximo com base nos dados reais
            if rankings:
                max_pontos = max([r['pontos'] for r in rankings]) if rankings else pontuacao_primeiro
                ylim_max = max_pontos * 1.1  # 10% a mais que o valor máximo para melhor visualização
            else:
                ylim_max = pontuacao_primeiro + 10  # Valor padrão se não houver dados
            
            arquivo = f'pontuacao_mensal_{mes}_{ano}.png'
        else:
            # Filtro por semestre - forçar recálculo das pontuações
            rankings = obter_ranking_semestral(semestre, ano, limite=None)
            periodo = f"{semestre.value}/{ano}"
            titulo = f"Pontuação Acumulada - {periodo}"
            subtitulo = f"Soma dos pontos de todos os meses do semestre (Primeiro = {pontuacao_primeiro}, redução = {reducao_pontos})"
            
            # Para o semestral, os limites dependem dos dados
            ylim_min = 0
            # Calculamos o máximo com base nos dados
            if rankings:
                max_pontos = max([r['pontos'] for r in rankings]) if rankings else pontuacao_primeiro
                ylim_max = max_pontos * 1.1  # 10% a mais que o valor máximo
            else:
                ylim_max = pontuacao_primeiro * 6  # Valor padrão se não houver dados
            
            arquivo = f'pontuacao_semestral_{semestre.name}_{ano}.png'
        
        # Limitar para os 15 primeiros para melhor visualização
        rankings = rankings[:15] if len(rankings) > 15 else rankings
        
        if not rankings:
            # Se não houver dados, criar um gráfico vazio
            plt.figure(figsize=(10, 6))
            plt.title(f"{titulo}", fontsize=18)
            plt.figtext(0.5, 0.5, "Não há pontuações registradas para este período", 
                     horizontalalignment='center', verticalalignment='center', fontsize=14)
            plt.figtext(0.5, 0.45, subtitulo, 
                     horizontalalignment='center', verticalalignment='center', fontsize=12, 
                     style='italic', color='gray')
            
            grafico_path = os.path.join(graphs_dir, arquivo)
            plt.savefig(grafico_path, bbox_inches='tight', dpi=100)
            plt.close()
            
            return arquivo
        
        # Extrair dados para o gráfico
        nomes = [r['integrante'].nome for r in rankings]
        pontos = [r['pontos'] for r in rankings]
        
        # Cores para destacar os 3 primeiros colocados
        cores = ['gold', 'silver', '#cd7f32']  # Ouro, Prata, Bronze
        cores.extend(['#1f77b4'] * (len(rankings) - 3))  # Azul para os demais
        
        # Criar o gráfico
        plt.figure(figsize=(12, 7))
        
        # Configurar fonte padrão maior para todo o gráfico
        plt.rcParams.update({'font.size': 12})
        
        # Adicionar linhas de referência específicas por tipo de gráfico
        if mes is not None:
            # Para gráfico mensal, linhas a cada 'reducao_pontos'
            for p in range(0, int(ylim_max) + reducao_pontos, reducao_pontos):
                plt.axhline(y=p, color='gray', linestyle='--', alpha=0.3)
        else:
            # Para gráfico semestral, linhas a cada 'pontuacao_primeiro'
            step = pontuacao_primeiro
            for p in range(0, int(ylim_max) + step, step):
                plt.axhline(y=p, color='gray', linestyle='--', alpha=0.3)
        
        # Plotar as barras
        barras = plt.bar(nomes, pontos, color=cores, width=0.6)
        
        # Adicionar valores sobre as barras com fonte maior
        for barra in barras:
            altura = barra.get_height()
            plt.text(barra.get_x() + barra.get_width()/2., altura + (ylim_max * 0.01),
                    f'{int(altura)}', ha='center', va='bottom', fontweight='bold', fontsize=14)
        
        # Configurar o gráfico com fontes maiores
        plt.xlabel('Integrantes', fontsize=14)
        plt.ylabel('Pontos', fontsize=14)
        plt.title(titulo, fontsize=18, pad=20)
        
        # Adicionar subtítulo
        plt.figtext(0.5, 0.01, subtitulo, ha='center', fontsize=12, style='italic')
        
        # Definir limites do eixo Y
        plt.ylim(ylim_min, ylim_max)
        
        # Aumentar tamanho das fontes dos ticks
        plt.xticks(rotation=45, ha='right', fontsize=12)
        plt.yticks(fontsize=12)
        
        plt.tight_layout()
        plt.grid(axis='y', linestyle='--', alpha=0.3)
        
        # Salvar o gráfico com qualidade maior
        grafico_path = os.path.join(graphs_dir, arquivo)
        plt.savefig(grafico_path, bbox_inches='tight', dpi=120)
        plt.close()
        
        # Retornar o nome do arquivo para uso no template
        return arquivo

    # API para gerar relatório mensal
    @app.route('/api/relatorio/mensal')
    @admin_required
    def api_relatorio_mensal():
        mes = request.args.get('mes', datetime.now().month, type=int)
        ano = request.args.get('ano', datetime.now().year, type=int)
        
        # Buscar todos os pagamentos do mês/ano
        pagamentos = Pagamento.query.filter_by(
            mes_referencia=mes,
            ano_referencia=ano
        ).all()
        
        # Calcular estatísticas
        total_arrecadado = sum(p.valor for p in pagamentos if p.status == StatusPagamentoEnum.VALIDADO)
        total_pendente = sum(p.valor for p in pagamentos if p.status == StatusPagamentoEnum.PENDENTE)
        total_aguardando = sum(p.valor for p in pagamentos if p.status == StatusPagamentoEnum.AGUARDANDO_VALIDACAO)
        
        # Detalhes por integrante
        detalhes_integrantes = []
        for pagamento in pagamentos:
            detalhes_integrantes.append({
                'nome': pagamento.integrante.nome,
                'categoria': pagamento.integrante.categoria.value,
                'valor': pagamento.valor,
                'status': pagamento.status.value,
                'data_pagamento': pagamento.data_pagamento.strftime('%d/%m/%Y %H:%M') if pagamento.data_pagamento else None
            })
        
        # Premiação do mês
        premiacao = Premiacao.query.filter_by(
            mes_referencia=mes,
            ano_referencia=ano,
            posicao=1
        ).first()
        
        vencedor = None
        if premiacao:
            vencedor = premiacao.integrante.nome
        
        relatorio = {
            'mes': mes,
            'ano': ano,
            'nome_mes': calendar.month_name[mes],
            'total_arrecadado': total_arrecadado,
            'total_pendente': total_pendente,
            'total_aguardando': total_aguardando,
            'detalhes_integrantes': detalhes_integrantes,
            'vencedor_premiacao': vencedor
        }
        
        return jsonify(relatorio)
