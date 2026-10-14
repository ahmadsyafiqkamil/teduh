import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TEDUH — Prioritas penanganan panas kota',
  description:
    'Alat bantu perencanaan mitigasi Urban Heat Island tingkat kelurahan untuk DKI Jakarta, '
    + 'dengan setiap angka bisa ditelusuri ke sumbernya.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        {/* Two weights beyond the body weight only; design/README.md calls for 400-700 and
            nothing wider. preconnect because the font is above the fold. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
