from datetime import datetime,timezone,timedelta
import math
from ecotwin.errors import TwinError
URL='https://api.openaq.org/v3'

def pages(client,path,headers,params,max_pages=100):
    values=[]
    for page in range(1,max_pages+1):
        document=client.json(URL+path,headers=headers,params={**params,'page':page,'limit':100})
        rows=document.get('results')
        if not isinstance(rows,list):
            raise TwinError('UPSTREAM_PAYLOAD_INVALID','OpenAQ results must be an array')
        values.extend(rows)
        found=document.get('meta',{}).get('found')
        if len(rows)<100 or isinstance(found,int) and len(values)>=found:
            return values
    raise TwinError('UPSTREAM_PAYLOAD_INVALID','OpenAQ pagination limit exceeded; narrow the study interval')

def fetch_air(client,settings,bbox,lookback_hours=48):
    if not settings.openaq_enabled or not settings.openaq_api_key.get_secret_value():
        raise TwinError('OPENAQ_CREDENTIAL_REQUIRED','Enable OpenAQ and supply a backend API key')
    if not 1<=lookback_hours<=168:
        raise TwinError('MODEL_INPUT_UNSUPPORTED','Air lookback must be 1–168 hours')
    headers={'X-API-Key':settings.openaq_api_key.get_secret_value()}
    now=datetime.now(timezone.utc)
    locations=pages(client,'/locations',headers,{'bbox':','.join(map(str,bbox))})
    observations=[]
    for location in locations:
        lat,lon=location['coordinates']['latitude'],location['coordinates']['longitude']
        if not bbox[0]<=lon<=bbox[2] or not bbox[1]<=lat<=bbox[3]:
            continue
        for sensor in location.get('sensors',[]):
            records=pages(client,f"/sensors/{sensor['id']}/hours",headers,{'datetime_from':(now-timedelta(hours=lookback_hours)).isoformat(),'datetime_to':now.isoformat()})
            for record in records:
                value=record.get('value')
                if value is None:
                    continue
                parameter=record.get('parameter',sensor.get('parameter',{}))
                measured=datetime.fromisoformat(record['period']['datetimeFrom']['utc'].replace('Z','+00:00'))
                if not isinstance(value,(int,float)) or not math.isfinite(value) or not parameter.get('name') or not parameter.get('units') or not measured.tzinfo:
                    raise TwinError('UPSTREAM_PAYLOAD_INVALID','Air measurements require finite value, species, units and UTC time')
                observations.append({'location':location,'sensor_id':str(sensor['id']),'parameter':parameter['name'],'unit':parameter['units'],'value':value,'measured_at':measured.isoformat(),'source_url':URL+f"/sensors/{sensor['id']}/hours"})
    return {'locations':locations,'observations':observations,'coverage':'stations' if observations else 'none','captured_at':now.isoformat()}
