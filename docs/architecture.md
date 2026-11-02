# Arquitetura e fluxo de atendimento

## Fluxo de ponta a ponta

1. **Monitoramento público:** indexar eventos e transações em redes suportadas usando RPC/exploradores públicos. Não presumir que um endereço pertence a uma pessoa.
2. **Triagem determinística:** validar rede, contrato/token, hash, confirmações, destino e tipo de falha. Registrar evidências e nível de confiança.
3. **Análise assistida por NVIDIA:** produzir explicação e classificação a partir dos dados públicos já validados. A IA não decide movimentações, não assina transações e não declara titularidade.
4. **Entrada voluntária:** o titular acessa o portal, informa o identificador da transação e conecta uma carteira compatível. A conexão não concede permissão para transferir fundos.
5. **Prova de controle:** solicitar uma assinatura de mensagem com nonce e validade, sem pedir segredo. A assinatura prova controle da chave naquele momento, não identidade civil nem propriedade legal incontestável.
6. **Análise humana e documental:** verificar se o procedimento da exchange ou da rede realmente permite recuperação. Em exchanges, o próprio titular deve abrir o chamado quando exigido.
7. **Contrato de serviço:** exibir escopo, riscos, comissão, cálculo do valor líquido, condições de encerramento e canal de reclamação. Exigir aceite inequívoco antes de qualquer serviço cobrável.
8. **Recuperação:** executar apenas o procedimento autorizado pelo titular e permitido pelo custodiante/protocolo.
9. **Liquidação:** se o titular optar por um contrato de divisão e a origem dos fundos permitir, a transação envia fundos diretamente ao contrato, que divide o valor. Se a exchange devolver diretamente ao titular, a cobrança será contratual e não pode ser imposta tecnicamente pelo CryptoResgate.

## Comunicação

Não existe um canal universal de mensagens privadas para endereços EVM ou carteiras comuns. O produto não deve tentar identificar pessoas por análise de endereço nem enviar mensagens on-chain não solicitadas. Notificações serão enviadas apenas a contatos fornecidos pelo titular ou a canais em que ele tenha optado por receber mensagens.

## Integração com exchanges

Começar com documentação e APIs oficiais públicas. Não usar credenciais de clientes, scraping de áreas privadas ou acesso não autorizado. Cada exchange define elegibilidade, taxas, documentos e fluxo próprios; em muitos casos somente o titular pode solicitar a recuperação.

## Limitações do MVP

- Monitoramento não equivale a identificação do dono.
- Saldo antigo não prova perda.
- Nem toda transação é reversível.
- Tokens em endereços controlados por exchanges dependem da política e capacidade técnica da exchange.
- A primeira versão do contrato inteligente não suporta todos os tokens ou redes.
