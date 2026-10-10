import NextAuth from 'next-auth';
import { getAuthOptions } from '@/lib/auth';

const handler = (req: any, res: any) => NextAuth(req, res, getAuthOptions());

export { handler as GET, handler as POST };
