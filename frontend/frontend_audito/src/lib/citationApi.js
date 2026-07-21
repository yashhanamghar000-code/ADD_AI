export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Matches AuthContext.tsx / services/api.ts exactly: token lives in
// sessionStorage under "audito_token" — not localStorage.
export function getAuthToken() {
  return window.sessionStorage.getItem("audito_token");
}

export function getDocumentFileUrl(fileId) {
  return `${API_BASE_URL}/api/documents/${fileId}/file`;
}

export function getAuthHeaders() {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}