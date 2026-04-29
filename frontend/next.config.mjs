/** @type {import('next').NextConfig} */
const backendApiBaseUrl = (process.env.BACKEND_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendApiBaseUrl}/api/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${backendApiBaseUrl}/health`,
      },
      {
        source: "/readyz",
        destination: `${backendApiBaseUrl}/readyz`,
      },
      {
        source: "/metrics",
        destination: `${backendApiBaseUrl}/metrics`,
      },
      {
        source: "/dashboard/:path*",
        destination: `${backendApiBaseUrl}/dashboard/:path*`,
      },
    ];
  },
};

export default nextConfig;
