# Sistema de Gestão de Pagamentos da Copa do Laboratório

Aplicação web desenvolvida em Python para gerenciar de forma prática e transparente os pagamentos mensais da copa do laboratório, oferecendo controle financeiro, incentivo à pontualidade através de premiação, e ferramentas intuitivas para confirmação e registro dos pagamentos.

## Funcionalidades Principais

### Dashboard Principal
- Saldo total em caixa (atualização automática)
- Ranking mensal (pódio) de pontualidade nos pagamentos
- Destaque mensal ao primeiro colocado com premiação (caixa de bombons)

### Busca e Confirmação de Pagamentos
- Barra de pesquisa dinâmica para filtrar integrantes
- Modal para visualização de meses pendentes e envio de comprovante

### Painel Administrativo
- Gerenciamento de integrantes (cadastro, edição, remoção)
- Validação de comprovantes de pagamento
- Relatórios financeiros detalhados
- Notificações automatizadas
- Gráficos estatísticos

## Categorias de Pagamento

| Categoria   | Valor de Contribuição |
|-------------|----------------------:|
| Graduando   | R$ 15,00              |
| Mestrando   | R$ 20,00              |
| Doutorando  | R$ 25,00              |
| Pós-Doutorando | R$ 30,00           |
| Professor   | R$ 35,00              |

## Estrutura Técnica

### Backend
- Python (Framework: Flask)
- ORM: SQLAlchemy
- Banco de Dados: PostgreSQL
- Armazenamento dos comprovantes: Sistema de arquivos local

### Frontend
- HTML, CSS e JavaScript
- Framework CSS: Bootstrap
- Responsivo para dispositivos móveis e desktop