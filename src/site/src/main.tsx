import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import { AuthProvider } from '@/components/auth/AuthProvider';
import App from './App.tsx';

const cspNonce = (document.querySelector('meta[property="csp-nonce"]') as HTMLMetaElement)?.content ?? undefined;
if (cspNonce) (window as any).__CSP_NONCE__ = cspNonce;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider csp={{ nonce: cspNonce }} theme={{ token: { motion: false } }}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </ConfigProvider>
  </StrictMode>,
);
