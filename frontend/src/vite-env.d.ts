/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_STATIC_BASE?: string;
  readonly BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
