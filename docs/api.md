# API CryptoResgate

Base local: `http://localhost:8000`. Documentação OpenAPI: `/docs`.

## Saúde
- `GET /` — identificação e versão da API.
- `GET /health` — verificação de processo (não garante conexão com o banco).

## Casos
- `POST /api/v1/cases` — abre caso; exige `consent_to_privacy_notice=true` e `consent_to_analysis=true`.
- `GET /api/v1/cases/{case_reference}` — consulta estado, rede e data de criação.

O cadastro e a consulta dependem do PostgreSQL e das seis tabelas da migração inicial.

## Triagem
- `POST /api/v1/analyze-case` — análise preliminar com NVIDIA NIM. Depende de `NVIDIA_API_KEY` e `NVIDIA_MODEL`.

## Blockchain pública
- `GET /api/v1/public/transaction/{tx_hash}` — consulta somente leitura de transação EVM pelo `EVM_RPC_URL` configurado no servidor.

A rota EVM consulta somente a rede apontada pelo RPC. Não tente consultar hashes de redes incompatíveis. Nenhuma rota identifica titulares, pede segredos ou assina/envia transações.

## Códigos de resposta esperados
- `201`: caso registrado.
- `400`: consentimentos ausentes.
- `404`: referência inexistente.
- `409`: rede e hash já cadastrados.
- `422`: dados inválidos.
- `502`: provedor externo indisponível.
- `503`: banco ou configuração de serviço indisponível.

As rotas de caso ainda precisam ser testadas ponta a ponta depois da aplicação da migração Neon.
