# Fisher — Controle financeiro pessoal

Aplicação web para registrar receitas e despesas, acompanhar o orçamento mensal e organizar metas financeiras. A interface e a API são servidas pelo FastAPI; os dados ficam em um banco SQLite local.

## Recursos

- Cadastro, edição, filtros e exclusão de transações.
- Categorias para receitas e despesas, com descrição, data e valor.
- Resumo mensal com receitas, despesas e saldo.
- Gráfico de evolução dos últimos seis meses e categorias com maiores despesas.
- Criação de metas e atualização do progresso.
- Validação de entradas e armazenamento de valores em centavos para evitar erros de arredondamento.
- Migração automática da tabela de transações criada nas etapas iniciais do projeto.
- Interface responsiva em português, sem dependências de frontend/CDN.
- Documentação interativa da API disponível em `/docs`.

## Executar localmente

Requer Python 3.10 ou superior.

```powershell
cd C:\Users\mathe\Documents\SYSTEM2919\main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Abra <http://127.0.0.1:8000> para usar o sistema ou <http://127.0.0.1:8000/docs> para explorar a API.

O SQLite cria `financas.db` ao iniciar a aplicação. Faça cópias desse arquivo se quiser preservar ou transportar seus dados. O banco contém dados pessoais: não o publique no repositório.

## Rotas principais

| Método | Rota | Uso |
| --- | --- | --- |
| `GET` | `/transacoes/lista` | Lista transações; aceita `mes`, `tipo` e `categoria` |
| `POST` | `/transacoes/nova` | Cadastra uma transação |
| `PUT` | `/transacoes/{id}` | Edita uma transação |
| `DELETE` | `/transacoes/{id}` | Exclui uma transação |
| `GET` | `/api/dashboard?mes=AAAA-MM` | Resumo, evolução e maiores despesas |
| `GET` | `/api/categorias` | Categorias permitidas |
| `GET` / `POST` | `/api/metas` | Lista ou cria metas |
| `PUT` | `/api/metas/{id}/progresso` | Atualiza o valor guardado em uma meta |
| `DELETE` | `/api/metas/{id}` | Exclui uma meta |

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes usam um banco temporário, verificam operações e resumos, e confirmam que a migração preserva registros antigos.

## Limites atuais

Este projeto é um protótipo local para portfólio, não um serviço bancário. Ele não possui autenticação multiusuário, sincronização em nuvem, integração com bancos ou cópias de segurança automáticas. Não o exponha diretamente à internet nem use para armazenar credenciais bancárias.
