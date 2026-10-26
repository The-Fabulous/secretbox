import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || window.location.origin;
export const api = axios.create({ baseURL: API_URL, timeout: 60000 });
export const authConfig = (token) => ({ headers: { Authorization: `Bearer ${token}` } });
