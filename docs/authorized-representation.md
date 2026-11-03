# Atendimento e representação técnica autorizada — Crypto Resgate

## Finalidade

O Crypto Resgate presta assistência técnica e administrativa ao titular legítimo de criptoativos ou da conta relacionada a uma transferência. Com autorização expressa, a plataforma pode organizar evidências públicas, preparar relatórios, acompanhar protocolos e auxiliar o titular na comunicação com exchanges, custodiante, provedores e autoridades competentes.

A plataforma não se apresenta como proprietária dos ativos, não presume titularidade a partir de um endereço blockchain e não garante recuperação.

## Fluxo obrigatório

1. **Cadastro do solicitante:** coletar apenas os dados necessários para abrir o atendimento.
2. **Verificação de legitimidade:** confirmar identidade do solicitante por processo proporcional e seguro. Se ele não for o titular, exigir prova documental de representação legal ou autorização válida.
3. **Mandato específico:** registrar autorização destacada, datada, vinculada ao caso e revogável. Ela deve identificar o titular, o representante/plataforma, o escopo, as instituições que poderão ser contatadas, os dados que podem ser compartilhados, o prazo e os limites da atuação.
4. **Prova de controle quando aplicável:** solicitar assinatura de mensagem ou outro mecanismo não custodial recomendado pela rede, sem jamais pedir seed phrase, chave privada, senha, código 2FA ou acesso remoto à carteira.
5. **Análise técnica:** validar hash, rede, ativo, montante, endereços, recibos, confirmações e eventos de token. Distinguir fatos on-chain de hipóteses e de dados internos que só a exchange pode confirmar.
6. **Relatório e revisão humana:** gerar relatório com fontes, horários, limitações, classificação de evidência e pedido objetivo. Um revisor confere o conteúdo antes de qualquer envio externo.
7. **Contato com a instituição:** usar canal oficial e respeitar o procedimento da exchange. Se ela exigir que o titular abra o chamado ou conclua autenticação, orientar o titular e fornecer o material para envio por ele.
8. **Acompanhamento:** registrar protocolo, data, canal, documentos enviados, resposta recebida, pendências, prazo informado e próximo passo. Atualizar o status sem inferir aprovação ou recuperação.
9. **Revogação e encerramento:** permitir revogar a autorização e interromper novos contatos. Preservar apenas registros cuja retenção seja necessária e legalmente justificada.

## Escopo de autorização

A autorização pode permitir, conforme escolha expressa do titular:

- consultar e organizar informações públicas de blockchain relacionadas ao caso;
- preparar relatório técnico e minuta de solicitação;
- compartilhar com a instituição indicada os dados estritamente necessários;
- acompanhar protocolo e respostas;
- receber e organizar documentos fornecidos pelo titular.

A autorização **não** permite movimentar ativos, assinar transações em nome do titular, acessar conta/carteira, alterar credenciais, aceitar acordos, renunciar a direitos, receber fundos, pagar taxas em nome do cliente ou assumir poderes legais não expressamente conferidos e aceitos pela instituição.

Qualquer poder adicional exige instrumento separado, análise jurídica e confirmação de que a instituição o aceita.

## Modelo de declaração do titular

> Eu, [nome completo], declaro ser o titular legítimo da conta e/ou dos criptoativos relacionados ao caso [referência], ou apresento em anexo documento válido que comprova meus poderes de representação. Autorizo o Crypto Resgate, no escopo descrito neste instrumento, a analisar os dados públicos da transação, organizar evidências, preparar relatórios e, quando permitido pela instituição destinatária, encaminhar solicitações técnicas e acompanhar os respectivos protocolos. Autorizo o compartilhamento apenas dos dados e documentos estritamente necessários com [instituição]. Compreendo que a instituição pode exigir autenticação, formulários, procuração ou contato direto do titular; que esta autorização não garante recuperação; e que o Crypto Resgate não pode movimentar meus ativos nem solicitar minhas chaves privadas, seed phrase, senha ou códigos de autenticação. Posso revogar esta autorização pelos canais informados, sem prejuízo dos registros cuja retenção seja legalmente necessária.
>
> **Titular:** [nome]  
> **Caso:** [referência]  
> **Instituição autorizada para contato:** [nome]  
> **Escopo e dados autorizados:** [descrição]  
> **Validade:** [data inicial] até [data final ou conclusão do caso]  
> **Data e assinatura:** [assinatura verificável]

Este texto é um modelo operacional inicial, não substitui revisão por advogado no Brasil nem os formulários/mandatos próprios de cada exchange. Não deve ser usado como procuração genérica.

## Padrão de comunicação com exchanges

O Crypto Resgate deve identificar-se claramente como prestador de assistência técnica autorizado, indicar a referência do caso e anexar a autorização pertinente. A mensagem deve pedir apenas confirmação de procedimento, requisitos e análise do evento; nunca solicitar dados pessoais, saldo, identidade ou informação interna de terceiros sem que o solicitante esteja autenticado e a instituição possa legalmente fornecer tais dados.

Se a autorização não estiver verificada ou o canal não aceitar representantes, não enviar a solicitação em nome do cliente. Preparar a minuta e orientar o próprio titular a submetê-la no canal autenticado.

## Status padronizados

- `received`: caso recebido;
- `identity_pending`: aguardando verificação do titular/representante;
- `authorization_pending`: aguardando autorização específica;
- `technical_review`: análise técnica em andamento;
- `report_ready`: relatório revisado;
- `customer_submission_required`: instituição exige envio pelo titular;
- `submitted_to_institution`: enviado por canal aceito, com protocolo;
- `awaiting_institution`: aguardando resposta;
- `additional_documents_required`: documentação adicional solicitada;
- `institution_rejected`: solicitação recusada;
- `recovery_confirmed_by_customer`: recuperação confirmada com evidência fornecida pelo titular;
- `closed`: encerrado.

Nunca usar `recovered` apenas porque uma transferência chegou a um endereço de exchange. A confirmação de recuperação exige evidência adequada do titular ou da instituição.

## Requisitos de segurança e conformidade antes da operação

- controle de acesso por função, autenticação forte para operadores e trilha de auditoria;
- criptografia em trânsito e em repouso, retenção mínima e descarte seguro;
- consentimento separado para análise, contato e compartilhamento de documentos;
- mecanismo de revogação, canal de privacidade e atendimento a direitos LGPD;
- validação de arquivos, proteção contra malware e limites de upload;
- revisão humana antes de enviar mensagens ou anexos externos;
- templates específicos por instituição, sem automatizar login, contornar CAPTCHA ou burlar controles;
- nenhuma cobrança ou taxa de recuperação sem contrato claro, preço transparente e confirmação do cliente;
- avaliação jurídica e de proteção de dados antes do lançamento comercial.

## Caso técnico de referência — 9.996 USDT

O caso público documentado no repositório permanece apenas como referência técnica. Não há titular identificado nem autorização de cliente para representação. Portanto, não deve ser submetido como pedido de recuperação em nome de alguém. Pode ser usado somente para testar análise pública e para formular uma pergunta geral sobre procedimentos, sem solicitar dados internos ou revelar informações de titular.
