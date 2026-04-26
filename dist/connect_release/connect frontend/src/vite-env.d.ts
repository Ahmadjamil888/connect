/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?: string
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string
  readonly VITE_CONNECT_DASHBOARD_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
