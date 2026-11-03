import re
from typing import Any
import httpx

RPC_URL = "https://api.mainnet-beta.solana.com"
_SIG_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{80,100}$")

class SolanaProviderError(RuntimeError):
    pass

def _account_keys(message: dict[str, Any]) -> list[str]:
    keys=[]
    for item in message.get("accountKeys") or []:
        if isinstance(item, str):
            keys.append(item)
        elif isinstance(item, dict):
            keys.append(str(item.get("pubkey") or ""))
    return keys

def _token_deltas(meta: dict[str, Any]) -> list[dict[str, Any]]:
    before={}
    after={}
    for field, target in (("preTokenBalances", before), ("postTokenBalances", after)):
        for item in meta.get(field) or []:
            if not isinstance(item, dict): continue
            ui=item.get("uiTokenAmount") or {}
            key=(item.get("accountIndex"), item.get("mint"), item.get("owner"))
            try: amount=int(ui.get("amount", "0"))
            except (TypeError, ValueError): continue
            target[key]=(amount, ui.get("decimals"))
    result=[]
    for key in set(before)|set(after):
        old,dec0=before.get(key,(0,None)); new,dec1=after.get(key,(0,None))
        delta=new-old
        if delta == 0: continue
        decimals=dec1 if dec1 is not None else dec0
        result.append({"account_index":key[0],"mint":key[1],"owner":key[2],
                       "amount_raw":str(abs(delta)),"decimals":decimals,
                       "direction":"received" if delta>0 else "sent"})
    return result

def _parsed_native_transfers(transaction: dict[str, Any]) -> list[dict[str, Any]]:
    message=transaction.get("transaction",{}).get("message",{})
    meta=transaction.get("meta") or {}
    instructions=list(message.get("instructions") or [])
    for group in meta.get("innerInstructions") or []:
        instructions.extend(group.get("instructions") or [])
    transfers=[]
    for ix in instructions:
        parsed=ix.get("parsed") if isinstance(ix,dict) else None
        if not isinstance(parsed,dict) or parsed.get("type") not in {"transfer","transferWithSeed"}: continue
        info=parsed.get("info") or {}
        lamports=info.get("lamports")
        if not isinstance(lamports,int) or lamports<=0: continue
        transfers.append({"from_address":info.get("source"),"to_address":info.get("destination"),
                          "amount_lamports":lamports,"amount_sol":(lambda q: f"{q[0]}.{str(q[1]).rjust(9, \"0\").rstrip(\"0\")}".rstrip(".") if q[1] else str(q[0]))(divmod(lamports,1_000_000_000))})
    return transfers

async def inspect_solana_transaction(signature: str) -> dict[str, Any]:
    if not _SIG_RE.fullmatch(signature):
        raise ValueError("Informe uma assinatura Solana válida em Base58.")
    timeout=httpx.Timeout(18.0,connect=7.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response=await client.post(RPC_URL,json={"jsonrpc":"2.0","id":1,"method":"getTransaction",
                "params":[signature,{"encoding":"jsonParsed","commitment":"finalized","maxSupportedTransactionVersion":0}]})
            response.raise_for_status(); payload=response.json()
        except (httpx.HTTPError,ValueError) as exc:
            raise SolanaProviderError("Não foi possível consultar o RPC público Solana.") from exc
    if not isinstance(payload,dict) or payload.get("error"):
        raise SolanaProviderError("O RPC Solana retornou erro na consulta.")
    tx=payload.get("result")
    if tx is None:
        return {"found":False,"network":"solana","transaction_hash":signature,"status":"not_found",
                "classification":"unknown","recovery_candidate":False,
                "notice":"Assinatura não encontrada ou ainda não disponível no RPC consultado. Isso não prova perda."}
    meta=tx.get("meta") or {}
    if meta.get("err") is not None:
        status="failed"; classification="failed_on_chain"
    else:
        status="confirmed" if tx.get("slot") is not None else "pending"
        classification="pending_confirmation" if status=="pending" else "confirmed_transfer_requires_recipient_verification"
    token_deltas=_token_deltas(meta)
    native_transfers=_parsed_native_transfers(tx)
    if status=="confirmed" and not token_deltas and not native_transfers:
        classification="successful_transaction_no_supported_transfer_detected"
    return {"found":True,"network":"solana","transaction_hash":signature,"status":status,
        "slot":tx.get("slot"),"fee_lamports":meta.get("fee"),"error":meta.get("err"),
        "token_balance_changes":token_deltas,"native_transfers":native_transfers,
        "classification":classification,"recovery_candidate":False,
        "notice":"Consulta pública somente leitura. Alterações de saldo não provam crédito interno em exchange nem possibilidade de recuperação; movimentos não interpretados podem não aparecer nesta análise."}
