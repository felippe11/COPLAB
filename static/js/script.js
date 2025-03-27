/**
 * Script principal para o Sistema de Gestão de Pagamentos da Copa
 */

// Função para buscar integrantes dinamicamente
function buscarIntegrantes(termo) {
    // Elemento que mostrará os resultados
    const resultadosDiv = document.getElementById('resultados-busca');
    
    // Se o termo de busca estiver vazio, mostrar mensagem padrão
    if (!termo || termo.trim() === '') {
        resultadosDiv.innerHTML = '<p class="text-muted text-center">Digite um nome para buscar...</p>';
        return;
    }
    
    // Mostrar indicador de carregamento
    resultadosDiv.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Carregando...</span></div><p class="mt-2">Buscando integrantes...</p></div>';
    
    // Fazer requisição AJAX para a API
    fetch(`/api/integrantes?termo=${encodeURIComponent(termo)}`)
        .then(response => response.json())
        .then(data => {
            // Se não houver resultados
            if (data.length === 0) {
                resultadosDiv.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>Nenhum integrante encontrado com este nome.</div>';
                return;
            }
            
            // Construir lista de resultados
            let html = '<div class="list-group">';
            
            data.forEach(integrante => {
                html += `
                <a href="/integrante/${integrante.id}" class="list-group-item list-group-item-action">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <div>
                            <h5 class="mb-1">${integrante.nome}</h5>
                            <p class="mb-1 text-muted">${integrante.categoria}</p>
                        </div>
                        <div class="text-end">
                            <span class="badge bg-primary rounded-pill">R$ ${integrante.valor_mensal.toFixed(2)}</span>
                            <br>
                            <small class="text-muted">Clique para detalhes</small>
                        </div>
                    </div>
                </a>`;
            });
            
            html += '</div>';
            resultadosDiv.innerHTML = html;
        })
        .catch(error => {
            console.error('Erro ao buscar integrantes:', error);
            resultadosDiv.innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>Erro ao buscar integrantes. Tente novamente.</div>';
        });
}

// Configurar busca dinâmica quando o documento estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    const campoBusca = document.getElementById('termo-busca');
    
    // Se o campo de busca existir na página atual
    if (campoBusca) {
        // Adicionar evento de input para busca em tempo real
        campoBusca.addEventListener('input', function() {
            const termo = this.value;
            buscarIntegrantes(termo);
        });
        
        // Focar no campo de busca automaticamente
        campoBusca.focus();
    }
    
    // Configurar modais de confirmação se existirem
    const modais = document.querySelectorAll('.modal');
    if (modais.length > 0) {
        modais.forEach(modal => {
            modal.addEventListener('show.bs.modal', function(event) {
                // Obter botão que acionou o modal
                const button = event.relatedTarget;
                if (button) {
                    // Obter informações do botão via atributos data-*
                    const id = button.getAttribute('data-id');
                    const action = button.getAttribute('data-action');
                    const target = button.getAttribute('data-target');
                    
                    // Se houver um formulário no modal, atualizar sua action
                    if (id && action) {
                        const form = this.querySelector('form');
                        if (form) {
                            form.action = action.replace('ID', id);
                        }
                    }
                    
                    // Se houver um elemento alvo para atualizar com o ID
                    if (id && target) {
                        const targetElement = this.querySelector(target);
                        if (targetElement) {
                            targetElement.value = id;
                        }
                    }
                }
            });
        });
    }
});