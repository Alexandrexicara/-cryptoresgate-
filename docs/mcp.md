# MCP — ChatGPT e outros clientes

O servidor MCP permite que um usuário consulte orientações, envie voluntariamente um caso com consentimento explícito e consulte o status usando a referência secreta recebida no cadastro.

## Ferramentas expostas
- `recovery_guidance`: orientação pública e segura por tipo de ocorrência.
- `submit_recovery_case`: intake voluntário; exige `consent_to_analysis=true`; devolve uma referência aleatória de alta entropia.
- `get_recovery_case_status`: retorna somente status e rede usando a referência secreta. Não expõe contatos nem documentos privados.

## Publicação
Criar um serviço separado no Render apontando para `backend/`, instalar `requirements.txt`, definir `DATABASE_URL` como secret e iniciar com `python mcp_server.py`. O servidor usa Streamable HTTP; validar a URL MCP gerada no deploy antes de cadastrar no ChatGPT em Configurações > Apps/Conectores > criar conector MCP (a disponibilidade e o método de autenticação dependem do cliente).

## Segurança
- Não habilitar ferramentas de transferência, assinatura ou varredura de identidade.
- Não pedir seed phrase, chave privada, senha ou 2FA.
- Referência do caso é segredo de acesso: usuário deve guardá-la e não publicá-la.
- Para produção, adicionar autenticação OAuth por usuário, rate limiting, política de retenção, criptografia de contatos e logs sem dados pessoais.
- O MCP não torna automaticamente os dados do projeto visíveis em qualquer chat. O usuário precisa conectar o servidor MCP no cliente compatível e autorizar o acesso.
