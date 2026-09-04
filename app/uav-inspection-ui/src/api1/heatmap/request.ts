import axios from 'axios';
import { BASE_URL } from '../../utils/webroot';

// 创建 axios 实例
const service = axios.create({
  baseURL: `${BASE_URL}api/v1`, // 配合 vite.config.ts 的 proxy 解决跨域；子路径部署时带前缀
  timeout: 30000,     // 默认 30 秒（普通 API 足够）
});

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    // 如果有 Token，可以在这里加上：config.headers.Authorization = `Bearer ${token}`
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
service.interceptors.response.use(
  (response) => {
    if (response.config.responseType === 'blob') {
      return response.data;
    }
    const res = response.data;
    // 假设后端标准返回格式为 { code: 200, data: ..., message: 'success' }
    if (res.code !== 200) {
      console.error('API Error:', res.message);
      return Promise.reject(new Error(res.message || 'Error'));
    }
    return res.data;
  },
  (error) => {
    console.error('网络请求失败:', error);
    return Promise.reject(error);
  }
);

export default service;