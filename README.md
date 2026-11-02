# CryptoResgate

Plataforma de triagem técnica e acompanhamento de casos de criptoativos potencialmente recuperáveis.

## Objetivo

Identificar situações técnicas que possam admitir recuperação legítima — por exemplo, depósitos não creditados em exchanges, redes incompatíveis e ativos presos em contratos — e orientar o titular por um fluxo transparente de análise, autorização e prestação de serviço.

## Limites fundamentais

- Um endereço blockchain não identifica, por si só, uma pessoa nem fornece contato privado.
- APIs públicas de exchanges não dão acesso à identidade ou aos contatos de seus clientes.
- O sistema não envia mensagens privadas diretamente para carteiras arbitrárias. O titular precisa iniciar o contato ou autorizar um canal de comunicação.
- Nunca solicitar seed phrase, chave privada, senha ou código 2FA.
- Nunca movimentar ativos de terceiros sem autorização válida.
- Saldo parado não significa ativo perdido ou recuperável.
- A IA auxilia na triagem; não comprova titularidade nem garante recuperação.
- A comissão de 50% só pode ser aplicada quando estiver previamente aceita em contrato, sobre o valor líquido efetivamente recuperado e conforme a lei aplicável.

## Arquitetura inicial

- `backend/`: API e serviços de análise.
- `contracts/`: contratos inteligentes.
- `frontend/`: interface web e fluxo de consentimento.
- `docs/`: arquitetura, segurança e operação.
- `legal/`: minutas sujeitas à revisão jurídica.
- `tests/`: testes automatizados.

## Integração de IA NVIDIA

Configurar credenciais somente em variáveis de ambiente no servidor. Nunca colocar chaves em arquivos versionados ou no frontend. Consulte `.env.example`.

## Contrato inteligente

A primeira implementação é experimental e limitada a pagamentos nativos da rede escolhida, com divisão imediata entre dois endereços informados no deploy. Não é uma carteira de custódia e não recupera ativos automaticamente de endereços de terceiros. Não implantar em mainnet antes de testes, revisão independente e auditoria.

## Desenvolvimento

Consulte os documentos em `docs/`. O projeto ainda está em fase inicial; funcionalidades não implementadas não devem ser anunciadas como disponíveis.


## Interface web

O frontend está em `frontend/`, usando React e Vite.

- `npm install` — instala as dependências.
- `npm run dev` — inicia o ambiente local.
- `npm run build` — gera a versão de produção em `frontend/dist`.

Configure `VITE_API_URL` no frontend para apontar à API. No backend, configure `CORS_ORIGINS` com as origens exatas autorizadas.

## Consulta pública de transações EVM

A rota `GET /api/v1/public/transaction/{tx_hash}` consulta uma transação por meio do endpoint RPC configurado em `EVM_RPC_URL`. A consulta é somente leitura e não identifica titulares nem movimenta ativos. O endpoint RPC deve corresponder à rede que será consultada.

## Estado de implementação

A interface inicial, cadastro/consulta de casos, triagem NVIDIA e consulta pública EVM estão implementados no código. O funcionamento integrado ainda depende da configuração do banco, RPC e credenciais do provedor, além de testes de ponta a ponta.

Autenticação social, painel administrativo completo, prova criptográfica de carteira e monitoramento contínuo de redes permanecem pendentes. Não anuncie esses recursos como disponíveis até serem implementados e testados.
