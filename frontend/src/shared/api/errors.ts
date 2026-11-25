import axios from "axios";

export function apiErrorMessage(error: unknown, fallback: string) {
  if (!axios.isAxiosError(error)) return fallback;

  const payload: unknown = error.response?.data;
  if (payload && typeof payload === "object") {
    const detail = "detail" in payload ? payload.detail : null;
    if (typeof detail === "string") return detail;
    const firstValue = Object.values(payload).find((value) => value !== undefined);
    if (typeof firstValue === "string") return firstValue;
    if (Array.isArray(firstValue) && typeof firstValue[0] === "string") {
      return firstValue[0];
    }
  }
  if (error.code === "ECONNABORTED" || !error.response) {
    return "Le serveur ne répond pas. Vérifiez votre connexion et réessayez.";
  }
  return fallback;
}
