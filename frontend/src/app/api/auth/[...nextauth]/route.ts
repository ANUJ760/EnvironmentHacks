import { NextResponse } from 'next/server';
function removed() { return NextResponse.json({ detail: 'Authentication has been removed. The planning workspace is public.' }, { status: 410 }); }
export { removed as GET, removed as POST };
