from flask import render_template, redirect, url_for, flash, request, jsonify, send_from_directory
from extensions import db
from utils import allowed_file
from models import Integrante, Pagamento, Administrador, Premiacao, CategoriaEnum, StatusPagamentoEnum, VALORES_CATEGORIA, Gasto
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import calendar
import json

def register_routes(app):

    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}

    # Função auxiliar para gerar nome único para arquivo
    def gerar_nome_arquivo(filename):
        ext = filename.rsplit('.', 1)[1].lower()
        novo_nome = f"{uuid.uuid4().hex}.{ext}"
        return novo_nome

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
        
        # Obter ranking do mês atual (top 3)
        ranking = obter_ranking_mensal(mes_atual, ano_atual, limite=3)
        
        return render_template('index.html', 
                            saldo_total=saldo_total, 
                            total_arrecadado=total_arrecadado,
                            total_gastos=total_gastos,
                            ranking=ranking, 
                            mes_atual=mes_atual, 
                            ano_atual=ano_atual,
                            valores_categoria=VALORES_CATEGORIA,
                            categorias=CategoriaEnum)

    # Função para obter ranking mensal
    def obter_ranking_mensal(mes, ano, limite=3):
        # Buscar pagamentos validados do mês/ano especificado
        pagamentos = Pagamento.query.filter_by(
            mes_referencia=mes,
            ano_referencia=ano,
            status=StatusPagamentoEnum.VALIDADO
        ).order_by(Pagamento.data_pagamento).all()
        
        # Criar lista de integrantes com suas posições
        ranking = []
        for i, pagamento in enumerate(pagamentos[:limite]):
            ranking.append({
                'posicao': i + 1,
                'integrante': pagamento.integrante,
                'data_pagamento': pagamento.data_pagamento
            })
        
        return ranking

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
        
        return render_template('admin/dashboard.html', 
                               total_integrantes=total_integrantes,
                               pagamentos_pendentes=pagamentos_pendentes,
                                saldo_total=saldo_total,
                                total_arrecadado=total_arrecadado,
                                total_gastos=total_gastos,
                                mes_atual_nome=mes_atual_nome,
                                pagamentos_aguardando=pagamentos_aguardando,
                                gastos_recentes=gastos_recentes)

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
            
            # Verificar se é o primeiro pagamento do mês para atualizar o ranking
            mes = pagamento.mes_referencia
            ano = pagamento.ano_referencia
            
            # Verificar se já existe premiação para este mês/ano
            premiacao_existente = Premiacao.query.filter_by(
                mes_referencia=mes,
                ano_referencia=ano,
                posicao=1  # Primeiro lugar
            ).first()
            
            if not premiacao_existente:
                # Criar premiação para o primeiro colocado
                premiacao = Premiacao(
                    integrante_id=pagamento.integrante_id,
                    mes_referencia=mes,
                    ano_referencia=ano,
                    posicao=1
                )
                db.session.add(premiacao)
            
            flash('Pagamento validado com sucesso!', 'success')
        elif acao == 'rejeitar':
            pagamento.status = StatusPagamentoEnum.REJEITADO
            pagamento.observacao = observacao
            flash('Pagamento rejeitado!', 'warning')
        
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    # Rota para relatórios financeiros
    @app.route('/admin/relatorios')
    @admin_required
    def admin_relatorios():
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
            
            # Iniciar consulta base
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
            
            # Calcular resumo financeiro
            total_arrecadado = sum(p.valor for p in query.filter(Pagamento.status == StatusPagamentoEnum.VALIDADO).all())
            total_pendente = sum(p.valor for p in query.filter(Pagamento.status.in_([StatusPagamentoEnum.PENDENTE, StatusPagamentoEnum.AGUARDANDO_VALIDACAO])).all())
            pagamentos_validados = query.filter(Pagamento.status == StatusPagamentoEnum.VALIDADO).count()
            pagamentos_pendentes = query.filter(Pagamento.status.in_([StatusPagamentoEnum.PENDENTE, StatusPagamentoEnum.AGUARDANDO_VALIDACAO])).count()
            
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
                'total_pagamentos': query.count()
            }
            
            return render_template('admin/relatorios.html', 
                                filtros=filtros,
                                pagamentos=pagamentos.items,
                                pagina=pagina,
                                paginas=pagamentos.pages,
                                resumo=resumo,
                                estatisticas_categoria=estatisticas_categoria)

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
        # Get current month and year
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        
        # Get full ranking for current month
        ranking = obter_ranking_mensal(mes_atual, ano_atual, limite=None)  # No limit to get all rankings
        
        return render_template('ranking_completo.html', 
                            ranking=ranking,
                            mes_atual=mes_atual, 
                            ano_atual=ano_atual)

    @app.route('/admin/ranking')
    @admin_required
    def admin_ranking():
        # Obter mês e ano atual
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year
        
        # Obter ranking para o mês/ano atual
        ranking = obter_ranking_mensal(mes_atual, ano_atual, limite=None)
        
        # Obter premiações já registradas
        premiacoes = Premiacao.query.filter_by(
            mes_referencia=mes_atual,
            ano_referencia=ano_atual
        ).all()
        
        return render_template('admin/ranking.html', 
                            ranking=ranking,
                            premiacoes=premiacoes,
                            mes_selecionado=mes_atual, 
                            ano_selecionado=ano_atual)

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
