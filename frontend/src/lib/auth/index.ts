import type { NextAuthOptions, Session, User } from 'next-auth';
import type { JWT } from 'next-auth/jwt';
import CognitoProvider from 'next-auth/providers/cognito';
import CredentialsProvider from 'next-auth/providers/credentials';
import { getServerEnv } from '../env';

async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const env = getServerEnv();
    if (env.FRONTEND_AUTH_MODE !== 'cognito' || !env.COGNITO_ISSUER) {
      return token;
    }

    const tokenEndpoint = `${env.COGNITO_ISSUER}/oauth2/token`;
    const response = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...(env.COGNITO_CLIENT_SECRET
          ? {
              Authorization: `Basic ${Buffer.from(
                `${env.COGNITO_CLIENT_ID}:${env.COGNITO_CLIENT_SECRET}`
              ).toString('base64')}`,
            }
          : {}),
      },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: env.COGNITO_CLIENT_ID,
        refresh_token: token.refreshToken as string,
      }),
    });

    const refreshedTokens = await response.json();

    if (!response.ok) {
      throw refreshedTokens;
    }

    return {
      ...token,
      accessToken: refreshedTokens.access_token,
      accessTokenExpires: Date.now() + (refreshedTokens.expires_in ?? 3600) * 1000,
      refreshToken: refreshedTokens.refresh_token ?? token.refreshToken,
    };
  } catch (error) {
    console.error('Error refreshing access token:', error);
    return {
      ...token,
      error: 'RefreshAccessTokenError',
    };
  }
}

export function getAuthOptions(): NextAuthOptions {
  const env = getServerEnv();
  const providers = [];

  if (env.FRONTEND_AUTH_MODE === 'cognito' && env.COGNITO_ISSUER) {
    providers.push(
      CognitoProvider({
        clientId: env.COGNITO_CLIENT_ID,
        clientSecret: env.COGNITO_CLIENT_SECRET,
        issuer: env.COGNITO_ISSUER,
        authorization: {
          params: {
            scope: 'openid email profile',
            response_type: 'code',
          },
        },
      })
    );
  } else {
    // Development mode credentials provider
    providers.push(
      CredentialsProvider({
        id: 'dev-login',
        name: 'Local Developer Account',
        credentials: {
          username: { label: 'Username', type: 'text', placeholder: 'local-developer' },
        },
        async authorize(credentials) {
          const user: User = {
            id: credentials?.username || 'local-developer',
            name: credentials?.username || 'Local Developer',
            email: `${credentials?.username || 'developer'}@local.ecotwin`,
          };
          return user;
        },
      })
    );
  }

  return {
    secret: env.NEXTAUTH_SECRET,
    session: {
      strategy: 'jwt',
      maxAge: 30 * 24 * 60 * 60, // 30 days
    },
    providers,
    callbacks: {
      async jwt({ token, account, user }) {
        if (account && user) {
          token.id = user.id;
          token.name = user.name;
          token.email = user.email;
          if (account.access_token) {
            token.accessToken = account.access_token;
            token.refreshToken = account.refresh_token;
            token.accessTokenExpires = account.expires_at ? account.expires_at * 1000 : Date.now() + 3600000;
          }
          return token;
        }

        // Return token if not expired
        if (typeof token.accessTokenExpires === 'number' && Date.now() < token.accessTokenExpires) {
          return token;
        }

        // Refresh token if expired and refreshToken exists
        if (token.refreshToken) {
          return refreshAccessToken(token);
        }

        return token;
      },
      async session({ session, token }): Promise<Session> {
        // Strip access token from browser-visible session
        return {
          ...session,
          user: {
            name: (token.name as string) || session.user?.name || null,
            email: (token.email as string) || session.user?.email || null,
            image: null,
          },
        };
      },
    },
    pages: {
      signIn: '/account',
    },
  };
}
