/** @type {import('next').NextConfig} */
const nextConfig = {
    images: {
        remotePatterns: [
            {
                protocol: 'https',
                hostname: 'cdn.cloudflare.steamstatic.com',
                pathname: '/apps/dota2/images/**',
            },
            {
                protocol: 'https',
                hostname: 'cdn.dota2.com',
                pathname: '/apps/dota2/images/**',
            },
            {
                protocol: 'https',
                hostname: 'www.opendota.com',
                pathname: '/assets/images/**',
            },
        ],
    },
};

export default nextConfig;
