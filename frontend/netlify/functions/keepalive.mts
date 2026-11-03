export default async () => {
  const apiUrl = Netlify.env.get("CRYPTORESGATE_API_URL") || "https://cryptoresgate.onrender.com";
  const operatorKey = Netlify.env.get("CRYPTORESGATE_OPERATOR_KEY");
  if (!operatorKey) {
    console.error("CRYPTORESGATE_OPERATOR_KEY is not configured");
    return;
  }

  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/api/v1/admin/monitor/run`, {
      method: "POST",
      headers: {
        "X-Operator-Key": operatorKey,
        "Accept": "application/json"
      },
      signal: AbortSignal.timeout(25000)
    });
    const body = await response.text();
    if (!response.ok) {
      console.error("CryptoResgate monitor failed:", response.status, body.slice(0, 1000));
      return;
    }
    console.log("CryptoResgate monitor executed:", body);
  } catch (error) {
    console.error("CryptoResgate monitor request error:", error);
  }
};

export const config = {
  schedule: "*/5 * * * *"
};
