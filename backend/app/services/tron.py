import re
from typing import Any
import httpx

BASE_URL="https://api.trongrid.io"
_HASH_RE=re.compile(r"^[a-fA-F0-9]{64}$")
_ADDRESS_RE=re.compile(r"^41[0-9a-fA-F]{40}$")
_TRANSFER_TOPIC="ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

class TronProviderError(RuntimeError):
    pass

def _hex_int(value: Any) -> int | None:
    try:
        if isinstance(value,int): return value
        if isinstance(value,str): return int(value,16)
    except ValueError: return None
    return None

def _decode_trc20(log: dict[str,Any]) -> dict[str,Any] | None:
    topics=log.get("topics") or []
    data=log.get("data") or ""
    if len(topics)!=3 or str(topics[0]).lower().removeprefix("0x")!=_TRANSFER_TOPIC: return None
    if not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{64}",str(topics[1])) or not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{64}",str(topics[2])): return None
    if not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{64}",str(data)): return None
    sender=str(topics[1])[-40:].lower(); recipient=str(topics[2])[-40:].lower()
    return {"token_contract":log.get("address"),"from_address_hex":"41"+sender,
            "to_address_hex":"41"+recipient,"amount_raw":str(int(str(data).removeprefix("0x"),16))}

async def inspect_tron_transaction(txid: str) -> dict[str,Any]:
    if not _HASH_RE.fullmatch(txid):
        raise ValueError("Informe um TXID TRON válido com 64 caracteres hexadecimais.")
    timeout=httpx.Timeout(18.0,connect=7.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def post(path: str) -> dict[str,Any]:
            try:
                response=await client.post(f"{BASE_URL}/wallet/{path}",json={"value":txid})
                response.raise_for_status(); data=response.json()
            except (httpx.HTTPError,ValueError) as exc:
                raise TronProviderError("Não foi possível consultar o nó público TRON.") from exc
            if not isinstance(data,dict): raise TronProviderError("Resposta inválida do nó TRON.")
            return data
        tx,info=await __import__("asyncio").gather(post("gettransactionbyid"),post("gettransactioninfobyid"))
    if not tx:
        return {"found":False,"network":"tron","transaction_hash":txid,"status":"not_found",
                "classification":"unknown","recovery_candidate":False,
                "notice":"TXID não encontrado no nó consultado. Isso não prova perda de ativos."}
    contracts=(tx.get("raw_data") or {}).get("contract") or []
    native=[]
    for item in contracts:
        value=item.get("parameter",{}).get("value",{})
        if item.get("type")=="TransferContract":
            amount=value.get("amount")
            if isinstance(amount,int) and amount>0:
                native.append({"from_address_hex":value.get("owner_address"),"to_address_hex":value.get("to_address"),
                               "amount_sun":amount,"amount_trx":f"{amount/1_000_000:.6f}".rstrip("0").rstrip(".")})
    logs=info.get("log") or []
    tokens=[decoded for log in logs if isinstance(log,dict) and (decoded:=_decode_trc20(log))]
    receipt=info.get("receipt") or {}
    confirmed=bool(info.get("blockNumber"))
    success=confirmed and (receipt.get("result") in {None,"SUCCESS"}) and not tx.get("ret")
    status="confirmed" if success else "failed" if confirmed else "pending"
    classification=("failed_on_chain" if status=="failed" else "pending_confirmation" if status=="pending"
                    else "confirmed_transfer_requires_recipient_verification" if native or tokens
                    else "successful_transaction_no_supported_transfer_detected")
    return {"found":True,"network":"tron","transaction_hash":txid,"status":status,
            "block_number":info.get("blockNumber"),"native_transfers":native,"token_transfers":tokens,
            "token_transfer_count":len(tokens),"classification":classification,"recovery_candidate":False,
            "notice":"Consulta pública somente leitura. Transferência confirmada não comprova crédito interno em exchange nem possibilidade de recuperação. Endereços hexadecimais TRON são apresentados sem conversão Base58."}
