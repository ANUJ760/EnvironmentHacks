'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
export function Navbar() {
  const pathname = usePathname();
  return <header className="h-16 border-b border-border bg-background px-6 flex items-center justify-between shrink-0">
    <Link href="/explore" className="text-xl font-bold">Eco<span className="text-primary">Twin</span></Link>
    <nav aria-label="Main navigation" className="flex gap-3 text-sm">
      {[['/explore', 'Cities'], ['/data-methodology', 'Evidence'], ['/status', 'Status']].map(([href, label]) => <Link key={href} href={href!} aria-current={pathname.startsWith(href!) ? 'page' : undefined} className="glass-button px-3 py-2 rounded-lg">{label}</Link>)}
    </nav>
  </header>;
}
