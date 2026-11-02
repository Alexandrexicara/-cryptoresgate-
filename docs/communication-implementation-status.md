# Comunicação implementada e estado operacional

## Implementado no backend

- Endpoint `POST /api/v1/cases/{case_reference}/contact`: registra endereço informado pelo titular somente com consentimento explícito, criptografa o e-mail e inicia confirmação.
- Endpoint `GET /api/v1/contact/verify?token=...`: confirma token de uso único com validade de 30 minutos.
- Endpoint `DELETE /api/v1/cases/{case_reference}/contact`: revoga o consentimento e remove o contato armazenado.
- Endpoint `POST /api/v1/cases/{case_reference}/notifications`: envia atualização de caso somente para e-mail verificado, com consentimento ativo, autenticação de operador e limite de cinco mensagens em 24 horas.
- Limite de três solicitações de confirmação por caso por hora.
- Hash do endereço para busca/auditoria; e-mail criptografado com Fernet.
- Auditoria do consentimento e da confirmação.
- E-mail de confirmação transacional por SMTP com STARTTLS ou SMTP SSL.
- Nenhuma seed phrase, chave privada, senha ou 2FA é solicitada.
- Nenhum e-mail é obtido por scraping ou derivado de endereço blockchain.

## Variáveis necessárias no Render

- `CONTACT_ENCRYPTION_KEY`: chave Fernet gerada fora do repositório; manter estável e fazer backup seguro. Perder a chave impede descriptografar contatos existentes.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`.
- `PUBLIC_APP_URL`: URL pública do frontend, opcional (padrão `https://cryptoresgate.netlify.app`).
- `OPERATOR_API_KEY`: segredo longo para autorizar notificações operacionais; guardar somente no servidor e no painel seguro do operador.
- `SMTP_USE_SSL`: `true` para SMTP SSL direto, senão STARTTLS.
- `SMTP_TIMEOUT_SECONDS`: timeout opcional.

Sem essas configurações, o endpoint falha fechado e não afirma que enviou e-mail.

## Banco

A tabela `contact_preferences` é criada pela migração `backend/migrations/002_contact_preferences.sql`. A migração foi preparada e testada em branch temporária Neon; ainda requer aprovação para aplicar no banco principal.

## Ainda não ativo

- Push Protocol: exige canal oficialmente criado e signer de operação protegido. Não foi criado nem configurado um signer/carteira automaticamente.
- XMTP: exige identidade/inbox do destinatário e integração com SDK compatível; endereço EVM isolado não basta.
- ENS: registros são públicos, mas não equivalem a consentimento para marketing. Não serão usados para campanhas frias.
- WhatsApp: exige WhatsApp Business Platform e opt-in comprovável.
- Monitoramento automático amplo de todas as carteiras não está implementado por esta entrega.

## Estado dos testes

Os testes unitários cobrem criptografia, ausência de chave e falha fechada sem SMTP. Testes integrados exigem banco migrado e credenciais SMTP reais; não usar destinatários reais sem autorização.
