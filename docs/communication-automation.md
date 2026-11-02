# Central de comunicação automatizada

## Objetivo

Permitir que o CryptoResgate prepare e entregue avisos legítimos sobre oportunidades de análise, sem criar uma carteira custodial, sem acessar contas de exchanges e sem tentar descobrir dados pessoais de titulares.

## O que cada canal realmente permite

### Push Protocol (notificações Web3)

- O CryptoResgate poderá operar um canal oficial após configurar e ativar esse canal conforme a documentação do protocolo.
- As notificações são vinculadas a endereços de carteira e podem ser recebidas em carteiras/aplicativos que integrem Push.
- A documentação do protocolo diferencia assinantes de não assinantes: mensagens/notificações de um canal podem cair na caixa de spam para quem não se inscreveu; solicitações de chat dependem de aceitação do destinatário.
- Portanto, não prometer entrega na caixa principal nem tratar Push como autorização para publicidade em massa.
- O backend deverá registrar canal, status de envio, resposta do provedor e identificador da mensagem, sem registrar chaves privadas.

Documentação: https://comms.push.org/docs/notifications/

### XMTP (mensagens privadas entre carteiras)

- Permite iniciar conversas usando identidade Ethereum, mas o destinatário precisa ter criado previamente uma identidade/inbox compatível e publicado os dados necessários.
- Um endereço blockchain qualquer não garante uma inbox XMTP.
- Usar apenas quando o destinatário estiver disponível no protocolo e respeitar pedidos/controles de bloqueio e spam.
- Não é um canal universal de entrega.

Documentação: https://xmtp.org/sdk/inboxes/

### ENS e contatos públicos

- Um titular pode publicar voluntariamente registros de contato no perfil ENS, inclusive e-mail e telefone.
- Só considerar registros explicitamente publicados pelo titular; não inferir, enriquecer ou correlacionar identidade privada por outros meios.
- Antes de enviar qualquer proposta comercial, verificar a base legal aplicável, finalidade, transparência, oposição/descadastro e regras anti-spam. A presença de um e-mail público não é, isoladamente, consentimento para marketing.

Documentação: https://support.ens.domains/en/articles/15102798-profiles-and-records

### E-mail e WhatsApp

- E-mail só será enviado a endereço fornecido pelo próprio titular no formulário ou publicado voluntariamente para contato, após verificação da base legal e preferência de comunicação.
- WhatsApp só será habilitado com opt-in verificável e integração oficial (WhatsApp Business Platform), respeitando templates, janela de atendimento e políticas da Meta.
- Não comprar, raspar ou montar listas de e-mails/telefones a partir de endereços blockchain.
- Toda mensagem terá identificação clara do CryptoResgate, motivo do contato, link para o portal oficial e opção simples de não receber novos avisos.

## Fluxo automático permitido

1. O monitor de blockchain encontra um evento público e cria uma oportunidade técnica, sem atribuir identidade a um endereço.
2. O motor de triagem valida rede, hash, contrato, evidências e limitações. Saldo parado nunca é classificado automaticamente como perda.
3. O sistema verifica apenas canais de contato que o titular publicou ou forneceu voluntariamente e os sinais de disponibilidade dos protocolos.
4. Se houver canal Web3 compatível, o sistema prepara uma notificação de baixo volume e respeita as regras do protocolo; mensagens privadas ficam condicionadas à aceitação do destinatário.
5. Se houver contato tradicional fornecido/opt-in, o sistema envia e-mail ou WhatsApp oficial dentro da finalidade autorizada.
6. Sem canal autorizado, a oportunidade permanece no painel e o CryptoResgate publica conteúdo informativo e uma página de consulta voluntária. Nenhuma mensagem é enviada ao endereço aleatório.
7. Respostas e consentimentos são registrados com data, finalidade, versão do aviso e origem. O titular pode revogar a autorização.
8. O atendimento só começa após o titular se apresentar, comprovar controle da carteira por assinatura de mensagem segura e aceitar os termos.

## Segurança e privacidade

- Nunca pedir seed phrase, chave privada, senha, código 2FA ou acesso à conta de exchange.
- Nunca assinar ou transmitir transações em nome do titular durante a triagem.
- Uma assinatura de mensagem demonstra controle técnico da chave naquele momento; não comprova identidade civil nem propriedade jurídica incontestável.
- Não enviar dados pessoais ou alegações de perda em notificações públicas/on-chain.
- Não incluir saldo ou valor de ativos no assunto de e-mail ou notificações que possam aparecer na tela bloqueada.
- Aplicar limitação de frequência, lista de supressão, auditoria, retenção mínima e proteção contra abuso.
- Não disparar campanhas em massa para carteiras aleatórias.
- O contrato inteligente não concede consentimento em nome do dono da carteira e não pode obrigar Binance ou outra exchange a encaminhar mensagens.

## Variáveis e dependências futuras

A integração só será ativada depois de implementar e testar:
- canal Push oficial, delegações mínimas e credenciais guardadas no servidor;
- adaptador XMTP para destinatários que tenham inbox compatível;
- provedor SMTP transacional para e-mails consentidos;
- WhatsApp Business Platform oficial, se aprovado;
- armazenamento criptografado de contatos e trilha de consentimento;
- filas, rate limit, retry idempotente, descadastro e monitoramento de entrega.

Nenhuma chave ou segredo de provedor deve ser colocado no frontend ou versionado no Git.

## Critérios de aceite

- Um endereço aleatório sem inbox/canal/contato publicado nunca gera alegação de mensagem entregue.
- O sistema distingue `queued`, `sent_to_provider`, `delivered` (somente com confirmação do provedor) e `failed`.
- Mensagem privada XMTP só é tentada quando o destinatário é compatível.
- E-mail/WhatsApp exigem origem de contato e base legal registradas.
- O titular consegue revogar consentimento e solicitar exclusão conforme política de retenção.
- Nenhuma etapa de comunicação movimenta criptoativos.
