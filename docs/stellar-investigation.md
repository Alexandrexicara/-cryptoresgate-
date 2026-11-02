# Investigação Stellar (XLM)

## Endpoint

`GET /api/v1/public/stellar/transaction/{tx_hash}`

Consulta somente leitura a rede pública Stellar (Horizon). O hash deve conter 64 caracteres hexadecimais, sem prefixo `0x`.

## O que a análise verifica

- existência e sucesso da transação;
- conta de origem, memo e tipo de memo;
- operações de pagamento, ativo, quantidade e destino;
- configuração SEP-29 `config.memo_required` na conta de destino.

Quando a transação foi confirmada, não contém memo e o destino publica a exigência de memo, o resultado é classificado como `possible_uncredited_missing_memo`.

## Limite essencial

Essa classificação é um **indício técnico**, não uma prova de que uma exchange deixou de creditar o depósito. A blockchain não expõe o livro-razão interno da exchange. O titular precisa comprovar que o endereço/memo eram os dados de depósito da própria conta e obter a confirmação do destinatário.

A classificação não identifica pessoas, não tenta descobrir dados KYC e não inicia contato automático ou movimentação de fundos. O próximo passo é o titular abrir solicitação no canal oficial da exchange e fornecer TXID e comprovante da plataforma de origem.

## Teste manual

Use um hash público Stellar conhecido:

`GET /api/v1/public/stellar/transaction/{64-hex-hash}`

Verifique `found`, `status`, `memo_present`, `payments`, `classification` e `notice`. Um teste com transação comum deve resultar em `confirmed_transfer_requires_recipient_verification`, não em recuperação confirmada.

## Escopo atual

Este módulo cobre Stellar/XLM. Ethereum e redes EVM continuam usando o endpoint existente `GET /api/v1/public/transaction/{0x-hash}`. Bitcoin, Solana, TRON e outras redes ainda precisam de adaptadores próprios antes de serem anunciadas como suportadas para investigação automática.
