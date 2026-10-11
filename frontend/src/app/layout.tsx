import type { Metadata } from 'next';
import './globals.css';
import 'maplibre-gl/dist/maplibre-gl.css';
import { AppProviders } from '@/providers';
import { Navbar } from '@/components/shell/Navbar';

export const metadata: Metadata = {
  title: 'EcoTwin — City Change Planner',
  description: 'Evidence-backed urban digital twin for land-cover interventions, runoff screening, and solar potential analysis.',
  icons: {
    icon: '/brand/icon.svg',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-background text-ink antialiased">
        <AppProviders>
          <Navbar />
          <main className="flex-1 flex flex-col">{children}</main>
        </AppProviders>
      </body>
    </html>
  );
}
