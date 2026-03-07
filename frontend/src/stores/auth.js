import { ref } from "vue";

const TOKEN_KEY = "meal_api_token";
const token = ref(localStorage.getItem(TOKEN_KEY));

export function getToken() {
  return token.value;
}

export function setToken(newToken) {
  localStorage.setItem(TOKEN_KEY, newToken);
  token.value = newToken;
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  token.value = null;
}

export function isAuthenticated() {
  return Boolean(token.value);
}
