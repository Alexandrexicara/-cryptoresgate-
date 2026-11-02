# Segurança, privacidade e controles obrigatórios

## Segredos de carteira

O sistema jamais deve solicitar, receber, registrar, transmitir ou armazenar:
- seed phrase / frase de recuperação;
- chave privada;
- senha da carteira;
- códigos 2FA ou códigos de recuperação.

A conexão de carteira deve usar padrões de assinatura de mensagem e permissões mínimas. Não solicitar aprovações ERC-20 ilimitadas nem permissões de operador.

## Assinaturas

- Usar nonce aleatório, de uso único, associado à sessão.
- Incluir domínio, finalidade, endereço, rede e expiração na mensagem.
- Rejeitar replay, nonce reutilizado, domínio incorreto e assinatura expirada.
- Separar prova de controle da carteira de consentimento contratual.
- Mostrar o conteúdo exato antes da assinatura.

## Dados pessoais

- Coletar somente dados necessários.
- Informar finalidade, retenção, compartilhamento e canal de exclusão.
- Proteger dados em trânsito e em repouso.
- Restringir acesso por função e registrar ações administrativas.
- Não publicar informações que associem uma pessoa a um endereço sem base legal e consentimento.

## IA NVIDIA

- Chaves somente no backend, via secret manager/variáveis de ambiente.
- Enviar à IA apenas dados necessários e, sempre que possível, pseudonimizados.
- Tratar respostas do modelo como sugestões não confiáveis.
- Nunca permitir que saída do modelo execute transferências, altere permissões ou aprove contratos.
- Validar respostas com regras determinísticas e revisão humana.

## Smart contract

- Código experimental até auditoria independente.
- Testes unitários, fuzzing, análise estática e revisão de dependências.
- Sem função administrativa para confiscar fundos.
- Sem função de saque unilateral pelo operador.
- Endereços de beneficiários imutáveis na primeira versão.
- Não implantar em mainnet nem receber valores reais antes de revisão jurídica e auditoria.
