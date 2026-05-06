/** @type {import('next').NextConfig} */
const nextConfig = {
  // 백엔드 API 프록시 (CORS 우회)
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
