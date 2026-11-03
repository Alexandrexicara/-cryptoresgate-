import { useState } from "react";

const CHAINS = {
  "0x1": "Ethereum",
  "0x38": "BNB Smart Chain",
  "0x89": "Polygon",
  "0xa4b1": "Arbitrum",
  "0xa": "Optimism",
  "0x2105": "Base",
};

async function api(base, path, options = {}) {
  const response = await fetch(base + path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Não foi possível concluir a operação.");
  return data;
}

export default function WalletAuthorization({ caseReference, apiBase }) {
  const [busy, setBusy] = useState(false);
  const [wallet, setWallet] = useState("");
  const [chainId, setChainId] = useState(null);
  const [proof, setProof] = useState(false);
  const [institution, setInstitution] = useState("Coinbase");
  const [represent, setRepresent] = useState(false);
  const [feeConsent, setFeeConsent] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [authorized, setAuthorized] = useState(false);

  async function proveWallet() {
    setBusy(true); setError(""); setMessage("");
    try {
      if (!window.ethereum) throw new Error("Instale ou abra uma carteira EVM compatível, como MetaMask.");
      const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
      if (!accounts?.[0]) throw new Error("Nenhuma carteira foi selecionada.");
      const address = accounts[0].toLowerCase();
      const chain = await window.ethereum.request({ method: "eth_chainId" });
      if (!CHAINS[chain]) throw new Error("Troque para Ethereum, BNB Chain, Polygon, Arbitrum, Optimism ou Base.");
      const challenge = await api(apiBase, `/api/v1/cases/${encodeURIComponent(caseReference)}/wallet/challenge`, {
        method: "POST",
        body: JSON.stringify({ wallet_address: address, chain_id: Number.parseInt(chain, 16) }),
      });
      const signature = await window.ethereum.request({
        method: "personal_sign",
        params: [challenge.message, address],
      });
      await api(apiBase, `/api/v1/cases/${encodeURIComponent(caseReference)}/wallet/verify`, {
        method: "POST",
        body: JSON.stringify({ wallet_address: address, nonce: challenge.nonce, signature }),
      });
      setWallet(address); setChainId(Number.parseInt(chain, 16)); setProof(true);
      setMessage("Controle da carteira comprovado. Isso não comprova identidade civil nem titularidade de conta em exchange.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function acceptAuthorization(e) {
    e.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const data = await api(apiBase, `/api/v1/cases/${encodeURIComponent(caseReference)}/authorization`, {
        method: "POST",
        body: JSON.stringify({
          wallet_address: wallet,
          institution,
          authorized_scope: ["prepare_report", "prepare_exchange_request", "submit_when_institution_allows", "track_case"],
          service_fee_bps: 5000,
          terms_version: "1.0",
          consent_to_represent: represent,
          consent_to_fee: feeConsent,
        }),
      });
      setAuthorized(true);
      setMessage(`Autorização registrada. Divisão contratual registrada: ${data.service_fee_percent}% serviço e ${data.client_percent}% titular. A liquidação automática ainda depende de um meio de pagamento aceito e conectado.`);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function revoke() {
    setBusy(true); setError(""); setMessage("");
    try {
      await api(apiBase, `/api/v1/cases/${encodeURIComponent(caseReference)}/authorization?wallet_address=${encodeURIComponent(wallet)}`, { method: "DELETE" });
      setAuthorized(false); setMessage("Autorização revogada.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <section className="form contactForm">
    <h3>Comprovar carteira e autorizar o serviço</h3>
    <p className="muted">A assinatura é uma mensagem gratuita: não envia moedas, não pede seed phrase e não concede acesso à carteira.</p>
    {!proof ? <button type="button" className="secondary" disabled={busy} onClick={proveWallet}>{busy ? "Verificando..." : "Conectar carteira e comprovar controle"}</button> : <>
      <p><b>Carteira:</b> {wallet}</p>
      <p><b>Rede:</b> {Object.entries(CHAINS).find(([id]) => Number.parseInt(id, 16) === chainId)?.[1] || chainId}</p>
      {!authorized && <form className="form" onSubmit={acceptAuthorization}>
        <label>Exchange ou instituição<input value={institution} onChange={e => setInstitution(e.target.value)} required minLength="2" maxLength="120" /></label>
        <div className="warning">Remuneração prevista nesta versão: 50% para o serviço e 50% para o titular, somente sobre valores efetivamente recuperados e conforme contrato. A assinatura não autoriza movimentar fundos. A instituição pode exigir que o próprio titular faça o protocolo.</div>
        <label className="check"><input type="checkbox" checked={represent} onChange={e => setRepresent(e.target.checked)} /> Autorizo o Crypto Resgate a preparar relatórios, solicitações e acompanhar este caso perante a instituição indicada, dentro do escopo informado.</label>
        <label className="check"><input type="checkbox" checked={feeConsent} onChange={e => setFeeConsent(e.target.checked)} /> Aceito a remuneração de 50% do valor efetivamente recuperado, com divisão registrada e liquidação por mecanismo autorizado.</label>
        <button className="primary" disabled={busy || !represent || !feeConsent || !institution.trim()}>{busy ? "Registrando..." : "Confirmar autorização e remuneração"}</button>
      </form>}
      {authorized && <button type="button" className="secondary" disabled={busy} onClick={revoke}>Revogar autorização</button>}
    </>}
    {error && <div className="alert error">{error}</div>}
    {message && <div className="alert success">{message}</div>}
  </section>;
}
