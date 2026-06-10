import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { authApi } from "../api/auth";

const TOKEN_KEY = "tradingradar_token";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY));
  const user = ref<{ id: string; email: string; display_name: string } | null>(null);

  const isAuthenticated = computed(() => token.value !== null);

  function setToken(value: string | null) {
    token.value = value;
    if (value) {
      localStorage.setItem(TOKEN_KEY, value);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }

  async function fetchUser() {
    try {
      const resp = await authApi.me();
      user.value = resp.data;
    } catch {
      logout();
    }
  }

  function logout() {
    setToken(null);
    user.value = null;
  }

  return {
    token,
    user,
    isAuthenticated,
    setToken,
    fetchUser,
    logout,
  };
});
