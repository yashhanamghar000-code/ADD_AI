/**
 * NEW FILE — copy into src/lib/citationApi.js
 *
 * Small helper for the citation viewer: builds the auth-header'd request
 * pdf.js needs to stream the original PDF from the new backend endpoint
 * GET /api/documents/{file_id}/file.
 *
 * IMPORTANT: adjust `getAuthToken()` and `API_BASE_URL` below to match
 * however your app already stores the JWT and the API base URL — this is
 * written generically since I don't have your existing auth/http-client
 * file in front of me. If you already have an `api.js`/`http.js` with an
 * axios instance or a token getter, just reuse that instead of this file.
 */

// Adjust this if your app already exposes an API base URL constant/env var.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Adjust this if your app stores the JWT under a different key, or in a
// context/store instead of localStorage.
export function getAuthToken() {
  return localStorage.getItem("token");
}

export function getDocumentFileUrl(fileId) {
  return `${API_BASE_URL}/api/documents/${fileId}/file`;
}

export function getAuthHeaders() {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
