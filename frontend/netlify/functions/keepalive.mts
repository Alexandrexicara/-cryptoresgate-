export default async () => {
  const apiUrl = "https://cryptoresgate.onrender.com";
  try {
    const response = await fetch(`${apiUrl}/health`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      signal: AbortSignal.timeout(25000)
    });
    const body = await response.text();
    if (!response.ok) {
      console.error("CryptoResgate keepalive failed:", response.status, body.slice(0, 500));
      return;
    }
    console.log("CryptoResgate backend keepalive OK:", body);
  } catch (error) {
    console.error("CryptoResgate keepalive request error:", error);
  }
};
export const config = { schedule: "*/5 * * * *" };
