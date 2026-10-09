from functools import lru_cache
import jwt
from ecotwin.errors import TwinError

@lru_cache(maxsize=4)
def jwks_client(issuer: str):
    return jwt.PyJWKClient(issuer+'/.well-known/jwks.json',cache_jwk_set=True,lifespan=300,timeout=5)

def verify_token(token: str,settings) -> str:
    try:
        if settings.auth_mode=='dev':
            claims=jwt.decode(token,settings.dev_jwt_secret.get_secret_value(),algorithms=['HS256'],issuer='ecotwin-local',audience='ecotwin-local',options={'require':['exp','iat','iss','sub','aud','token_use']})
        else:
            key=jwks_client(settings.issuer).get_signing_key_from_jwt(token)
            claims=jwt.decode(token,key.key,algorithms=['RS256'],issuer=settings.issuer,options={'verify_aud':False,'require':['exp','iat','iss','sub','client_id','token_use']})
            if claims['client_id']!=settings.cognito_client_id:
                raise jwt.InvalidAudienceError('Wrong client')
        if claims['token_use']!='access' or not claims['sub']:
            raise jwt.InvalidTokenError('Access token required')
        return claims['sub']
    except (jwt.PyJWTError,ValueError,KeyError) as exc:
        raise TwinError('UNAUTHORIZED','A valid unexpired access token is required',401) from exc
