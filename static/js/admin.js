/**
 * Script para funcionalidades administrativas do Sistema de Gestão de Pagamentos da Copa
 */

document.addEventListener('DOMContentLoaded', function() {
    // Configurar modais de validação e rejeição de pagamentos
    configurePaymentModals();
    
    // Configurar modal de premiação
    configurePremiacaoModal();
    
    // Configurar modais de gerenciamento de integrantes
    configureIntegranteModals();
});

/**
 * Configura os modais de validação e rejeição de pagamentos
 */
function configurePaymentModals() {
    // Modal de validação
    const validarModal = document.getElementById('validarModal');
    if (validarModal) {
        validarModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const pagamentoId = button.getAttribute('data-pagamento-id');
            const form = document.getElementById('form-validar');
            form.action = `/admin/pagamentos/validar/${pagamentoId}`;
        });
    }
    
    // Modal de rejeição - versão única (dashboard)
    const rejeitarModal = document.getElementById('rejeitarModal');
    if (rejeitarModal) {
        rejeitarModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const pagamentoId = button.getAttribute('data-pagamento-id');
            const form = document.getElementById('form-rejeitar');
            form.action = `/admin/pagamentos/rejeitar/${pagamentoId}`;
        });
        
        // Transferir observação para o campo hidden antes do envio
        const formRejeitar = document.getElementById('form-rejeitar');
        if (formRejeitar) {
            formRejeitar.addEventListener('submit', function() {
                const observacao = document.getElementById('observacao').value;
                document.getElementById('observacao-hidden').value = observacao;
            });
        }
    }
    
    // Modais de rejeição dinâmicos (página de relatórios)
    const rejeitarModais = document.querySelectorAll('[id^="rejeitar-modal-"]');
    rejeitarModais.forEach(modal => {
        // Já estão configurados via HTML com action correta
        console.log('Modal de rejeição configurado:', modal.id);
        
        // Prevenir que o modal feche automaticamente ao clicar fora dele
        modal.setAttribute('data-bs-backdrop', 'static');
        modal.setAttribute('data-bs-keyboard', 'false');
        
        // Configurar o formulário de rejeição
        const modalForm = modal.querySelector('form');
        if (modalForm) {
            modalForm.addEventListener('submit', function(event) {
                // Verificar se o formulário está válido antes de enviar
                if (!this.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                    return false;
                }
                
                // Transferir observação para o campo hidden antes do envio
                const modalId = modal.id.split('-').pop();
                const observacaoTextarea = document.getElementById(`observacao-${modalId}`);
                const observacaoHidden = modalForm.querySelector('input[name="observacao"]');
                
                if (observacaoTextarea && observacaoHidden) {
                    observacaoHidden.value = observacaoTextarea.value;
                    console.log(`Observação transferida para o campo hidden: ${observacaoHidden.value}`);
                }
                
                // Se o formulário estiver válido, permitir o envio normal
                console.log('Formulário de rejeição enviado:', modal.id);
                // Não prevenimos o comportamento padrão para permitir que o formulário seja enviado normalmente
            });
        }
    });}



/**
 * Configura o modal de premiação
 */
function configurePremiacaoModal() {
    const premiacaoModal = document.getElementById('premiacaoModal');
    if (premiacaoModal) {
        premiacaoModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const integranteId = button.getAttribute('data-integrante-id');
            const integranteNome = button.getAttribute('data-integrante-nome');
            const posicao = button.getAttribute('data-posicao');
            const mes = button.getAttribute('data-mes');
            const ano = button.getAttribute('data-ano');
            
            // Atualizar texto e formulário
            document.getElementById('nome-integrante-premiacao').textContent = integranteNome;
            document.getElementById('posicao-premiacao').textContent = posicao;
            document.getElementById('posicao-premiacao').className = `ranking-badge ranking-${posicao} me-3`;
            document.getElementById('mes-ano-premiacao').textContent = `${mes}/${ano}`;
            
            // Atualizar campos ocultos
            document.getElementById('integrante-id-hidden').value = integranteId;
            document.getElementById('posicao-hidden').value = posicao;
            document.getElementById('mes-hidden').value = mes;
            document.getElementById('ano-hidden').value = ano;
            
            // Atualizar action do formulário
            const form = document.getElementById('form-premiacao');
            form.action = `/admin/registrar_premiacao`;
        });
    }
}

/**
 * Configura os modais de gerenciamento de integrantes
 */
function configureIntegranteModals() {
    // Configurar modal de edição
    const editarModal = document.getElementById('editarIntegranteModal');
    if (editarModal) {
        editarModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const nome = button.getAttribute('data-nome');
            const categoria = button.getAttribute('data-categoria');
            
            // Atualizar formulário
            document.getElementById('edit-nome').value = nome;
            document.getElementById('edit-categoria').value = categoria;
            
            // Atualizar action do formulário
            const form = document.getElementById('form-editar-integrante');
            form.action = `/admin/editar_integrante/${id}`;
        });
    }
    
    // Configurar modal de desativação
    const desativarModal = document.getElementById('desativarIntegranteModal');
    if (desativarModal) {
        desativarModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const nome = button.getAttribute('data-nome');
            
            // Atualizar texto e formulário
            document.getElementById('nome-desativar').textContent = nome;
            
            // Atualizar action do formulário
            const form = document.getElementById('form-desativar');
            form.action = `/admin/desativar_integrante/${id}`;
        });
    }
    
    // Configurar modal de ativação
    const ativarModal = document.getElementById('ativarIntegranteModal');
    if (ativarModal) {
        ativarModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const nome = button.getAttribute('data-nome');
            
            // Atualizar texto e formulário
            document.getElementById('nome-ativar').textContent = nome;
            
            // Atualizar action do formulário
            const form = document.getElementById('form-ativar');
            form.action = `/admin/ativar_integrante/${id}`;
        });
    }
}

//configuração do modal de exclusão de gastos
function configureGastosModals() {
    // Configurar modal de exclusão de gastos
    const excluirGastoModal = document.getElementById('excluirGastoModal');
    if (excluirGastoModal) {
        excluirGastoModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const descricao = button.getAttribute('data-descricao');
            
            // Atualizar texto e formulário
            document.getElementById('descricao-excluir').textContent = descricao;
            
            // Atualizar action do formulário
            const form = document.getElementById('form-excluir');
            form.action = `/admin/gastos/excluir/${id}`;
        });
    }
}

// Adicionar a chamada à função na função principal
document.addEventListener('DOMContentLoaded', function() {
    // Configurar modais de validação e rejeição de pagamentos
    configurePaymentModals();
    
    // Configurar modal de premiação
    configurePremiacaoModal();
    
    // Configurar modais de gerenciamento de integrantes
    configureIntegranteModals();
    
    // Configurar modais de gerenciamento de gastos
    configureGastosModals();
});