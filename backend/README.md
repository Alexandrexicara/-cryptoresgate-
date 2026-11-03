# Backend CryptoResgate

## Executar localmente

Na pasta `backend`:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Verificação: `GET /health`. Documentação interativa: `/docs`.

## NVIDIA

Configure no ambiente do servidor:
- `NVIDIA_API_KEY`
- `NVIDIA_MODEL`
- opcionalmente `NVIDIA_BASE_URL`

O backend chama a API compatível com chat completions. A chave nunca deve ir para o frontend ou para o Git. Não há fallback que simule uma resposta se a credencial estiver ausente.

## Endpoint inicial

`POST /api/v1/analyze-case` recebe dados técnicos de uma transação e retorna uma triagem preliminar. A resposta da IA não pode acionar transações, identificar pessoas ou comprovar titularidade.


## Consulta EVM e tokens

A rota `GET /api/v1/public/transaction/{tx_hash}?network=ethereum` lê transações e eventos padrão Transfer de tokens ERC-20/BEP-20. Redes aceitas: ethereum, bsc, polygon, arbitrum, optimism e base. Configure os RPCs por rede no ambiente do backend. EVM_RPC_URL continua aceito para compatibilidade com EVM_NETWORK. O serviço verifica o chain ID e nunca assina ou envia transações. Metadados de tokens são opcionais; sem decimals, o retorno preserva o valor bruto.
