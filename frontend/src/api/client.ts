import axios from "axios";

export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 10000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("tradingradar_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("tradingradar_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
