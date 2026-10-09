import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The API is a separate Cloud Run service, so there is nothing to rewrite here; the
  // client reads NEXT_PUBLIC_TEDUH_API directly. Kept explicit so nobody adds a proxy
  // and quietly breaks CORS expectations on the API side.
  env: {
    NEXT_PUBLIC_TEDUH_API: process.env.NEXT_PUBLIC_TEDUH_API ?? 'http://localhost:8080',
  },
};

export default nextConfig;
