import { redirect } from 'next/navigation';
export default async function SimulatePage({ params }: { params: Promise<{ cityId: string }> }) {
  const { cityId } = await params;
  redirect(`/city/${encodeURIComponent(cityId)}`);
}
