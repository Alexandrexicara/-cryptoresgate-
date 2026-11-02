import os
from typing import Any

import httpx


class NvidiaConfigurationError(RuntimeError):
    pass


async def explain_case(case_data: dict[str, Any]) -> str:
    """
    Ask NVIDIA NIM for a cautious technical triage.
    This function must never initiate transactions or identify wallet owners.
    """
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    model = os.getenv("NVIDIA_MODEL", "").strip()

    if not api_key or not model:
        raise NvidiaConfigurationError(
            "Configure NVIDIA_API_KEY e NVIDIA_MODEL no ambiente do servidor."
        )

    # Only accept a narrow allowlist of public technical fields.
    safe_data = {
        "network": str(case_data.get("network", ""))[:80],
        "transaction_hash": str(case_data.get("transaction_hash", ""))[:160],
        "asset_contract": str(case_data.get("asset_contract", ""))[:160],
        "reported_issue": str(case_data.get("reported_issue", ""))[:1000],
        "public_evidence": str(case_data.get("public_evidence", ""))[:3000],
    }

    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 700,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um assistente de triagem técnica do CryptoResgate. "
                    "Analise somente os dados técnicos fornecidos. Não tente identificar "
                    "pessoas, donos de carteiras ou dados pessoais. Não presuma que saldo "
                    "parado está perdido. Não prometa recuperação. Não instrua transferências, "
                    "não solicite seed phrase, chave privada, senha ou 2FA. "
                    "Explique evidências, incertezas, próximos passos seguros e quando o "
                    "titular deve contatar diretamente a exchange. A resposta é uma sugestão "
                    "e exige validação humana."
                ),
            },
            {
                "role": "user",
                "content": "Faça a triagem técnica deste caso:\n" + str(safe_data),
            },
        ],
    }

    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Resposta inesperada do serviço NVIDIA.") from exc
